"""
A Session is a running instance of the Tribler Core and the Core's central class.

Author(s): Arno Bakker, Niels Zeilmaker, Vadim Bulavintsev
"""

import errno
import logging
import os
import sys
import time as timemod
from asyncio import get_event_loop
from io import StringIO
from traceback import print_exception

from _socket import gaierror

from ipv8.loader import IPv8CommunityLoader
from ipv8.messaging.interfaces.dispatcher.endpoint import DispatcherEndpoint
from ipv8.taskmanager import TaskManager

from ipv8_service import IPv8

from tribler_common.simpledefs import (
    NTFY,
    STATEDIR_CHANNELS_DIR,
    STATEDIR_CHECKPOINT_DIR,
    STATEDIR_DB_DIR,
    STATE_LOAD_CHECKPOINTS,
    STATE_READABLE_STARTED,
    STATE_START_API,
    STATE_START_LIBTORRENT,
    STATE_START_TORRENT_CHECKER,
    STATE_START_WATCH_FOLDER,
    STATE_UPGRADING_READABLE,
)

import tribler_core.utilities.permid as permid_module
from tribler_core.modules.bootstrap import Bootstrap
from tribler_core.modules.ipv8_module_catalog import register_default_launchers
from tribler_core.modules.metadata_store.gigachannel_manager import GigaChannelManager
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.metadata_store.utils import generate_test_channels
from tribler_core.modules.payout_manager import PayoutManager
from tribler_core.modules.resource_monitor import ResourceMonitor
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.tracker_manager import TrackerManager
from tribler_core.modules.versioncheck_manager import VersionCheckManager
from tribler_core.modules.watch_folder import WatchFolder
from tribler_core.notifier import Notifier
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.statistics import TriblerStatistics
from tribler_core.upgrade.upgrade import TriblerUpgrader
from tribler_core.utilities.crypto_patcher import patch_crypto_be_discovery
from tribler_core.utilities.install_dir import get_lib_path

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035  # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

# There are some errors that we are ignoring.
IGNORED_ERRORS = {
    # No route to host: this issue is non-critical since Tribler can still function when a request fails.
    (OSError, 113): "Observed no route to host error (but ignoring)."
                    "This might indicate a problem with your firewall.",
    # Socket block: this sometimes occurs on Windows and is non-critical.
    (BlockingIOError, SOCKET_BLOCK_ERRORCODE): f"Unable to send data due to builtins.OSError {SOCKET_BLOCK_ERRORCODE}",
    (OSError, 51): "Could not send data: network is unreachable.",
    (ConnectionAbortedError, 10053): "An established connection was aborted by the software in your host machine.",
    (ConnectionResetError, 10054): "Connection forcibly closed by the remote host.",
    (OSError, 10022): "Failed to get address info. Error code: 10022",
    (OSError, 16): "Socket error: Device or resource busy. Error code: 16",
    (OSError, 0): "",
    gaierror: "Unable to perform DNS lookup."
}


class Session(TaskManager):
    """
    A Session is a running instance of the Tribler Core and the Core's central class.
    """
    __single = None

    def __init__(self, config, core_test_mode = False):
        """
        A Session object is created
        Only a single session instance can exist at a time in a process.
        :config TriblerConfig object parametrizing the Session
        """
        super(Session, self).__init__()

        get_event_loop().set_exception_handler(self.unhandled_error_observer)

        patch_crypto_be_discovery()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.config = config

        self.notifier = Notifier()

        self.upgrader_enabled = True
        self.upgrader = None
        self.readable_status = ''  # Human-readable string to indicate the status during startup/shutdown of Tribler

        self.ipv8 = None
        self.ipv8_start_time = 0

        self._logger = logging.getLogger(self.__class__.__name__)

        self.shutdownstarttime = None

        self.bootstrap = None

        # modules
        self.ipv8_community_loader = IPv8CommunityLoader()
        register_default_launchers(self.ipv8_community_loader)

        self.api_manager = None
        self.watch_folder = None
        self.version_check_manager = None
        self.resource_monitor = None

        self.gigachannel_manager = None

        self.dlmgr = None  # Libtorrent Manager
        self.tracker_manager = None
        self.torrent_checker = None
        self.tunnel_community = None
        self.bandwidth_community = None
        self.wallets = {}
        self.popularity_community = None
        self.gigachannel_community = None
        self.remote_query_community = None

        self.dht_community = None
        self.payout_manager = None
        self.mds = None  # Metadata Store

        # In test mode, the Core does not communicate with the external world and the state dir is read-only
        self.core_test_mode = core_test_mode

    def load_ipv8_overlays(self):
        self.ipv8_community_loader.load(self.ipv8, self)

    def enable_ipv8_statistics(self):
        if self.config.get_ipv8_statistics():
            for overlay in self.ipv8.overlays:
                self.ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

    def import_bootstrap_file(self):
        with open(self.bootstrap.bootstrap_file, 'r') as f:
            sql_dumb = f.read()
        self._logger.info("Executing bootstrap script")
        # TODO we should do something here...

    async def start_bootstrap_download(self):
        if not self.payout_manager:
            self._logger.warning("Running bootstrap without payout enabled")
        self.bootstrap = Bootstrap(self.config.get_state_dir(), dht=self.dht_community)
        self.bootstrap.start_by_infohash(self.dlmgr.start_download, self.config.get_bootstrap_infohash())
        await self.bootstrap.download.future_finished
        # Temporarily disabling SQL import for experimental release
        #await get_event_loop().run_in_executor(None, self.import_bootstrap_file)
        self.bootstrap.bootstrap_finished = True

    def create_state_directory_structure(self):
        """Create directory structure of the state directory."""

        def create_dir(path):
            if not path.is_dir():
                os.makedirs(path)

        def create_in_state_dir(path):
            create_dir(self.config.get_state_dir() / path)

        create_dir(self.config.get_state_dir())
        create_in_state_dir(STATEDIR_DB_DIR)
        create_in_state_dir(STATEDIR_CHECKPOINT_DIR)
        create_in_state_dir(STATEDIR_CHANNELS_DIR)

    def get_ports_in_config(self):
        """Claim all required random ports."""
        if self.core_test_mode:
            self.config.selected_ports = {}
            return
        self.config.get_libtorrent_port()
        self.config.get_anon_listen_port()
        self.config.get_tunnel_community_socks5_listen_ports()

    def init_keypair(self):
        """
        Set parameters that depend on state_dir.
        """
        trustchain_pairfilename = self.config.get_trustchain_keypair_filename()
        if trustchain_pairfilename.exists():
            self.trustchain_keypair = permid_module.read_keypair_trustchain(trustchain_pairfilename)
        else:
            self.trustchain_keypair = permid_module.generate_keypair_trustchain()

            # Save keypair
            trustchain_pubfilename = self.config.get_state_dir() / 'ecpub_multichain.pem'
            permid_module.save_keypair_trustchain(self.trustchain_keypair, trustchain_pairfilename)
            permid_module.save_pub_key_trustchain(self.trustchain_keypair, trustchain_pubfilename)

        trustchain_testnet_pairfilename = self.config.get_trustchain_testnet_keypair_filename()
        if trustchain_testnet_pairfilename.exists():
            self.trustchain_testnet_keypair = permid_module.read_keypair_trustchain(trustchain_testnet_pairfilename)
        else:
            self.trustchain_testnet_keypair = permid_module.generate_keypair_trustchain()

            # Save keypair
            trustchain_testnet_pubfilename = self.config.get_state_dir() / 'ecpub_trustchain_testnet.pem'
            permid_module.save_keypair_trustchain(self.trustchain_testnet_keypair, trustchain_testnet_pairfilename)
            permid_module.save_pub_key_trustchain(self.trustchain_testnet_keypair, trustchain_testnet_pubfilename)

    def unhandled_error_observer(self, loop, context):
        """
        This method is called when an unhandled error in Tribler is observed.
        It broadcasts the tribler_exception event.
        """
        exception = context.get('exception')

        ignored_message = None
        try:
            ignored_message = IGNORED_ERRORS.get(
                (exception.__class__, exception.errno),
                IGNORED_ERRORS.get(exception.__class__))
        except (ValueError, AttributeError):
            pass
        if ignored_message is not None:
            self._logger.error(ignored_message if ignored_message != "" else context.get('message'))
            return

        text = str(exception or context.get('message'))

        # We already have a check for invalid infohash when adding a torrent, but if somehow we get this
        # error then we simply log and ignore it.
        if isinstance(exception, RuntimeError) and 'invalid info-hash' in text:
            self._logger.error("Invalid info-hash found")
            return

        text_long = text
        exc = context.get('exception')
        if exc:
            with StringIO() as buffer:
                print_exception(type(exc), exc, exc.__traceback__, file=buffer)
                text_long = text_long + "\n--LONG TEXT--\n" + buffer.getvalue()
        text_long = text_long + "\n--CONTEXT--\n" + str(context)

        self._logger.error("Unhandled exception occurred! %s", text_long)

        if self.api_manager and len(text_long) > 0:
            self.api_manager.get_endpoint('events').on_tribler_exception(text_long)
            self.api_manager.get_endpoint('state').on_tribler_exception(text_long)

    def get_tribler_statistics(self):
        """Return a dictionary with general Tribler statistics."""
        return TriblerStatistics(self).get_tribler_statistics()

    def get_ipv8_statistics(self):
        """Return a dictionary with IPv8 statistics."""
        return TriblerStatistics(self).get_ipv8_statistics()

    async def start(self):
        """
        Start a Tribler session by initializing the LaunchManyCore class, opening the database and running the upgrader.
        Returns a deferred that fires when the Tribler session is ready for use.

        :param config: a TriblerConfig object
        """

        self._logger.info("Session is using state directory: %s", self.config.get_state_dir())
        self.get_ports_in_config()
        self.create_state_directory_structure()
        self.init_keypair()

        # Start the REST API before the upgrader since we want to send interesting upgrader events over the socket
        if self.config.get_api_http_enabled() or self.config.get_api_https_enabled():
            self.api_manager = RESTManager(self)
            self.readable_status = STATE_START_API
            await self.api_manager.start()

        if self.upgrader_enabled and not self.core_test_mode:
            self.upgrader = TriblerUpgrader(self)
            self.readable_status = STATE_UPGRADING_READABLE
            try:
                await self.upgrader.run()
            except Exception as e:
                self._logger.error("Error in Upgrader callback chain: %s", e)

        self.tracker_manager = TrackerManager(self)

        # Start torrent checker before Popularity community is loaded
        if self.config.get_torrent_checking_enabled() and not self.core_test_mode:
            self.readable_status = STATE_START_TORRENT_CHECKER
            self.torrent_checker = TorrentChecker(self)
            await self.torrent_checker.initialize()

        # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
        # certificates provided by the system trust store.
        if sys.platform == 'darwin':
            os.environ['SSL_CERT_FILE'] = str((get_lib_path() / 'root_certs_mac.pem'))

        if self.config.get_chant_enabled():
            channels_dir = self.config.get_chant_channels_dir()
            metadata_db_name = 'metadata.db' if not self.config.get_chant_testnet() else 'metadata_testnet.db'
            database_path = self.config.get_state_dir() / 'sqlite' / metadata_db_name
            self.mds = MetadataStore(database_path, channels_dir, self.trustchain_keypair,
                                     notifier=self.notifier,
                                     disable_sync=self.core_test_mode)
            if self.core_test_mode:
                generate_test_channels(self.mds)

        # IPv8
        if self.config.get_ipv8_enabled():
            from ipv8.configuration import ConfigBuilder
            ipv8_config_builder = (ConfigBuilder()
                                   .set_port(self.config.get_ipv8_port())
                                   .set_address(self.config.get_ipv8_address())
                                   .clear_overlays()
                                   .clear_keys()  # We load the keys ourselves
                                   .set_working_directory(str(self.config.get_state_dir()))
                                   .set_walker_interval(self.config.get_ipv8_walk_interval()))

            if self.config.get_ipv8_bootstrap_override():
                import ipv8.community as community_file
                community_file._DEFAULT_ADDRESSES = [self.config.get_ipv8_bootstrap_override()]
                community_file._DNS_ADDRESSES = []

            self.ipv8 = IPv8(ipv8_config_builder.finalize(),
                             enable_statistics=self.config.get_ipv8_statistics()) \
                if not self.core_test_mode else IPv8(ipv8_config_builder.finalize(),
                                                     endpoint_override=DispatcherEndpoint([]))
            await self.ipv8.start()

            self.config.set_anon_proxy_settings(2, ("127.0.0.1",
                                                    self.
                                                    config.get_tunnel_community_socks5_listen_ports()))
            self.ipv8_start_time = timemod.time()
            self.load_ipv8_overlays()
            if not self.core_test_mode:
                self.enable_ipv8_statistics()
            if self.api_manager:
                self.api_manager.set_ipv8_session(self.ipv8)
            if self.config.get_tunnel_community_enabled():
                await self.tunnel_community.wait_for_socks_servers()
            if self.config.get_ipv8_walk_scaling_enabled():
                from tribler_core.modules.ipv8_health_monitor import IPv8Monitor
                IPv8Monitor(self.ipv8,
                            self.config.get_ipv8_walk_interval(),
                            self.config.get_ipv8_walk_scaling_upper_limit()).start(self)

        # Note that currently we should only start libtorrent after the SOCKS5 servers have been started
        if self.config.get_libtorrent_enabled():
            self.readable_status = STATE_START_LIBTORRENT
            from tribler_core.modules.libtorrent.download_manager import DownloadManager
            self.dlmgr = DownloadManager(self, dummy_mode=self.core_test_mode)
            self.dlmgr.initialize()
            self.readable_status = STATE_LOAD_CHECKPOINTS
            await self.dlmgr.load_checkpoints()
            if self.core_test_mode:
                await self.dlmgr.start_download_from_uri("magnet:?xt=urn:btih:0000000000000000000000000000000000000000")
        self.readable_status = STATE_READABLE_STARTED

        if self.config.get_watch_folder_enabled():
            self.readable_status = STATE_START_WATCH_FOLDER
            self.watch_folder = WatchFolder(self)
            self.watch_folder.start()

        if self.config.get_resource_monitor_enabled() and not self.core_test_mode:
            self.resource_monitor = ResourceMonitor(self)
            self.resource_monitor.start()

        if self.config.get_version_checker_enabled() and not self.core_test_mode:
            self.version_check_manager = VersionCheckManager(self)
            self.version_check_manager.start()

        if self.config.get_ipv8_enabled():
            self.payout_manager = PayoutManager(self.bandwidth_community, self.dht_community)

        # GigaChannel Manager should be started *after* resuming the downloads,
        # because it depends on the states of torrent downloads
        if self.config.get_chant_enabled() and self.config.get_chant_manager_enabled()\
                and self.config.get_libtorrent_enabled:
            self.gigachannel_manager = GigaChannelManager(self)
            if not self.core_test_mode:
                self.gigachannel_manager.start()

        if self.config.get_bootstrap_enabled() and not self.core_test_mode:
            self.register_task('bootstrap_download', self.start_bootstrap_download)

        self.notifier.notify(NTFY.TRIBLER_STARTED)

    async def shutdown(self):
        """
        Checkpoints the session and closes it, stopping the download engine.
        This method has to be called from the reactor thread.
        """
        self.shutdownstarttime = timemod.time()

        # Indicates we are shutting down core. With this environment variable set
        # to 'TRUE', RESTManager will no longer accepts any new requests.
        os.environ['TRIBLER_SHUTTING_DOWN'] = "TRUE"

        if self.dlmgr:
            self.dlmgr.stop_download_states_callback()

        await self.shutdown_task_manager()

        if self.torrent_checker:
            self.notify_shutdown_state("Shutting down Torrent Checker...")
            await self.torrent_checker.shutdown()
        self.torrent_checker = None

        if self.gigachannel_manager:
            self.notify_shutdown_state("Shutting down Gigachannel Manager...")
            await self.gigachannel_manager.shutdown()
        self.gigachannel_manager = None

        if self.version_check_manager:
            self.notify_shutdown_state("Shutting down Version Checker...")
            await self.version_check_manager.stop()
        self.version_check_manager = None

        if self.resource_monitor:
            self.notify_shutdown_state("Shutting down Resource Monitor...")
            await self.resource_monitor.stop()
        self.resource_monitor = None

        if self.bootstrap:
            # We shutdown the bootstrap module before IPv8 since it uses the DHTCommunity.
            await self.bootstrap.shutdown()
        self.bootstrap = None

        self.tracker_manager = None

        if self.tunnel_community and self.bandwidth_community:
            # We unload these overlays manually since the TrustChain has to be unloaded after the tunnel overlay.
            tunnel_community = self.tunnel_community
            self.tunnel_community = None
            self.notify_shutdown_state("Unloading Tunnel Community...")
            await self.ipv8.unload_overlay(tunnel_community)
            bandwidth_community = self.bandwidth_community
            self.bandwidth_community = None
            self.notify_shutdown_state("Shutting down Bandwidth Community...")
            await self.ipv8.unload_overlay(bandwidth_community)

        if self.ipv8:
            self.notify_shutdown_state("Shutting down IPv8...")
            await self.ipv8.stop(stop_loop=False)
        self.ipv8 = None

        if self.payout_manager:
            await self.payout_manager.shutdown()
            self.payout_manager = None

        if self.watch_folder:
            self.notify_shutdown_state("Shutting down Watch Folder...")
            await self.watch_folder.stop()
        self.watch_folder = None

        if not self.core_test_mode:
            self.notify_shutdown_state("Saving configuration...")
            self.config.write()

        if self.dlmgr:
            await self.dlmgr.shutdown()
        self.dlmgr = None

        if self.mds:
            self.notify_shutdown_state("Shutting down Metadata Store...")
            self.mds.shutdown()
        self.mds = None

        # We close the API manager as late as possible during shutdown.
        if self.api_manager:
            self.notify_shutdown_state("Shutting down API Manager...")
            await self.api_manager.stop()
        self.api_manager = None

    def notify_shutdown_state(self, state):
        self._logger.info("Tribler shutdown state notification:%s", state)
        self.notifier.notify(NTFY.TRIBLER_SHUTDOWN_STATE, state)
