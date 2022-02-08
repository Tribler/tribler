import asyncio
import logging
import logging.config
import os
import signal
import sys
from typing import List

from tribler_core import notifications
from tribler_core.check_os import (
    check_and_enable_code_tracing,
    set_process_priority,
    should_kill_other_tribler_instances,
)
from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.base import Component, Session
from tribler_core.components.gigachannel.gigachannel_component import GigaChannelComponent
from tribler_core.components.gigachannel_manager.gigachannel_manager_component import GigachannelManagerComponent
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.payout.payout_component import PayoutComponent
from tribler_core.components.popularity.popularity_component import PopularityComponent
from tribler_core.components.reporter.exception_handler import default_core_exception_handler
from tribler_core.components.reporter.reporter_component import ReporterComponent
from tribler_core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.tag.tag_component import TagComponent
from tribler_core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent
from tribler_core.components.tunnel.tunnel_component import TunnelsComponent
from tribler_core.components.version_check.version_check_component import VersionCheckComponent
from tribler_core.components.watch_folder.watch_folder_component import WatchFolderComponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.logger.logger import load_logger_config
from tribler_core.sentry_reporter.sentry_reporter import SentryReporter, SentryStrategy
from tribler_core.upgrade.version_manager import VersionHistory
from tribler_core.utilities.process_checker import ProcessChecker

logger = logging.getLogger(__name__)
CONFIG_FILE_NAME = 'triblerd.conf'


# pylint: disable=import-outside-toplevel


def components_gen(config: TriblerConfig):
    """This function defines components that will be used in Tibler
    """
    yield ReporterComponent()
    if config.api.http_enabled or config.api.https_enabled:
        yield RESTComponent()
    if config.chant.enabled or config.torrent_checking.enabled:
        yield MetadataStoreComponent()
    if config.ipv8.enabled:
        yield Ipv8Component()

    yield KeyComponent()
    yield TagComponent()

    if config.libtorrent.enabled:
        yield LibtorrentComponent()
    if config.ipv8.enabled and config.chant.enabled:
        yield GigaChannelComponent()
    if config.ipv8.enabled:
        yield BandwidthAccountingComponent()
    if config.resource_monitor.enabled:
        yield ResourceMonitorComponent()

    # The components below are skipped if config.gui_test_mode == True
    if config.gui_test_mode:
        return

    if config.libtorrent.enabled:
        yield SocksServersComponent()

    if config.torrent_checking.enabled:
        yield TorrentCheckerComponent()
    if config.ipv8.enabled and config.torrent_checking.enabled and config.popularity_community.enabled:
        yield PopularityComponent()
    if config.ipv8.enabled and config.tunnel_community.enabled:
        yield TunnelsComponent()
    if config.ipv8.enabled:
        yield PayoutComponent()
    if config.watch_folder.enabled:
        yield WatchFolderComponent()
    if config.general.version_checker_enabled:
        yield VersionCheckComponent()
    if config.chant.enabled and config.chant.manager_enabled and config.libtorrent.enabled:
        yield GigachannelManagerComponent()


async def core_session(config: TriblerConfig, components: List[Component]):
    session = Session(config, components, failfast=False)
    signal.signal(signal.SIGTERM, lambda signum, stack: session.shutdown_event.set)
    async with session.start() as session:
        # If there is a config error, report to the user via GUI notifier
        if config.error:
            session.notifier[notifications.report_config_error](config.error)

        # SHUTDOWN
        await session.shutdown_event.wait()

        if not config.gui_test_mode:
            session.notifier[notifications.tribler_shutdown_state]("Saving configuration...")
            config.write()


def run_tribler_core_session(api_port, api_key, state_dir, gui_test_mode=False):
    """
    This method will start a new Tribler session.
    Note that there is no direct communication between the GUI process and the core: all communication is performed
    through the HTTP API.
    """
    logger.info(f'Start tribler core. API port: "{api_port}". '
                f'API key: "{api_key}". State dir: "{state_dir}". '
                f'Core test mode: "{gui_test_mode}"')

    config = TriblerConfig.load(
        file=state_dir / CONFIG_FILE_NAME,
        state_dir=state_dir,
        reset_config_on_error=True)
    config.gui_test_mode = gui_test_mode

    if SentryReporter.is_in_test_mode():
        default_core_exception_handler.sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED

    config.api.http_port = int(api_port)
    # If the API key is set to an empty string, it will remain disabled
    if config.api.key not in ('', api_key):
        config.api.key = api_key
        config.write()  # Immediately write the API key so other applications can use it
    config.api.http_enabled = True

    priority_order = config.resource_monitor.cpu_priority
    set_process_priority(pid=os.getpid(), priority_order=priority_order)

    # Enable tracer if --trace-debug or --trace-exceptions flag is present in sys.argv
    log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
    trace_logger = check_and_enable_code_tracing('core', log_dir)

    logging.getLogger('asyncio').setLevel(logging.WARNING)

    if sys.platform.startswith('win'):
        # TODO for the moment being, we use the SelectorEventLoop on Windows, since with the ProactorEventLoop, ipv8
        # peer discovery becomes unstable. Also see issue #5485.
        asyncio.set_event_loop(asyncio.SelectorEventLoop())

    loop = asyncio.get_event_loop()
    exception_handler = default_core_exception_handler
    loop.set_exception_handler(exception_handler.unhandled_error_observer)

    try:
        loop.run_until_complete(core_session(config, components=list(components_gen(config))))
    finally:
        if trace_logger:
            trace_logger.close()

        # Flush the logs to the file before exiting
        for handler in logging.getLogger().handlers:
            handler.flush()


def run_core(api_port, api_key, root_state_dir, parsed_args):
    should_kill_other_tribler_instances(root_state_dir)
    logger.info('Running Core' + ' in gui_test_mode' if parsed_args.gui_test_mode else '')
    load_logger_config('tribler-core', root_state_dir)

    # Check if we are already running a Tribler instance
    process_checker = ProcessChecker(root_state_dir)
    if process_checker.already_running:
        logger.info('Core is already running, exiting')
        sys.exit(1)
    process_checker.create_lock_file()
    version_history = VersionHistory(root_state_dir)
    state_dir = version_history.code_version.directory
    try:
        run_tribler_core_session(api_port, api_key, state_dir, gui_test_mode=parsed_args.gui_test_mode)
    finally:
        logger.info('Remove lock file')
        process_checker.remove_lock_file()
