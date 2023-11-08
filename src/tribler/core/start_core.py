import asyncio
import logging
import logging.config
import os
import signal
import sys
from pathlib import Path
from typing import List, Optional

from tribler.core import notifications
from tribler.core.check_os import (
    check_and_enable_code_tracing,
    set_process_priority,
)
from tribler.core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler.core.components.component import Component
from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.gigachannel.gigachannel_component import GigaChannelComponent
from tribler.core.components.gigachannel_manager.gigachannel_manager_component import GigachannelManagerComponent
from tribler.core.components.gui_process_watcher.gui_process_watcher import GuiProcessWatcher
from tribler.core.components.gui_process_watcher.gui_process_watcher_component import GuiProcessWatcherComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.knowledge_component import KnowledgeComponent
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.payout.payout_component import PayoutComponent
from tribler.core.components.popularity.popularity_component import PopularityComponent
from tribler.core.components.reporter.exception_handler import default_core_exception_handler
from tribler.core.components.reporter.reporter_component import ReporterComponent
from tribler.core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent
from tribler.core.components.restapi.restapi_component import RESTComponent
from tribler.core.components.session import Session
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler.core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent
from tribler.core.components.tunnel.tunnel_component import TunnelsComponent
from tribler.core.components.version_check.version_check_component import VersionCheckComponent
from tribler.core.components.watch_folder.watch_folder_component import WatchFolderComponent
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.logger.logger import load_logger_config
from tribler.core.sentry_reporter.sentry_reporter import SentryReporter, SentryStrategy
from tribler.core.upgrade.version_manager import VersionHistory
from tribler.core.utilities import slow_coro_detection
from tribler.core.utilities.process_manager import ProcessKind, ProcessManager, TriblerProcess, \
    set_global_process_manager

logger = logging.getLogger(__name__)
CONFIG_FILE_NAME = 'triblerd.conf'


# pylint: disable=import-outside-toplevel


def components_gen(config: TriblerConfig):
    """This function defines components that will be used in Tibler
    """
    yield ReporterComponent()
    yield GuiProcessWatcherComponent()
    yield DatabaseComponent()
    yield RESTComponent()
    if config.chant.enabled or config.torrent_checking.enabled:
        yield MetadataStoreComponent()
    if config.ipv8.enabled:
        yield Ipv8Component()

    yield KeyComponent()
    yield KnowledgeComponent()

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
    yield WatchFolderComponent()
    if config.general.version_checker_enabled:
        yield VersionCheckComponent()
    if config.chant.enabled and config.chant.manager_enabled and config.libtorrent.enabled:
        yield GigachannelManagerComponent()


async def core_session(config: TriblerConfig, components: List[Component]) -> int:
    """
    Async task for running a new Tribler session.

    Returns an exit code, which is non-zero if the Tribler session finished with an error.
    """
    logger.info('Start tribler core session...')
    session = Session(config, components, failfast=False)
    signal.signal(signal.SIGTERM, lambda signum, stack: session.shutdown_event.set)
    async with session:
        # If there is a config error, report to the user via GUI notifier
        if config.error:
            logger.warning(f'Config error: {config.error}')
            session.notifier[notifications.report_config_error](config.error)

        # SHUTDOWN
        logger.warning('Waiting for the shutdown...')
        await session.shutdown_event.wait()
        logger.info('Shutdown event fired')

        if not config.gui_test_mode:
            session.notifier[notifications.tribler_shutdown_state]("Saving configuration...")
            config.write()

    return session.exit_code


def run_tribler_core_session(api_port: Optional[int], api_key: str,
                             state_dir: Path, gui_test_mode: bool = False) -> int:
    """
    This method will start a new Tribler session.
    Note that there is no direct communication between the GUI process and the core: all communication is performed
    through the HTTP API.

    Returns an exit code value, which is non-zero if the Tribler session finished with an error.
    """
    logger.info(f'Start tribler core. API port: "{api_port or "<not specified>"}". '
                f'API key: "{api_key}". State dir: "{state_dir}". '
                f'Core test mode: "{gui_test_mode}"')

    slow_coro_detection.patch_asyncio()  # Track the current coroutine handled by asyncio
    slow_coro_detection.start_watching_thread()  # Run a separate thread to watch for the main thread asyncio freezes

    config = TriblerConfig.load(state_dir=state_dir, reset_config_on_error=True)
    config.gui_test_mode = gui_test_mode

    if SentryReporter.is_in_test_mode():
        default_core_exception_handler.sentry_reporter.global_strategy = SentryStrategy.SEND_ALLOWED

    # The -1 value is assigned for backward compatibility reasons when the port is not specified.
    # When RESTManager actually uses the value, it converts -1 to zero.
    # It is possible that later we can directly store zero to config.api.http_port, but I prefer to be safe now.
    config.api.http_port = api_port or -1
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

    loop = asyncio.get_event_loop()
    exception_handler = default_core_exception_handler
    loop.set_exception_handler(exception_handler.unhandled_error_observer)

    try:
        exit_code = loop.run_until_complete(core_session(config, components=list(components_gen(config))))
    finally:
        if trace_logger:
            trace_logger.close()

        # Flush the logs to the file before exiting
        for handler in logging.getLogger().handlers:
            handler.flush()

    return exit_code


def run_core(api_port: Optional[int], api_key: Optional[str], root_state_dir, parsed_args):
    logger.info(f"Running Core in {'gui_test_mode' if parsed_args.gui_test_mode else 'normal mode'}")

    gui_pid = GuiProcessWatcher.get_gui_pid()
    current_process = TriblerProcess.current_process(ProcessKind.Core, creator_pid=gui_pid)
    process_manager = ProcessManager(root_state_dir, current_process)
    set_global_process_manager(process_manager)
    current_process_is_primary = process_manager.current_process.become_primary()

    load_logger_config('tribler-core', root_state_dir, current_process_is_primary)

    if not current_process_is_primary:
        msg = 'Another Core process is already running'
        logger.warning(msg)
        process_manager.sys_exit(1, msg)

    version_history = VersionHistory(root_state_dir)
    state_dir = version_history.code_version.directory
    exit_code = run_tribler_core_session(api_port, api_key, state_dir, gui_test_mode=parsed_args.gui_test_mode)
    process_manager.sys_exit(exit_code)
