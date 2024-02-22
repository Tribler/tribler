import asyncio
import logging
import sys
import time
from asyncio import all_tasks, get_event_loop, sleep
from collections import defaultdict
from itertools import permutations
from typing import List, Optional, Tuple
from unittest.mock import MagicMock, AsyncMock

import pytest
from _pytest.tmpdir import TempPathFactory
from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT
from ipv8.peer import Peer
from ipv8.test.messaging.anonymization import test_community
from ipv8.test.messaging.anonymization.mock import MockDHTProvider
from ipv8.test.mocking.exit_socket import MockTunnelExitSocket
from tribler.core.components.ipv8.adapters_tests import TriblerMockIPv8

# Pylint does not agree with the way pytest handles fixtures.
# pylint: disable=W0613,W0621
from tribler.core.components.libtorrent.download_manager.download import Download
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.settings import LibtorrentSettings
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.socks_servers.socks5.server import Socks5Server
from tribler.core.components.socks_servers.socks_servers_component import NUM_SOCKS_PROXIES
from tribler.core.components.tunnel.community.tunnel_community import TriblerTunnelCommunity
from tribler.core.components.tunnel.settings import TunnelCommunitySettings
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.utilities.simpledefs import DownloadStatus

logger = logging.getLogger("TunnelTests")


@pytest.fixture
def crash_on_error():
    def exception_handler(_, context):
        logger.exception(context.get('exception'))
        sys.exit(-1)

    get_event_loop().set_exception_handler(exception_handler)


class ProxyFactory:
    def __init__(self, temp_path_factory):
        self.communities = []
        self.temp_path_factory = temp_path_factory

    async def get(self, exitnode=False, start_lt=False) -> TriblerTunnelCommunity:
        tunnel_community_config = TunnelCommunitySettings()
        community = await create_tunnel_community(self.temp_path_factory, tunnel_community_config,
                                                  exit_node_enable=exitnode,
                                                  start_lt=start_lt)
        self.communities.append(community)
        return community


@pytest.fixture
async def proxy_factory(tmp_path_factory: TempPathFactory):
    factory = ProxyFactory(tmp_path_factory)
    yield factory

    for community in factory.communities:
        if community.download_manager:
            await community.download_manager.shutdown()
        await community.unload()
    test_community.global_dht_services = defaultdict(list)  # Reset the global_dht_services variable


@pytest.fixture
async def hidden_seeder_comm(proxy_factory: ProxyFactory, video_tdef: TorrentDef) -> TriblerTunnelCommunity:
    # Also load the tunnel community in the seeder session
    community = await proxy_factory.get(start_lt=True)
    community.build_tunnels(1)

    download_config = DownloadConfig()
    download_config.set_dest_dir(TESTS_DATA_DIR)
    download_config.set_hops(1)
    upload = await community.download_manager.start_download(tdef=video_tdef, config=download_config)

    def seeder_state_callback(download_state):
        """
        The callback of the seeder download. For now, this only logs the state of the download that's seeder and is
        useful for debugging purposes.
        """
        community.monitor_downloads([download_state])
        download = download_state.get_download()
        status = download_state.get_status().name
        logger.info(f"seeder: {repr(download.get_def().get_name())} {status} {download_state.get_progress()}")
        return 2

    upload.set_state_callback(seeder_state_callback)

    await upload.wait_for_status(DownloadStatus.SEEDING)
    return community


async def create_tunnel_community(temp_path_factory: TempPathFactory,
                                  config: Optional[TunnelCommunitySettings] = None,
                                  exit_node_enable: bool = False,
                                  start_lt: bool = False) -> TriblerTunnelCommunity:
    """
    Load the tunnel community in a given session. We are using our own tunnel community here instead of the one
    used in Tribler.
    """
    socks_servers = []
    socks_ports = []
    # Start the SOCKS5 servers
    if start_lt:
        for hops in range(NUM_SOCKS_PROXIES):
            socks_server = Socks5Server(hops+1)
            socks_servers.append(socks_server)
            await socks_server.start()
            socks_ports.append(socks_server.port)

    download_manager = None
    if start_lt:
        # If libtorrent tries to connect to the socks5 servers before they are loaded,
        # it will never recover (on Mac/Linux with Libtorrent >=1.2.0). Therefore, we start
        # libtorrent afterwards.
        download_manager_settings = LibtorrentSettings()
        download_manager_settings.dht = False

        download_manager = DownloadManager(state_dir=temp_path_factory.mktemp('state_dir'),
                                           config=download_manager_settings,
                                           peer_mid=MagicMock(),
                                           socks_listen_ports=socks_ports,
                                           notifier=MagicMock())
        download_manager.metadata_tmpdir = temp_path_factory.mktemp('metadata_tmpdir')

    config = config or TunnelCommunitySettings()
    config.exitnode_enabled = exit_node_enable

    ipv8 = TriblerMockIPv8("curve25519",
                           TriblerTunnelCommunity,
                           config=config,
                           socks_servers=socks_servers,
                           dlmgr=download_manager)
    if start_lt:
        download_manager.peer_mid = ipv8.my_peer.mid
        download_manager.initialize()
        download_manager.is_shutdown_ready = lambda: True
    tunnel_community = ipv8.overlay
    tunnel_community.should_join_circuit = AsyncMock(return_value=True)
    tunnel_community.settings.max_circuits = 1

    if exit_node_enable:
        ipv8.overlay.settings.peer_flags.add(PEER_FLAG_EXIT_BT)
    ipv8.overlay.dht_provider = MockDHTProvider(Peer(ipv8.overlay.my_peer.key, ipv8.overlay.my_estimated_wan))
    ipv8.overlay.settings.remove_tunnel_delay = 0
    ipv8.overlay.exit_sockets = MockExitDict(ipv8.overlay.crypto_endpoint.exit_sockets)
    ipv8.overlay.crypto_endpoint.exit_sockets = ipv8.overlay.exit_sockets

    return tunnel_community


class MockExitDict(dict):
    def __getitem__(self, key):
        value = super().__getitem__(key)
        return value if isinstance(value, MockTunnelExitSocket) else MockTunnelExitSocket(value)


async def start_anon_download(tunnel_community: TriblerTunnelCommunity,
                        seeder_port: int,
                        torrent_def: TorrentDef,
                        hops: int = 1) -> Download:
    """
    Start an anonymous download in the main Tribler session.
    """
    download_manager = tunnel_community.download_manager
    config = DownloadConfig()
    config.set_dest_dir(download_manager.state_dir)
    config.set_hops(hops)
    download = await download_manager.start_download(tdef=torrent_def, config=config)
    tunnel_community.bittorrent_peers[download] = [("127.0.0.1", seeder_port)]
    return download


async def introduce_peers(communities: List[TriblerTunnelCommunity]):
    for community1, community2 in permutations(communities, 2):
        community1.walk_to(community2.endpoint.wan_address)

    await deliver_messages()


async def deliver_messages(timeout: float = .1):
    """
    Allow peers to communicate.
    The strategy is as follows:
     1. Measure the amount of tasks
     2. After 10 milliseconds, check if we are below 2 twice in a row
     3. If not, go back to handling calls (step 2) or return, if the timeout has been reached
    :param timeout: the maximum time to wait for messages to be delivered
    """
    remaining_time = 0
    probable_exit = False
    while remaining_time < timeout:
        await sleep(.01)
        remaining_time += .01
        if len(all_tasks()) < 2:
            if probable_exit:
                break
            probable_exit = True
        else:
            probable_exit = False


CreateNodesResult = Tuple[List[TriblerTunnelCommunity], List[TriblerTunnelCommunity]]


async def create_nodes(proxy_factory: ProxyFactory, num_relays: int = 1, num_exit_nodes: int = 1) -> CreateNodesResult:
    relays = []
    exit_nodes = []
    for _ in range(num_relays):
        relay = await proxy_factory.get()
        relays.append(relay)
    for _ in range(num_exit_nodes):
        exit_node = await proxy_factory.get(exitnode=True)
        exit_nodes.append(exit_node)
    return relays, exit_nodes


@pytest.fixture
async def tunnel_community(tmp_path_factory: TempPathFactory):
    community = await create_tunnel_community(tmp_path_factory, exit_node_enable=False, start_lt=True)

    yield community

    await community.download_manager.shutdown()
    await community.unload()


@pytest.mark.tunneltest
async def test_anon_download(proxy_factory: ProxyFactory, video_seeder: DownloadManager, video_tdef: TorrentDef,
                             tunnel_community: TriblerTunnelCommunity, crash_on_error):
    """
    Testing whether an anonymous download over our tunnels works
    """
    relays, exit_nodes = await create_nodes(proxy_factory)
    await introduce_peers([tunnel_community] + relays + exit_nodes)
    download_manager = tunnel_community.download_manager

    download = await start_anon_download(tunnel_community, video_seeder.libtorrent_port, video_tdef)
    await download.wait_for_status(DownloadStatus.DOWNLOADING)
    download_manager.set_download_states_callback(download_manager.sesscb_states_callback, interval=.1)

    while not tunnel_community.find_circuits():
        num_verified_peers = len(tunnel_community.network.verified_peers)
        logger.warning("No circuits found - checking again later (verified peers: %d)", num_verified_peers)
        await sleep(.5)
    await sleep(.6)
    assert tunnel_community.find_circuits()[0].bytes_up > 0
    assert tunnel_community.find_circuits()[0].bytes_down > 0


@pytest.mark.tunneltest
async def test_hidden_services(proxy_factory: ProxyFactory, hidden_seeder_comm: TriblerTunnelCommunity,
                               video_tdef: TorrentDef, crash_on_error):
    """
    Test the hidden services overlay by constructing an end-to-end circuit and downloading a torrent over it
    """
    leecher_community = await proxy_factory.get(exitnode=False, start_lt=True)
    # We don't want libtorrent peers interfering with the download. This is merely to avoid
    # getting "unregistered address" warnings in the logs and should not affect the outcome.
    leecher_community.readd_bittorrent_peers = MagicMock()  # type: ignore

    hidden_seeder_comm.build_tunnels(hops=1)

    relays, exit_nodes = await create_nodes(proxy_factory, num_relays=3, num_exit_nodes=2)
    await introduce_peers([leecher_community, hidden_seeder_comm] + relays + exit_nodes)
    await deliver_messages(timeout=1)

    for community in [leecher_community, hidden_seeder_comm] + relays + exit_nodes:
        assert len(community.get_peers()) == 6

    download_finished = asyncio.Event()

    def download_state_callback(state):
        logger.info(f"Time: {time.time()}, status: {state.get_status()}, progress: {state.get_progress()}")
        if state.get_progress():
            download_finished.set()
        return 2

    leecher_community.build_tunnels(hops=1)

    download = await start_anon_download(leecher_community, hidden_seeder_comm.download_manager.libtorrent_port,
                                         video_tdef, hops=1)
    download.set_state_callback(download_state_callback)
    await download_finished.wait()
