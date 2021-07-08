"""
Author(s): Vadim Bulavintsev
"""
import logging
import os
import sys
from asyncio import Event, get_event_loop
from dataclasses import dataclass, field
from typing import Optional, List

import tribler_core.utilities.permid as permid_module
from ipv8.peer import Peer
from ipv8.taskmanager import TaskManager
from ipv8_service import IPv8
from tribler_common.network_utils import NetworkUtils
from tribler_common.sentry_reporter.sentry_reporter import SentryReporter
from tribler_common.simpledefs import (
    NTFY,
    STATEDIR_CHANNELS_DIR,
    STATEDIR_DB_DIR,
    STATE_LOAD_CHECKPOINTS,
    STATE_READABLE_STARTED,
    STATE_START_API,
    STATE_START_LIBTORRENT,
    STATE_START_TORRENT_CHECKER,
    STATE_START_WATCH_FOLDER,
    STATE_UPGRADING_READABLE,
)
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.metadata_store.utils import generate_test_channels
from tribler_core.modules.settings import Ipv8Settings
from tribler_core.notifier import Notifier
from tribler_core.utilities.crypto_patcher import patch_crypto_be_discovery
from tribler_core.utilities.install_dir import get_lib_path
from tribler_core.utilities.unicode import hexlify


@dataclass
class Mediator:
    config: TriblerConfig
    notifier: Optional[Notifier] = None
    ipv8: Optional[IPv8] = None
    metadata_store = None
    download_manager = None
    torrent_checker = None

    dictionary: dict = field(default_factory=dict)


@dataclass
class Factory:
    create_class: Optional[type] = None
    kwargs: dict = field(default_factory=dict)


async def create_ipv8(
        config: Ipv8Settings,
        state_dir,
        ipv8_tasks,
        communities_cls: List[Factory],
        mediator: Mediator,
        trustchain_keypair,
        core_test_mode=False):
    from ipv8.configuration import ConfigBuilder
    from ipv8.messaging.interfaces.dispatcher.endpoint import DispatcherEndpoint
    port = config.port
    address = config.address
    logger = logging.getLogger("Session")
    logger.info('Starting ipv8')
    logger.info(f'Port: {port}. Address: {address}')
    ipv8_config_builder = (ConfigBuilder()
                           .set_port(port)
                           .set_address(address)
                           .clear_overlays()
                           .clear_keys()  # We load the keys ourselves
                           .set_working_directory(str(state_dir))
                           .set_walker_interval(config.walk_interval))

    if core_test_mode:
        endpoint = DispatcherEndpoint([])
    else:
        # IPv8 includes IPv6 support by default.
        # We only load IPv4 to not kill all Tribler overlays (currently, it would instantly crash all users).
        # If you want to test IPv6 in Tribler you can set ``endpoint = None`` here.
        endpoint = DispatcherEndpoint(["UDPIPv4"], UDPIPv4={'port': port,
                                                            'ip': address})
    ipv8 = IPv8(ipv8_config_builder.finalize(),
                enable_statistics=config.statistics and not core_test_mode,
                endpoint_override=endpoint)
    await ipv8.start()

    bootstrapper = None
    if config.bootstrap_override:
        address, port = config.bootstrap_override.split(':')
        from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
        bootstrapper = DispersyBootstrapper(ip_addresses=[(address, int(port))], dns_addresses=[])

    peer = Peer(trustchain_keypair)
    mediator.ipv8 = ipv8
    for community_cls in communities_cls:
        community = community_cls.create_class(peer, ipv8.endpoint, ipv8.network, mediator=mediator, **community_cls.kwargs)
        community.fill_mediator(mediator)

        for strategy in community.strategies:
            ipv8.strategies.append((strategy.create_class(community), strategy.target_peers))

        if bootstrapper:
            community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)

    if config.statistics and not core_test_mode:
        # Enable gathering IPv8 statistics
        for overlay in ipv8.overlays:
            ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

    if config.walk_scaling_enabled and not core_test_mode:
        from tribler_core.modules.ipv8_health_monitor import IPv8Monitor
        IPv8Monitor(ipv8,
                    config.walk_interval,
                    config.walk_scaling_upper_limit).start(ipv8_tasks)
    return ipv8


def create_state_directory_structure(state_dir):
    """Create directory structure of the state directory."""

    def create_dir(path):
        if not path.is_dir():
            os.makedirs(path)

    def create_in_state_dir(path):
        create_dir(state_dir / path)

    create_dir(state_dir)
    create_in_state_dir(STATEDIR_DB_DIR)
    create_in_state_dir(STATEDIR_CHANNELS_DIR)


def init_keypair(state_dir, keypair_filename):
    """
    Set parameters that depend on state_dir.
    """
    keypair_path = state_dir / keypair_filename
    if keypair_path.exists():
        return permid_module.read_keypair_trustchain(keypair_path)
    else:
        trustchain_keypair = permid_module.generate_keypair_trustchain()

        # Save keypair
        trustchain_pubfilename = state_dir / 'ecpub_multichain.pem'
        permid_module.save_keypair_trustchain(trustchain_keypair, keypair_path)
        permid_module.save_pub_key_trustchain(trustchain_keypair, trustchain_pubfilename)
        return trustchain_keypair


async def core_session(
        config: TriblerConfig,
        communities_cls: List[Factory],
        components_cls: List[Factory],
        shutdown_event=Event(),
        notifier=Notifier()
):

    mediator = Mediator(config=config)
    # In test mode, the Core does not communicate with the external world and the state dir is read-only
    logger = logging.getLogger("Session")

    from tribler_core.exception_handler import CoreExceptionHandler
    exception_handler = CoreExceptionHandler(logger, config=config.error_handling)
    get_event_loop().set_exception_handler(exception_handler.unhandled_error_observer)
    patch_crypto_be_discovery()

    mediator.notifier = notifier

    logger.info("Session is using state directory: %s", config.state_dir)
    create_state_directory_structure(config.state_dir)
    keypair_filename = config.trustchain.ec_keypair_filename if not config.general.testnet else config.trustchain.testnet_keypair_filename
    trustchain_keypair = init_keypair(config.state_dir, keypair_filename)

    # we have to represent `user_id` as a string to make it equal to the
    # `user_id` on the GUI side
    user_id_str = hexlify(trustchain_keypair.key.pk).encode('utf-8')
    SentryReporter.set_user(user_id_str)

    # Start the REST API before the upgrader since we want to send interesting upgrader events over the socket
    if config.api.http_enabled or config.api.https_enabled:
        from tribler_core.restapi.root_endpoint import RootEndpoint
        from tribler_core.restapi.rest_manager import ApiKeyMiddleware, error_middleware
        root_endpoint = RootEndpoint(config, middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])

        from tribler_core.restapi.rest_manager import RESTManager
        api_manager = RESTManager(config=config.api, root_endpoint=root_endpoint)
        # Unfortunately, AIOHTTP endpoints cannot be added after the app has been started.
        # On the other hand, we have to start the state endpoint from the beginning, to
        # communicate with the upgrader. Thus, we start the endpoints immediately and
        # then gradually connect them to their respective backends during the core start process.
        await api_manager.start()
        api_manager.get_endpoint('settings').tribler_config = config

        state_endpoint = api_manager.get_endpoint('state')
        state_endpoint.connect_notifier(notifier)
        state_endpoint.readable_status = STATE_START_API

        exception_handler.events_endpoint = api_manager.get_endpoint('events')
        exception_handler.state_endpoint = state_endpoint

        api_manager.get_endpoint('events').connect_notifier(notifier)
        api_manager.get_endpoint('shutdown').connect_shutdown_callback(shutdown_event.set)

        downloads_endpoint = api_manager.get_endpoint('downloads')

    if config.upgrader_enabled and not config.core_test_mode:
        from tribler_core.upgrade.upgrade import TriblerUpgrader
        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)
        upgrader = TriblerUpgrader(
            state_dir=config.state_dir,
            channels_dir=channels_dir,
            trustchain_keypair=trustchain_keypair,
            notifier=notifier)
        state_endpoint.readable_status = STATE_UPGRADING_READABLE

        api_manager.get_endpoint('upgrader').upgrader = upgrader
        await upgrader.run()

    # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
    # certificates provided by the system trust store.
    if sys.platform == 'darwin':
        os.environ['SSL_CERT_FILE'] = str(get_lib_path() / 'root_certs_mac.pem')

    if config.chant.enabled:
        from tribler_core.modules.metadata_store.store import MetadataStore
        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)
        chant_testnet = config.general.testnet or config.chant.testnet
        metadata_db_name = 'metadata.db' if not chant_testnet else 'metadata_testnet.db'
        database_path = config.state_dir / 'sqlite' / metadata_db_name
        metadata_store = MetadataStore(
            database_path, channels_dir, trustchain_keypair,
            notifier=notifier,
            disable_sync=config.core_test_mode)

        api_manager.get_endpoint('search').mds = metadata_store

        if config.core_test_mode:
            generate_test_channels(metadata_store)

        mediator.metadata_store = metadata_store

    ipv8_tasks = TaskManager()

    if config.tunnel_community.enabled:
        anon_proxy_ports = config.tunnel_community.socks5_listen_ports
        if not anon_proxy_ports:
            anon_proxy_ports = [NetworkUtils().get_random_free_port() for _ in range(5)]
            config.tunnel_community.socks5_listen_ports = anon_proxy_ports
        anon_proxy_settings = ("127.0.0.1", anon_proxy_ports)
        logger.info(f'Set anon proxy settings: {anon_proxy_settings}')

        from tribler_core.modules.libtorrent.download_manager import DownloadManager
        DownloadManager.set_anon_proxy_settings(config.libtorrent, 2, anon_proxy_settings)

    # IPv8
    if config.ipv8.enabled:
        ipv8 = await create_ipv8(
            state_dir=config.state_dir,
            config=config.ipv8,
            ipv8_tasks=ipv8_tasks,
            communities_cls=communities_cls,
            mediator=mediator,
            trustchain_keypair=trustchain_keypair,
            core_test_mode=config.core_test_mode)

        if api_manager:
            from ipv8.messaging.anonymization.community import TunnelCommunity
            api_manager.get_endpoint('ipv8').initialize(ipv8)
            await ipv8.get_overlay(TunnelCommunity).wait_for_socks_servers()
    if config.libtorrent.enabled:
        state_endpoint.readable_status = STATE_START_LIBTORRENT
        from tribler_core.modules.libtorrent.download_manager import DownloadManager
        download_manager = DownloadManager(config=config.libtorrent,
                                           state_dir=config.state_dir,
                                           notifier=notifier,
                                           peer_mid=trustchain_keypair.key_to_hash(),
                                           download_defaults=config.download_defaults,
                                           payout_manager=None,
                                           tunnel_community=ipv8.get_overlay(TunnelCommunity),
                                           bootstrap_infohash=config.bootstrap.infohash,
                                           dummy_mode=config.core_test_mode)

        mediator.download_manager = download_manager

        download_manager.initialize()
        state_endpoint.readable_status = STATE_LOAD_CHECKPOINTS
        await download_manager.load_checkpoints()

        if api_manager:
            api_manager.get_endpoint('createtorrent').download_manager = download_manager
            api_manager.get_endpoint('libtorrent').download_manager = download_manager
            api_manager.get_endpoint('torrentinfo').download_manager = download_manager

        if config.core_test_mode:
            await download_manager.start_download_from_uri(
                "magnet:?xt=urn:btih:0000000000000000000000000000000000000000")

    # Note that currently we should only start libtorrent after the SOCKS5 servers have been started

    if api_manager and download_manager:
        api_manager.get_endpoint('settings').download_manager = download_manager

    state_endpoint.readable_status = STATE_READABLE_STARTED

    from tribler_core.modules.tracker_manager import TrackerManager
    tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store)

    # Start torrent checker before Popularity community is loaded
    if config.torrent_checking.enabled and not config.core_test_mode:
        from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
        state_endpoint.readable_status = STATE_START_TORRENT_CHECKER
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=download_manager,
                                         notifier=notifier,
                                         tracker_manager=tracker_manager,
                                         metadata_store=metadata_store)
        mediator.torrent_checker = torrent_checker
        await torrent_checker.initialize()

    if api_manager:
        from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity
        api_manager.get_endpoint('trustview').bandwidth_db = ipv8.get_overlay(BandwidthAccountingCommunity).database

    if config.ipv8.enabled:
        from tribler_core.modules.payout_manager import PayoutManager
        from ipv8.dht.community import DHTCommunity
        payout_manager = PayoutManager(ipv8.get_overlay(BandwidthAccountingCommunity), ipv8.get_overlay(DHTCommunity))
        download_manager.payout_manager = payout_manager

        if config.core_test_mode:
            from ipv8.messaging.interfaces.udp.endpoint import UDPv4Address
            from ipv8.dht.routing import RoutingTable
            ipv8.get_overlay(DHTCommunity).routing_tables[UDPv4Address] = RoutingTable('\x00' * 20)

    if api_manager:
        api_manager.get_endpoint('metadata').torrent_checker = torrent_checker
        api_manager.get_endpoint('metadata').mds = metadata_store

        from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
        api_manager.get_endpoint('remote_query').mds = metadata_store
        api_manager.get_endpoint('remote_query').gigachannel_community = ipv8.get_overlay(GigaChannelCommunity)

    watch_folder = None
    if config.watch_folder.enabled:
        from tribler_core.modules.watch_folder import WatchFolder
        state_endpoint.readable_status = STATE_START_WATCH_FOLDER
        watch_folder_path = config.watch_folder.get_path_as_absolute('directory', config.state_dir)
        watch_folder = WatchFolder(watch_folder_path=watch_folder_path,
                                   download_manager=download_manager,
                                   notifier=notifier)
        watch_folder.start()

    if config.resource_monitor.enabled and not config.core_test_mode:
        from tribler_core.modules.resource_monitor.core import CoreResourceMonitor
        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        resource_monitor = CoreResourceMonitor(state_dir=config.state_dir,
                                               log_dir=log_dir,
                                               config=config.resource_monitor,
                                               notifier=notifier)
        resource_monitor.start()

    if config.general.version_checker_enabled and not config.core_test_mode:
        from tribler_core.modules.versioncheck_manager import VersionCheckManager
        version_check_manager = VersionCheckManager(notifier=notifier)
        version_check_manager.start()

    # GigaChannel Manager should be started *after* resuming the downloads,
    # because it depends on the states of torrent downloads
    if config.chant.enabled and config.chant.manager_enabled and config.libtorrent.enabled:
        from tribler_core.modules.metadata_store.gigachannel_manager import GigaChannelManager
        gigachannel_manager = GigaChannelManager(notifier=notifier,
                                                 metadata_store=metadata_store,
                                                 download_manager=download_manager)
        if not config.core_test_mode:
            gigachannel_manager.start()

    if downloads_endpoint:
        downloads_endpoint.download_manager = download_manager
        downloads_endpoint.tunnel_community = ipv8.get_overlay(TunnelCommunity)
        downloads_endpoint.mds = metadata_store

    channels_endpoint = api_manager.get_endpoint('channels')
    channels_endpoint.mds = metadata_store
    channels_endpoint.download_manager = download_manager
    channels_endpoint.gigachannel_manager = gigachannel_manager
    channels_endpoint.gigachannel_community = ipv8.get_overlay(GigaChannelCommunity)

    collections_endpoint = api_manager.get_endpoint('collections')
    collections_endpoint.mds = metadata_store
    collections_endpoint.download_manager = download_manager
    collections_endpoint.gigachannel_manager = gigachannel_manager
    collections_endpoint.gigachannel_community = ipv8.get_overlay(GigaChannelCommunity)

    notifier.notify(NTFY.TRIBLER_STARTED, trustchain_keypair.key.pk)

    # If there is a config error, report to the user via GUI notifier
    if config.error:
        notifier.notify(NTFY.REPORT_CONFIG_ERROR, config.error)

    # SHUTDOWN
    await shutdown_event.wait()

    # Indicates we are shutting down core. With this environment variable set
    # to 'TRUE', RESTManager will no longer accepts any new requests.
    os.environ['TRIBLER_SHUTTING_DOWN'] = "TRUE"

    if download_manager:
        download_manager.stop_download_states_callback()

    if torrent_checker:
        notifier.notify_shutdown_state("Shutting down Torrent Checker...")
        await torrent_checker.shutdown()

    if gigachannel_manager:
        notifier.notify_shutdown_state("Shutting down Gigachannel Manager...")
        await gigachannel_manager.shutdown()

    if version_check_manager:
        notifier.notify_shutdown_state("Shutting down Version Checker...")
        await version_check_manager.stop()

    if resource_monitor:
        notifier.notify_shutdown_state("Shutting down Resource Monitor...")
        await resource_monitor.stop()

    if ipv8.get_overlay(TunnelCommunity) and ipv8.get_overlay(BandwidthAccountingCommunity):
        # We unload these overlays manually since the TrustChain has to be unloaded after the tunnel overlay.
        notifier.notify_shutdown_state("Unloading Tunnel Community...")
        await ipv8.unload_overlay(ipv8.get_overlay(TunnelCommunity))
        notifier.notify_shutdown_state("Shutting down Bandwidth Community...")
        await ipv8.unload_overlay(ipv8.get_overlay(BandwidthAccountingCommunity))

    if ipv8:
        notifier.notify_shutdown_state("Shutting down IPv8...")
        await ipv8.stop(stop_loop=False)
        await ipv8_tasks.shutdown_task_manager()

    if payout_manager:
        await payout_manager.shutdown()

    if watch_folder:
        notifier.notify_shutdown_state("Shutting down Watch Folder...")
        await watch_folder.stop()

    if not config.core_test_mode:
        notifier.notify_shutdown_state("Saving configuration...")
        config.write()

    if download_manager:
        await download_manager.shutdown()

    if metadata_store:
        notifier.notify_shutdown_state("Shutting down Metadata Store...")
        metadata_store.shutdown()

    # We close the API manager as late as possible during shutdown.
    if api_manager:
        notifier.notify_shutdown_state("Shutting down API Manager...")
        await api_manager.stop()
