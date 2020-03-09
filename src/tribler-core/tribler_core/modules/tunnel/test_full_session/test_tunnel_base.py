from asyncio import all_tasks, gather, sleep

from ipv8.keyvault.crypto import ECCrypto
from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_ANY
from ipv8.peer import Peer
from ipv8.peerdiscovery.community import DiscoveryCommunity
from ipv8.peerdiscovery.network import Network
from ipv8.test.messaging.anonymization.test_community import MockDHTProvider

from tribler_common.simpledefs import dlstatus_strings

from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.tunnel.community.triblertunnel_community import TriblerTunnelCommunity
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.tests.tools.test_as_server import TestAsServer


class TestTunnelBase(TestAsServer):

    async def setUp(self):
        """
        Setup various variables and load the tunnel community in the main downloader session.
        """
        await TestAsServer.setUp(self)
        self.seed_tdef = None
        self.sessions = []
        self.session2 = None
        self.bypass_dht = False
        self.seed_config = None
        self.tunnel_community_seeder = None

        self.eccrypto = ECCrypto()
        ec = self.eccrypto.generate_key(u"curve25519")
        self.test_class = TriblerTunnelCommunity
        self.test_class.master_peer = Peer(ec)

        self.tunnel_community = await self.load_tunnel_community_in_session(self.session, exitnode=True, start_lt=True)
        self.session.tunnel_community = self.tunnel_community  # Magic!
        self.tunnel_communities = []

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_ipv8_enabled(True)
        self.config.set_ipv8_port(-1)
        self.config.set_libtorrent_enabled(False)
        self.config.set_trustchain_enabled(False)
        self.config.set_tunnel_community_socks5_listen_ports(self.get_ports(5))

    async def tearDown(self):
        if self.session2:
            await self.session2.shutdown()

        await gather(*[s.shutdown() for s in self.sessions])

        await gather(*[tc.unload() for tc in self.tunnel_communities])

        if self.tunnel_community_seeder:
            await self.tunnel_community_seeder.unload()

        await TestAsServer.tearDown(self)

    async def setup_nodes(self, num_relays=1, num_exitnodes=1, seed_hops=0):
        """
        Setup all required nodes, including the relays, exit nodes and seeder.
        """
        baseindex = 3
        for i in range(baseindex, baseindex + num_relays):  # Normal relays
            proxy = await self.create_proxy(i)
            self.tunnel_communities.append(proxy)

        baseindex += num_relays + 1
        for i in range(baseindex, baseindex + num_exitnodes):  # Exit nodes
            proxy = await self.create_proxy(i, exitnode=True)
            self.tunnel_communities.append(proxy)

        # Setup the seeder session
        await self.setup_tunnel_seeder(seed_hops)

        # Add the tunnel community of the downloader session
        self.tunnel_communities.append(self.tunnel_community)

        self._logger.info("Introducing all nodes to each other in tests")
        other_tunnel_communities = [self.tunnel_community_seeder] if self.tunnel_community_seeder else []
        for community_introduce in self.tunnel_communities + other_tunnel_communities:
            for community in self.tunnel_communities + other_tunnel_communities:
                if community != community_introduce:
                    community.walk_to(('127.0.0.1', community_introduce.endpoint.get_address()[1]))

        await self.deliver_messages()

    async def sanitize_network(self, session):
        # We disable the discovery communities in this session since we don't want to walk to the live network
        for overlay in session.ipv8.overlays:
            if isinstance(overlay, DiscoveryCommunity):
                await overlay.unload()
        session.ipv8.overlays = []
        session.ipv8.strategies = []

        # Also reset the IPv8 network
        session.ipv8.network = Network()

    async def load_tunnel_community_in_session(self, session, exitnode=False, start_lt=False):
        """
        Load the tunnel community in a given session. We are using our own tunnel community here instead of the one
        used in Tribler.
        """
        await self.sanitize_network(session)

        keypair = ECCrypto().generate_key(u"curve25519")
        tunnel_peer = Peer(keypair)
        session.config.set_tunnel_community_exitnode_enabled(exitnode)
        overlay = self.test_class(tunnel_peer, session.ipv8.endpoint, session.ipv8.network,
                                  tribler_session=session, settings={"max_circuits": 1})
        if exitnode:
            overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        overlay._use_main_thread = False
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

        return overlay

    async def create_proxy(self, index, exitnode=False):
        """
        Create a single proxy and load the tunnel community in the session of that proxy.
        """
        from tribler_core.session import Session

        self.setUpPreSession()
        config = self.config.copy()
        config.set_libtorrent_enabled(False)
        config.set_tunnel_community_socks5_listen_ports(self.get_ports(5))

        session = Session(config)
        session.upgrader_enabled = False
        await session.start()
        self.sessions.append(session)

        return await self.load_tunnel_community_in_session(session, exitnode=exitnode)

    async def setup_tunnel_seeder(self, hops):
        """
        Setup the seeder.
        """
        from tribler_core.session import Session
        self.seed_config = self.config.copy()
        self.seed_config._state_dir = self.getRootStateDir(2)
        self.seed_config.set_libtorrent_enabled(hops == 0)
        self.seed_config.set_tunnel_community_socks5_listen_ports(self.get_ports(5))
        if self.session2 is None:
            self.session2 = Session(self.seed_config)
            self.session2.upgrader_enabled = False
            await self.session2.start()

        tdef = TorrentDef()
        tdef.add_content(TESTS_DATA_DIR / "video.avi")
        tdef.set_tracker("http://localhost/announce")
        torrentfn = self.session2.config.get_state_dir() / "gen.torrent"
        tdef.save(torrent_filepath=torrentfn)
        self.seed_tdef = tdef

        if hops > 0:  # Safe seeding enabled
            self.tunnel_community_seeder = await self.load_tunnel_community_in_session(self.session2, start_lt=True)
            self.tunnel_community_seeder.build_tunnels(hops)
        else:
            await self.sanitize_network(self.session2)

        dscfg = DownloadConfig()
        dscfg.set_dest_dir(TESTS_DATA_DIR)  # basedir of the file we are seeding
        dscfg.set_hops(hops)
        d = self.session2.dlmgr.start_download(tdef=tdef, config=dscfg)
        d.set_state_callback(self.seeder_state_callback)

    def seeder_state_callback(self, ds):
        """
        The callback of the seeder download. For now, this only logs the state of the download that's seeder and is
        useful for debugging purposes.
        """
        if self.tunnel_community_seeder:
            self.tunnel_community_seeder.monitor_downloads([ds])
        d = ds.get_download()
        self._logger.debug("seeder: %s %s %s", repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()], ds.get_progress())
        return 5.0

    def start_anon_download(self, hops=1):
        """
        Start an anonymous download in the main Tribler session.
        """
        dscfg = DownloadConfig()
        dscfg.set_dest_dir(self.getDestDir())
        dscfg.set_hops(hops)
        download = self.session.dlmgr.start_download(tdef=self.seed_tdef, config=dscfg)
        self.tunnel_community.bittorrent_peers[download] = [("127.0.0.1", self.session2.config.get_libtorrent_port())]
        return download

    async def deliver_messages(self, timeout=.1):
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
