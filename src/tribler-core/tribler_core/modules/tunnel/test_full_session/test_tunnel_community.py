import time
from asyncio import Future, all_tasks, sleep
from collections import defaultdict

from ipv8.keyvault.crypto import ECCrypto
from ipv8.messaging.anonymization.tunnel import CIRCUIT_TYPE_IP_SEEDER, PEER_FLAG_EXIT_BT
from ipv8.peer import Peer
from ipv8.peerdiscovery.community import DiscoveryCommunity
from ipv8.peerdiscovery.network import Network
from ipv8.test.messaging.anonymization import test_community
from ipv8.test.messaging.anonymization.test_community import MockDHTProvider

import pytest

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, dlstatus_strings

from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.tunnel.community.triblertunnel_community import TriblerTunnelCommunity
from tribler_core.session import Session
from tribler_core.tests.tools.common import TESTS_DATA_DIR


class ProxyFactory:

    def __init__(self, tribler_config, free_ports_factory):
        self.base_tribler_config = tribler_config
        self.free_ports_factory = free_ports_factory
        self.sessions = []

    async def get(self, exitnode=False):
        config = self.base_tribler_config.copy()
        config.set_ipv8_enabled(True)
        config.set_ipv8_port(-1)
        config.set_trustchain_enabled(False)
        config.set_libtorrent_enabled(False)
        config.set_tunnel_community_socks5_listen_ports(self.free_ports_factory(5))

        session = Session(config)
        session.upgrader_enabled = False
        await session.start()
        self.sessions.append(session)

        await load_tunnel_community_in_session(session, exitnode=exitnode)

        return session


@pytest.fixture
async def proxy_factory(request, tribler_config, free_ports):
    factory = ProxyFactory(tribler_config, free_ports)
    yield factory

    for session in factory.sessions:
        await session.shutdown()
    test_community.global_dht_services = defaultdict(list)  # Reset the global_dht_services variable


@pytest.fixture
async def hidden_seeder_session(seed_config, video_tdef):
    seed_config.set_ipv8_port(-1)
    seed_config.set_libtorrent_enabled(False)
    seeder_session = Session(seed_config)
    seeder_session.upgrader_enabled = False
    await seeder_session.start()

    # Also load the tunnel community in the seeder session
    await load_tunnel_community_in_session(seeder_session, start_lt=True)
    seeder_session.tunnel_community.build_tunnels(1)

    dscfg_seed = DownloadConfig()
    dscfg_seed.set_dest_dir(TESTS_DATA_DIR)
    dscfg_seed.set_hops(1)
    upload = seeder_session.dlmgr.start_download(tdef=video_tdef, config=dscfg_seed)

    def seeder_state_callback(ds):
        """
        The callback of the seeder download. For now, this only logs the state of the download that's seeder and is
        useful for debugging purposes.
        """
        seeder_session.tunnel_community.monitor_downloads([ds])
        d = ds.get_download()
        print("seeder: %s %s %s" % (repr(d.get_def().get_name()), dlstatus_strings[ds.get_status()], ds.get_progress()))
        return 2

    upload.set_state_callback(seeder_state_callback)

    await upload.wait_for_status(DLSTATUS_SEEDING)
    yield seeder_session
    await seeder_session.shutdown()


async def sanitize_network(session):
    # We disable the discovery communities in this session since we don't want to walk to the live network
    for overlay in session.ipv8.overlays:
        if isinstance(overlay, DiscoveryCommunity):
            await overlay.unload()
    session.ipv8.overlays = []
    session.ipv8.strategies = []

    # Also reset the IPv8 network
    session.ipv8.network = Network()


async def load_tunnel_community_in_session(session, exitnode=False, start_lt=False):
    """
    Load the tunnel community in a given session. We are using our own tunnel community here instead of the one
    used in Tribler.
    """
    await sanitize_network(session)

    keypair = ECCrypto().generate_key(u"curve25519")
    tunnel_peer = Peer(keypair)
    session.config.set_tunnel_community_exitnode_enabled(exitnode)
    overlay = TriblerTunnelCommunity(tunnel_peer, session.ipv8.endpoint, session.ipv8.network,
                                     tribler_session=session, settings={"max_circuits": 1})
    if exitnode:
        overlay.settings.peer_flags.add(PEER_FLAG_EXIT_BT)
    overlay.dht_provider = MockDHTProvider(Peer(overlay.my_peer.key, overlay.my_estimated_wan))
    overlay.settings.remove_tunnel_delay = 0
    session.ipv8.overlays.append(overlay)

    await overlay.wait_for_socks_servers()

    if start_lt:
        # If libtorrent tries to connect to the socks5 servers before they are loaded,
        # it will never recover (on Mac/Linux with Libtorrent >=1.2.0). Therefore, we start
        # libtorrent afterwards.
        tunnel_community_ports = session.config.get_tunnel_community_socks5_listen_ports()
        session.config.set_anon_proxy_settings(2, ("127.0.0.1", tunnel_community_ports))
        session.dlmgr = DownloadManager(session)
        session.dlmgr.initialize()
        session.dlmgr.is_shutdown_ready = lambda: True

    session.tunnel_community = overlay

    return overlay


def start_anon_download(session, seed_session, tdef, hops=1):
    """
    Start an anonymous download in the main Tribler session.
    """
    session.config.set_libtorrent_dht_readiness_timeout(0)
    dscfg = DownloadConfig()
    dscfg.set_dest_dir(session.config.get_state_dir())
    dscfg.set_hops(hops)
    download = session.dlmgr.start_download(tdef=tdef, config=dscfg)
    session.tunnel_community.bittorrent_peers[download] = [("127.0.0.1", seed_session.config.get_libtorrent_port())]
    return download


async def introduce_peers(sessions):
    for session_introduce in sessions:
        for session in sessions:
            if session_introduce != session:
                session.tunnel_community.walk_to(
                    ('127.0.0.1', session_introduce.tunnel_community.endpoint.get_address()[1]))

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


@pytest.mark.asyncio
@pytest.mark.timeout(20)
@pytest.mark.flaky
async def test_anon_download(enable_ipv8, proxy_factory, session, video_seeder_session, video_tdef):
    """
    Testing whether an anonymous download over our tunnels works
    """
    await load_tunnel_community_in_session(session, exitnode=False, start_lt=True)

    relays, exit_nodes = await create_nodes(proxy_factory)
    await introduce_peers([session] + relays + exit_nodes)

    download = start_anon_download(session, video_seeder_session, video_tdef)
    await download.wait_for_status(DLSTATUS_DOWNLOADING)
    session.dlmgr.set_download_states_callback(session.dlmgr.sesscb_states_callback, interval=.1)
    while not session.tunnel_community.find_circuits():
        await sleep(.1)
    await sleep(.6)
    assert session.tunnel_community.find_circuits()[0].bytes_up > 0
    assert session.tunnel_community.find_circuits()[0].bytes_down > 0


@pytest.mark.asyncio
@pytest.mark.timeout(30)
@pytest.mark.flaky
async def test_hidden_services(enable_ipv8, proxy_factory, session, hidden_seeder_session, video_tdef):
    """
    Test the hidden services overlay by constructing an end-to-end circuit and downloading a torrent over it
    """
    await load_tunnel_community_in_session(session, exitnode=False, start_lt=True)

    hidden_seeder_session.tunnel_community.build_tunnels(1)

    relays, exit_nodes = await create_nodes(proxy_factory, num_relays=3, num_exitnodes=2)
    await introduce_peers([session, hidden_seeder_session] + relays + exit_nodes)
    await deliver_messages(timeout=1)

    for ses in [session, hidden_seeder_session] + relays + exit_nodes:
        assert len(ses.tunnel_community.get_peers()) == 6

    progress = Future()

    def download_state_callback(ds):
        session.tunnel_community.monitor_downloads([ds])
        print(time.time(), ds.get_status(), ds.get_progress())
        if ds.get_progress():
            progress.set_result(None)
        return 2

    session.tunnel_community.build_tunnels(1)

    while not hidden_seeder_session.tunnel_community.find_circuits(ctype=CIRCUIT_TYPE_IP_SEEDER):
        await deliver_messages()

    download = start_anon_download(session, hidden_seeder_session, video_tdef, hops=1)
    download.set_state_callback(download_state_callback)
    await progress
