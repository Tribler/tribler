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

from anydex.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from anydex.wallet.tc_wallet import TrustchainWallet

from ipv8.dht.provider import DHTCommunityProvider
from ipv8.messaging.anonymization.community import TunnelSettings
from ipv8.peer import Peer
from ipv8.peerdiscovery.churn import RandomChurn
from ipv8.peerdiscovery.community import DiscoveryCommunity, PeriodicSimilarity
from ipv8.peerdiscovery.discovery import EdgeWalk, RandomWalk
from ipv8.taskmanager import TaskManager

from ipv8_service import IPv8

from tribler_common.simpledefs import (
    NTFY,
    STATEDIR_CHANNELS_DIR,
    STATEDIR_CHECKPOINT_DIR,
    STATEDIR_DB_DIR,
    STATEDIR_WALLET_DIR,
    STATE_LOAD_CHECKPOINTS,
    STATE_READABLE_STARTED,
    STATE_START_API,
    STATE_START_CREDIT_MINING,
    STATE_START_LIBTORRENT,
    STATE_START_TORRENT_CHECKER,
    STATE_START_WATCH_FOLDER,
    STATE_UPGRADING_READABLE,
)

import tribler_core.utilities.permid as permid_module
from tribler_core.modules.bootstrap import Bootstrap
from tribler_core.modules.metadata_store.gigachannel_manager import GigaChannelManager
from tribler_core.modules.metadata_store.store import MetadataStore
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


class Session(TaskManager):
    """
    A Session is a running instance of the Tribler Core and the Core's central class.
    """
    __single = None

    def __init__(self, config):
        """
        A Session object is created
        Only a single session instance can exist at a time in a process.
        :config TriblerConfig object parametrising the Session
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
        self.api_manager = None
        self.watch_folder = None
        self.version_check_manager = None
        self.resource_monitor = None

        self.gigachannel_manager = None

        self.ltmgr = None  # Libtorrent Manager
        self.tracker_manager = None
        self.torrent_checker = None
        self.tunnel_community = None
        self.trustchain_community = None
        self.wallets = {}
        self.popularity_community = None
        self.gigachannel_community = None
        self.remote_query_community = None

        self.credit_mining_manager = None
        self.market_community = None
        self.dht_community = None
        self.payout_manager = None
        self.mds = None  # Metadata Store

    def load_ipv8_overlays(self):
        if self.config.get_testnet():
            peer = Peer(self.trustchain_testnet_keypair)
        else:
            peer = Peer(self.trustchain_keypair)
        discovery_community = DiscoveryCommunity(peer, self.ipv8.endpoint, self.ipv8.network)
        discovery_community.resolve_dns_bootstrap_addresses()
        self.ipv8.overlays.append(discovery_community)
        self.ipv8.strategies.append((RandomChurn(discovery_community), -1))
        self.ipv8.strategies.append((PeriodicSimilarity(discovery_community), -1))
        self.ipv8.strategies.append((RandomWalk(discovery_community), 20))

        # TrustChain Community
        if self.config.get_trustchain_enabled():
            from ipv8.attestation.trustchain.community import TrustChainCommunity, \
                TrustChainTestnetCommunity

            community_cls = TrustChainTestnetCommunity if self.config.get_testnet() else TrustChainCommunity
            self.trustchain_community = community_cls(peer, self.ipv8.endpoint,
                                                      self.ipv8.network,
                                                      working_directory=self.config.get_state_dir())
            self.ipv8.overlays.append(self.trustchain_community)
            self.ipv8.strategies.append((EdgeWalk(self.trustchain_community), 20))

            tc_wallet = TrustchainWallet(self.trustchain_community)
            self.wallets[tc_wallet.get_identifier()] = tc_wallet

        # DHT Community
        if self.config.get_dht_enabled():
            from ipv8.dht.discovery import DHTDiscoveryCommunity

            self.dht_community = DHTDiscoveryCommunity(peer, self.ipv8.endpoint, self.ipv8.network)
            self.ipv8.overlays.append(self.dht_community)
            self.ipv8.strategies.append((RandomWalk(self.dht_community), 20))

        # Tunnel Community
        if self.config.get_tunnel_community_enabled():
            from tribler_core.modules.tunnel.community.triblertunnel_community import TriblerTunnelCommunity,\
                                                                               TriblerTunnelTestnetCommunity
            from tribler_core.modules.tunnel.community.discovery import GoldenRatioStrategy
            community_cls = TriblerTunnelTestnetCommunity if self.config.get_testnet() else \
                TriblerTunnelCommunity

            random_slots = self.config.get_tunnel_community_random_slots()
            competing_slots = self.config.get_tunnel_community_competing_slots()

            dht_provider = DHTCommunityProvider(self.dht_community, self.config.get_ipv8_port())
            settings = TunnelSettings()
            settings.min_circuits = 3
            settings.max_circuits = 10
            self.tunnel_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network,
                                                  tribler_session=self,
                                                  dht_provider=dht_provider,
                                                  ipv8=self.ipv8,
                                                  bandwidth_wallet=self.wallets["MB"],
                                                  random_slots=random_slots,
                                                  competing_slots=competing_slots,
                                                  settings=settings)
            self.ipv8.overlays.append(self.tunnel_community)
            self.ipv8.strategies.append((RandomWalk(self.tunnel_community), 20))
            self.ipv8.strategies.append((GoldenRatioStrategy(self.tunnel_community), -1))

        # Market Community
        if self.config.get_market_community_enabled() and self.config.get_dht_enabled():
            from anydex.core.community import MarketCommunity, MarketTestnetCommunity

            community_cls = MarketTestnetCommunity if self.config.get_testnet() else MarketCommunity
            self.market_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network,
                                                  trustchain=self.trustchain_community,
                                                  dht=self.dht_community,
                                                  wallets=self.wallets,
                                                  working_directory=self.config.get_state_dir(),
                                                  record_transactions=self.config.get_record_transactions())

            self.ipv8.overlays.append(self.market_community)

            self.ipv8.strategies.append((RandomWalk(self.market_community), 20))

        # Popular Community
        if self.config.get_popularity_community_enabled():
            from tribler_core.modules.popularity.popularity_community import PopularityCommunity

            self.popularity_community = PopularityCommunity(peer, self.ipv8.endpoint, self.ipv8.network,
                                                            metadata_store=self.mds,
                                                            torrent_checker=self.torrent_checker)

            self.ipv8.overlays.append(self.popularity_community)
            self.ipv8.strategies.append((RandomWalk(self.popularity_community), 20))

        # Gigachannel Community
        if self.config.get_chant_enabled():
            from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity, GigaChannelTestnetCommunity
            from tribler_core.modules.metadata_store.community.sync_strategy import SyncChannels

            community_cls = GigaChannelTestnetCommunity if self.config.get_testnet() else GigaChannelCommunity
            self.gigachannel_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network, self.mds,
                                                       notifier=self.notifier)

            self.ipv8.overlays.append(self.gigachannel_community)

            self.ipv8.strategies.append((RandomWalk(self.gigachannel_community), 20))
            self.ipv8.strategies.append((SyncChannels(self.gigachannel_community), 20))

            # Gigachannel RemoteQuery Community
            from tribler_core.modules.metadata_store.community.remote_query_community \
                import RemoteQueryCommunity, RemoteQueryTestnetCommunity

            community_cls = RemoteQueryTestnetCommunity if self.config.get_testnet() else RemoteQueryCommunity
            self.remote_query_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network, self.mds,
                                                        notifier=self.notifier)

            self.ipv8.overlays.append(self.remote_query_community)
            self.ipv8.strategies.append((RandomWalk(self.remote_query_community), 50))

    def enable_ipv8_statistics(self):
        if self.config.get_ipv8_statistics():
            for overlay in self.ipv8.overlays:
                self.ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

    def import_bootstrap_file(self):
        with open(self.bootstrap.bootstrap_file, 'r') as f:
            sql_dumb = f.read()
        self._logger.info("Executing script for trustchain bootstrap")
        self.trustchain_community.persistence.executescript(sql_dumb)
        self.trustchain_community.persistence.commit()

    async def start_bootstrap_download(self):
        if not self.payout_manager:
            self._logger.warning("Running bootstrap without payout enabled")
        self.bootstrap = Bootstrap(self.config.get_state_dir(), dht=self.dht_community)
        self.bootstrap.start_by_infohash(self.ltmgr.start_download, self.config.get_bootstrap_infohash())
        if self.trustchain_community:
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
        create_in_state_dir(STATEDIR_WALLET_DIR)
        create_in_state_dir(STATEDIR_CHANNELS_DIR)

    def get_ports_in_config(self):
        """Claim all required random ports."""
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
        text = str(context.get('exception', '')) or context['message']

        # There are some errors that we are ignoring.
        # No route to host: this issue is non-critical since Tribler can still function when a request fails.
        if 'builtins.OSError' in text and '[Errno 113]' in text:
            self._logger.error("Observed no route to host error (but ignoring)."
                               "This might indicate a problem with your firewall.")
            return

        # Socket block: this sometimes occurres on Windows and is non-critical.
        if 'builtins.OSError' in text and '[Errno %s]' % SOCKET_BLOCK_ERRORCODE in text:
            self._logger.error("Unable to send data due to builtins.OSError %s", SOCKET_BLOCK_ERRORCODE)
            return

        if 'builtins.OSError' in text and '[Errno 51]' in text:
            self._logger.error("Could not send data: network is unreachable.")
            return

        if 'builtins.OSError' in text and '[Errno 11001]' in text:
            self._logger.error("Unable to perform DNS lookup.")
            return

        if 'builtins.OSError' in text and '[Errno 10053]' in text:
            self._logger.error("An established connection was aborted by the software in your host machine.")
            return

        if 'builtins.OSError' in text and '[Errno 10054]' in text:
            self._logger.error("Connection forcibly closed by the remote host.")
            return

        if 'builtins.OSError' in text and '[Errno 10022]' in text:
            self._logger.error("Failed to get address info. Error code: 10022")
            return

        if 'builtins.OSError' in text and '[Errno 16]' in text:
            self._logger.error("Socket error: Device or resource busy. Error code: 16")
            return

        if 'builtins.OSError' in text and '[Errno 0]' in text:
            self._logger.error(text)
            return

        if 'builtins.OSError' in text and '[Errno -2]' in text:
            self._logger.error(text)
            return

        # We already have a check for invalid infohash when adding a torrent, but if somehow we get this
        # error then we simply log and ignore it.
        if 'exceptions.RuntimeError: invalid info-hash' in text:
            self._logger.error("Invalid info-hash found")
            return

        text_long = text
        exc = context.get('exception')
        if exc:
            with StringIO() as buffer:
                print_exception(type(exc), exc, exc.__traceback__, file=buffer)
                text_long = buffer.getvalue()

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
        if self.config.get_http_api_enabled():
            self.api_manager = RESTManager(self)
            self.readable_status = STATE_START_API
            await self.api_manager.start()

        if self.upgrader_enabled:
            self.upgrader = TriblerUpgrader(self)
            self.readable_status = STATE_UPGRADING_READABLE
            try:
                await self.upgrader.run()
            except Exception as e:
                self._logger.error("Error in Upgrader callback chain: %s", e)

        self.tracker_manager = TrackerManager(self)

        # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
        # certificates provided by the system trust store.
        if sys.platform == 'darwin':
            os.environ['SSL_CERT_FILE'] = str((get_lib_path() / 'root_certs_mac.pem'))

        if self.config.get_chant_enabled():
            channels_dir = self.config.get_chant_channels_dir()
            metadata_db_name = 'metadata.db' if not self.config.get_testnet() else 'metadata_testnet.db'
            database_path = self.config.get_state_dir() / 'sqlite' / metadata_db_name
            self.mds = MetadataStore(database_path, channels_dir, self.trustchain_keypair)

        # IPv8
        if self.config.get_ipv8_enabled():
            from ipv8.configuration import get_default_configuration
            ipv8_config = get_default_configuration()
            ipv8_config['port'] = self.config.get_ipv8_port()
            ipv8_config['address'] = self.config.get_ipv8_address()
            ipv8_config['overlays'] = []
            ipv8_config['keys'] = []  # We load the keys ourselves

            if self.config.get_ipv8_bootstrap_override():
                import ipv8.community as community_file
                community_file._DEFAULT_ADDRESSES = [self.config.get_ipv8_bootstrap_override()]
                community_file._DNS_ADDRESSES = []

            self.ipv8 = IPv8(ipv8_config, enable_statistics=self.config.get_ipv8_statistics())
            await self.ipv8.start()

            self.config.set_anon_proxy_settings(2, ("127.0.0.1",
                                                    self.
                                                    config.get_tunnel_community_socks5_listen_ports()))
            self.ipv8_start_time = timemod.time()
            self.load_ipv8_overlays()
            self.enable_ipv8_statistics()
            if self.api_manager:
                self.api_manager.set_ipv8_session(self.ipv8)
            if self.config.get_tunnel_community_enabled():
                await self.tunnel_community.wait_for_socks_servers()

        # Note that currently we should only start libtorrent after the SOCKS5 servers have been started
        if self.config.get_libtorrent_enabled():
            self.readable_status = STATE_START_LIBTORRENT
            from tribler_core.modules.libtorrent.libtorrent_mgr import LibtorrentMgr
            self.ltmgr = LibtorrentMgr(self)
            self.ltmgr.initialize()
            self.readable_status = STATE_LOAD_CHECKPOINTS
            await self.ltmgr.load_checkpoints()
        self.readable_status = STATE_READABLE_STARTED

        if self.config.get_torrent_checking_enabled():
            self.readable_status = STATE_START_TORRENT_CHECKER
            self.torrent_checker = TorrentChecker(self)
            await self.torrent_checker.initialize()

        # Wallets
        if self.config.get_bitcoinlib_enabled():
            try:
                from anydex.wallet.btc_wallet import BitcoinWallet, BitcoinTestnetWallet
                wallet_path = self.config.get_state_dir() / 'wallet'
                btc_wallet = BitcoinWallet(wallet_path)
                btc_testnet_wallet = BitcoinTestnetWallet(wallet_path)
                self.wallets[btc_wallet.get_identifier()] = btc_wallet
                self.wallets[btc_testnet_wallet.get_identifier()] = btc_testnet_wallet
            except Exception as exc:
                self._logger.error("bitcoinlib library cannot be loaded: %s", exc)

        if self.config.get_dummy_wallets_enabled():
            # For debugging purposes, we create dummy wallets
            dummy_wallet1 = DummyWallet1()
            self.wallets[dummy_wallet1.get_identifier()] = dummy_wallet1

            dummy_wallet2 = DummyWallet2()
            self.wallets[dummy_wallet2.get_identifier()] = dummy_wallet2

        if self.config.get_watch_folder_enabled():
            self.readable_status = STATE_START_WATCH_FOLDER
            self.watch_folder = WatchFolder(self)
            self.watch_folder.start()

        if self.config.get_resource_monitor_enabled():
            self.resource_monitor = ResourceMonitor(self)
            self.resource_monitor.start()

        if self.config.get_version_checker_enabled():
            self.version_check_manager = VersionCheckManager(self)
            self.version_check_manager.start()

        if self.config.get_ipv8_enabled() and self.config.get_trustchain_enabled():
            self.payout_manager = PayoutManager(self.trustchain_community, self.dht_community)

        if self.config.get_credit_mining_enabled():
            self.readable_status = STATE_START_CREDIT_MINING
            from tribler_core.modules.credit_mining.credit_mining_manager import CreditMiningManager
            self.credit_mining_manager = CreditMiningManager(self)

        # GigaChannel Manager should be started *after* resuming the downloads,
        # because it depends on the states of torrent downloads
        if self.config.get_chant_enabled() and self.config.get_chant_manager_enabled()\
                and self.config.get_libtorrent_enabled:
            self.gigachannel_manager = GigaChannelManager(self)
            self.gigachannel_manager.start()

        if self.config.get_bootstrap_enabled():
            self.register_task('bootstrap_download', self.start_bootstrap_download)

        self.notifier.notify(NTFY.TRIBLER_STARTED)

    async def shutdown(self):
        """
        Checkpoints the session and closes it, stopping the download engine.
        This method has to be called from the reactor thread.
        """

        # Indicates we are shutting down core. With this environment variable set
        # to 'TRUE', RESTManager will no longer accepts any new requests.
        os.environ['TRIBLER_SHUTTING_DOWN'] = "TRUE"

        if self.ltmgr:
            self.ltmgr.stop_download_states_callback()

        await self.shutdown_task_manager()

        self.shutdownstarttime = timemod.time()
        if self.credit_mining_manager:
            self.notify_shutdown_state("Shutting down Credit Mining...")
            await self.credit_mining_manager.shutdown()
        self.credit_mining_manager = None

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

        self.tracker_manager = None

        if self.tunnel_community and self.trustchain_community:
            # We unload these overlays manually since the TrustChain has to be unloaded after the tunnel overlay.
            tunnel_community = self.tunnel_community
            self.tunnel_community = None
            self.notify_shutdown_state("Unloading Tunnel Community...")
            await self.ipv8.unload_overlay(tunnel_community)
            trustchain_community = self.trustchain_community
            self.trustchain_community = None
            self.notify_shutdown_state("Shutting down TrustChain Community...")
            await self.ipv8.unload_overlay(trustchain_community)

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

        self.notify_shutdown_state("Saving configuration...")
        self.config.write()

        if self.bootstrap:
            await self.bootstrap.shutdown()
        self.bootstrap = None

        if self.ltmgr:
            await self.ltmgr.shutdown()
        self.ltmgr = None

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
