import logging
import sys
import time
from asyncio import Future, all_tasks, get_event_loop, sleep
from collections import defaultdict
from itertools import permutations
from traceback import print_exception
from typing import List

from asynctest import Mock

from ipv8.messaging.anonymization.tunnel import CIRCUIT_TYPE_IP_SEEDER, PEER_FLAG_EXIT_BT
from ipv8.peer import Peer
from ipv8.test.messaging.anonymization import test_community
from ipv8.test.messaging.anonymization.mock import MockDHTProvider
from ipv8.test.mocking.exit_socket import MockTunnelExitSocket
from ipv8.test.mocking.ipv8 import MockIPv8

import pytest

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, dlstatus_strings

# Pylint does not agree with the way pytest handles fixtures.
# pylint: disable=W0613,W0621
from tribler_core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler_core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler_core.components.libtorrent.settings import LibtorrentSettings
from tribler_core.components.libtorrent.torrentdef import TorrentDef
from tribler_core.components.socks_servers.socks5.server import Socks5Server
from tribler_core.components.socks_servers.socks_servers_component import NUM_SOCKS_PROXIES
from tribler_core.components.tunnel.community.tunnel_community import TriblerTunnelCommunity
from tribler_core.components.tunnel.settings import TunnelCommunitySettings
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.utilities.path_util import Path


def crash_on_error():
    def exception_handler(loop, context):
        exc = context.get('exception')
        print_exception(type(exc), exc, exc.__traceback__)
        sys.exit(-1)

    get_event_loop().set_exception_handler(exception_handler)


class ProxyFactory:

    def __init__(self):
        self.comms = []

    async def get(self, exitnode=False, start_lt=False):
        tunn_comm_config = TunnelCommunitySettings()
        comm = await create_tunnel_community(tunn_comm_config, exitnode=exitnode, start_lt=start_lt)
        self.comms.append(comm)
        return comm


@pytest.fixture
async def logger():
    return logging.getLogger("TunnelTests")


@pytest.fixture
async def proxy_factory():
    factory = ProxyFactory()
    yield factory

    for comm in factory.comms:
        if comm.dlmgr:
            await comm.dlmgr.shutdown()
        await comm.unload()
    test_community.global_dht_services = defaultdict(list)  # Reset the global_dht_services variable


@pytest.fixture
async def hidden_seeder_comm(proxy_factory, video_tdef):
    # Also load the tunnel community in the seeder session
    comm = await proxy_factory.get(start_lt=True)
    comm.build_tunnels(1)

    dscfg_seed = DownloadConfig()
    dscfg_seed.set_dest_dir(TESTS_DATA_DIR)
    dscfg_seed.set_hops(1)
    upload = comm.dlmgr.start_download(tdef=video_tdef, config=dscfg_seed)

    def seeder_state_callback(ds):
        """
        The callback of the seeder download. For now, this only logs the state of the download that's seeder and is
        useful for debugging purposes.
        """
        comm.monitor_downloads([ds])
        d = ds.get_download()
        print(f"seeder: {repr(d.get_def().get_name())} {dlstatus_strings[ds.get_status()]} {ds.get_progress()}")
        return 2

    upload.set_state_callback(seeder_state_callback)

    await upload.wait_for_status(DLSTATUS_SEEDING)
    return comm


async def create_tunnel_community(comm_config: TunnelCommunitySettings = None,
                                  exitnode=False,
                                  start_lt=False) -> TriblerTunnelCommunity:
    """
    Load the tunnel community in a given session. We are using our own tunnel community here instead of the one
    used in Tribler.
    """
    socks_servers = []
    socks_ports = []
    # Start the SOCKS5 servers
    if start_lt:
        for _ in range(NUM_SOCKS_PROXIES):
            socks_server = Socks5Server()
            socks_servers.append(socks_server)
            await socks_server.start()
            socks_ports.append(socks_server.port)

    dlmgr = None
    if start_lt:
        # If libtorrent tries to connect to the socks5 servers before they are loaded,
        # it will never recover (on Mac/Linux with Libtorrent >=1.2.0). Therefore, we start
        # libtorrent afterwards.
        dlmgr_settings = LibtorrentSettings()
        dlmgr_settings.dht = False

        dlmgr = DownloadManager(state_dir=Path.mkdtemp(),
                                config=dlmgr_settings,
                                peer_mid=Mock(),
                                socks_listen_ports=socks_ports,
                                notifier=Mock())

    comm_config = comm_config or TunnelCommunitySettings()
    comm_config.exitnode_enabled = exitnode
    mock_ipv8 = MockIPv8("curve25519",
                         TriblerTunnelCommunity,
                         settings={"max_circuits": 1},
                         config=comm_config,
                         socks_servers=socks_servers,
                         dlmgr=dlmgr)
    if start_lt:
        dlmgr.peer_mid = mock_ipv8.my_peer.mid
        dlmgr.initialize()
        dlmgr.is_shutdown_ready = lambda: True
    tunnel_community = mock_ipv8.overlay

    if exitnode:
        mock_ipv8.overlay.settings.peer_flags.add(PEER_FLAG_EXIT_BT)
    mock_ipv8.overlay.dht_provider = MockDHTProvider(
        Peer(mock_ipv8.overlay.my_peer.key, mock_ipv8.overlay.my_estimated_wan))
    mock_ipv8.overlay.settings.remove_tunnel_delay = 0

    return tunnel_community


def start_anon_download(tunnel_community: TriblerTunnelCommunity,
                        seeder_port,
                        tdef: TorrentDef,
                        hops=1):
    """
    Start an anonymous download in the main Tribler session.
    """
    download_manager = tunnel_community.dlmgr
    dscfg = DownloadConfig()
    dscfg.set_dest_dir(download_manager.state_dir)
    dscfg.set_hops(hops)
    download = download_manager.start_download(tdef=tdef, config=dscfg)
    tunnel_community.bittorrent_peers[download] = [("127.0.0.1", seeder_port)]
    return download


async def introduce_peers(communities: List[TriblerTunnelCommunity]):
    for i, j in permutations(communities, 2):
        i.walk_to(j.endpoint.wan_address)

    await deliver_messages()


async def deliver_messages(timeout=.1):
    """
    Allow peers to communicate.
    The strategy is as follows:
     1. Measure the amount of tasks
     2. After 10 milliseconds, check if we are below 2 twice in a row
     3. If not, go back to handling calls (step 2) or return, if the timeout has been reached
    :param timeout: the maximum time to wait for messages to be delivered
    """
    rtime = 0
    probable_exit = False
    while rtime < timeout:
        await sleep(.01)
        rtime += .01
        if len(all_tasks()) < 2:
            if probable_exit:
                break
            probable_exit = True
        else:
            probable_exit = False


async def create_nodes(proxy_factory, num_relays=1, num_exitnodes=1):
    relays = []
    exit_nodes = []
    for _ in range(num_relays):
        relay = await proxy_factory.get()
        relays.append(relay)
    for _ in range(num_exitnodes):
        exit_node = await proxy_factory.get(exitnode=True)
        exit_nodes.append(exit_node)
    return relays, exit_nodes


@pytest.fixture
async def my_comm():
    my_comm = await create_tunnel_community(exitnode=False, start_lt=True)

    yield my_comm

    await my_comm.dlmgr.shutdown()
    await my_comm.unload()


@pytest.mark.tunneltest
@pytest.mark.asyncio
@pytest.mark.timeout(40)
async def test_anon_download(proxy_factory, video_seeder: DownloadManager, video_tdef: TorrentDef, logger,
                             my_comm: TriblerTunnelCommunity):
    """
    Testing whether an anonymous download over our tunnels works
    """

    crash_on_error()

    relays, exit_nodes = await create_nodes(proxy_factory)
    await introduce_peers([my_comm] + relays + exit_nodes)
    dlmgr = my_comm.dlmgr

    download = start_anon_download(my_comm, video_seeder.libtorrent_port, video_tdef)
    await download.wait_for_status(DLSTATUS_DOWNLOADING)
    dlmgr.set_download_states_callback(dlmgr.sesscb_states_callback, interval=.1)

    while not my_comm.find_circuits():
        num_verified_peers = len(my_comm.network.verified_peers)
        logger.warning("No circuits found - checking again later (verified peers: %d)", num_verified_peers)
        await sleep(.5)
    await sleep(.6)
    assert my_comm.find_circuits()[0].bytes_up > 0
    assert my_comm.find_circuits()[0].bytes_down > 0


@pytest.mark.tunneltest
@pytest.mark.asyncio
@pytest.mark.timeout(40)
async def test_hidden_services(proxy_factory, hidden_seeder_comm, video_tdef, logger):
    """
    Test the hidden services overlay by constructing an end-to-end circuit and downloading a torrent over it
    """

    crash_on_error()

    leecher_comm = await proxy_factory.get(exitnode=False, start_lt=True)

    hidden_seeder_comm.build_tunnels(1)

    relays, exit_nodes = await create_nodes(proxy_factory, num_relays=3, num_exitnodes=2)
    await introduce_peers([leecher_comm, hidden_seeder_comm] + relays + exit_nodes)
    await deliver_messages(timeout=1)

    for comm in [leecher_comm, hidden_seeder_comm] + relays + exit_nodes:
        assert len(comm.get_peers()) == 6

    progress = Future()

    def download_state_callback(ds):
        leecher_comm.monitor_downloads([ds])
        logger.info("Time: %s, status: %s, progress: %s", time.time(), ds.get_status(), ds.get_progress())
        if ds.get_progress():
            progress.set_result(None)
        return 2

    leecher_comm.build_tunnels(1)

    class MockExitDict(dict):
        def __getitem__(self, key):
            value = super().__getitem__(key)
            return value if isinstance(value, MockTunnelExitSocket) else MockTunnelExitSocket(value)

    for e in exit_nodes:
        e.exit_sockets = MockExitDict(e.exit_sockets)

    download = start_anon_download(leecher_comm, hidden_seeder_comm.dlmgr.libtorrent_port, video_tdef, hops=1)
    download.set_state_callback(download_state_callback)
    await progress
