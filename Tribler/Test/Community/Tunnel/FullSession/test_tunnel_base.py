from __future__ import absolute_import

import os

from six.moves import xrange

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import deferLater

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import dlstatus_strings
from Tribler.Test.test_as_server import TESTS_DATA_DIR, TestAsServer
from Tribler.community.triblertunnel.community import TriblerTunnelCommunity
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.peerdiscovery.community import DiscoveryCommunity
from Tribler.pyipv8.ipv8.peerdiscovery.network import Network

# Map of info_hash -> peer list
global_dht_services = {}


class MockDHTProvider(object):

    def __init__(self, address):
        self.address = ("127.0.0.1", address[1])

    def lookup(self, info_hash, cb):
        if info_hash in global_dht_services:
            cb((info_hash, global_dht_services[info_hash], None))

    def announce(self, info_hash):
        if info_hash in global_dht_services:
            global_dht_services[info_hash].append(self.address)
        else:
            global_dht_services[info_hash] = [self.address]


class TestTunnelBase(TestAsServer):

    @inlineCallbacks
    def setUp(self):
        """
        Setup various variables and load the tunnel community in the main downloader session.
        """
        yield TestAsServer.setUp(self)
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

        self.tunnel_community = self.load_tunnel_community_in_session(self.session, exitnode=True)
        self.tunnel_communities = []

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_dispersy_enabled(False)
        self.config.set_ipv8_enabled(True)
        self.config.set_libtorrent_enabled(True)
        self.config.set_trustchain_enabled(False)
        self.config.set_resource_monitor_enabled(False)
        self.config.set_tunnel_community_socks5_listen_ports(self.get_socks5_ports())

    @inlineCallbacks
    def tearDown(self):
        if self.session2:
            yield self.session2.shutdown()

        for session in self.sessions:
            yield session.shutdown()

        yield TestAsServer.tearDown(self)

    @inlineCallbacks
    def setup_nodes(self, num_relays=1, num_exitnodes=1, seed_hops=0):
        """
        Setup all required nodes, including the relays, exit nodes and seeder.
        """
        baseindex = 3
        for i in xrange(baseindex, baseindex + num_relays):  # Normal relays
            proxy = yield self.create_proxy(i)
            self.tunnel_communities.append(proxy)

        baseindex += num_relays + 1
        for i in xrange(baseindex, baseindex + num_exitnodes):  # Exit nodes
            proxy = yield self.create_proxy(i, exitnode=True)
            self.tunnel_communities.append(proxy)

        # Setup the seeder session
        yield self.setup_tunnel_seeder(seed_hops)

        # Add the tunnel community of the downloader session
        self.tunnel_communities.append(self.tunnel_community)

        self._logger.info("Introducing all nodes to each other in tests")
        for community_introduce in self.tunnel_communities + ([self.tunnel_community_seeder] if
                                                              self.tunnel_community_seeder else []):
            for community in self.tunnel_communities + ([self.tunnel_community_seeder] if
                                                        self.tunnel_community_seeder else []):
                if community != community_introduce:
                    community.walk_to(community_introduce.endpoint.get_address())

        yield self.deliver_messages()

    def sanitize_network(self, session):
        # We disable the discovery communities in this session since we don't want to walk to the live network
        for overlay in session.lm.ipv8.overlays:
            if isinstance(overlay, DiscoveryCommunity):
                overlay.unload()
        session.lm.ipv8.overlays = []
        session.lm.ipv8.strategies = []

        # Also reset the IPv8 network
        session.lm.ipv8.network = Network()

    def load_tunnel_community_in_session(self, session, exitnode=False):
        """
        Load the tunnel community in a given session. We are using our own tunnel community here instead of the one
        used in Tribler.
        """
        self.sanitize_network(session)

        keypair = ECCrypto().generate_key(u"curve25519")
        tunnel_peer = Peer(keypair)
        session.config.set_tunnel_community_exitnode_enabled(exitnode)
        overlay = self.test_class(tunnel_peer, session.lm.ipv8.endpoint, session.lm.ipv8.network,
                                  tribler_session=session,
                                  dht_provider=MockDHTProvider(session.lm.ipv8.endpoint.get_address()),
                                  settings={"become_exitnode": exitnode, "max_circuits": 1})
        overlay._use_main_thread = False
        overlay.settings.remove_tunnel_delay = 0
        session.lm.ipv8.overlays.append(overlay)

        return overlay

    @inlineCallbacks
    def create_proxy(self, index, exitnode=False):
        """
        Create a single proxy and load the tunnel community in the session of that proxy.
        """
        from Tribler.Core.Session import Session

        self.setUpPreSession()
        config = self.config.copy()
        config.set_libtorrent_enabled(True)
        config.set_dispersy_enabled(False)
        config.set_state_dir(self.getStateDir(index))
        config.set_tunnel_community_socks5_listen_ports(self.get_socks5_ports())

        session = Session(config)
        yield session.start()
        self.sessions.append(session)

        returnValue(self.load_tunnel_community_in_session(session, exitnode=exitnode))

    def setup_tunnel_seeder(self, hops):
        """
        Setup the seeder.
        """
        from Tribler.Core.Session import Session

        self.seed_config = self.config.copy()
        self.seed_config.set_state_dir(self.getStateDir(2))
        self.seed_config.set_megacache_enabled(True)
        self.seed_config.set_tunnel_community_socks5_listen_ports(self.get_socks5_ports())
        if self.session2 is None:
            self.session2 = Session(self.seed_config)
            self.session2.start()

        tdef = TorrentDef()
        tdef.add_content(os.path.join(TESTS_DATA_DIR, "video.avi"))
        tdef.set_tracker("http://localhost/announce")
        tdef.finalize()
        torrentfn = os.path.join(self.session2.config.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)
        self.seed_tdef = tdef

        if hops > 0:  # Safe seeding enabled
            self.tunnel_community_seeder = self.load_tunnel_community_in_session(self.session2)
            self.tunnel_community_seeder.build_tunnels(hops)
        else:
            self.sanitize_network(self.session2)

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(TESTS_DATA_DIR)  # basedir of the file we are seeding
        dscfg.set_hops(hops)
        d = self.session2.start_download_from_tdef(tdef, dscfg)
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
        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(self.getDestDir())
        dscfg.set_hops(hops)
        download = self.session.start_download_from_tdef(self.seed_tdef, dscfg)
        tc = self.session.lm.tunnel_community
        tc.bittorrent_peers[download] = [("127.0.0.1", self.session2.config.get_libtorrent_port())]
        return download

    @inlineCallbacks
    def deliver_messages(self, timeout=.1):
        """
        Allow peers to communicate.
        The strategy is as follows:
         1. Measure the amount of working threads in the threadpool
         2. After 10 milliseconds, check if we are down to 0 twice in a row
         3. If not, go back to handling calls (step 2) or return, if the timeout has been reached
        :param timeout: the maximum time to wait for messages to be delivered
        """
        rtime = 0
        probable_exit = False
        while rtime < timeout:
            yield self.sleep(.01)
            rtime += .01
            if len(reactor.getThreadPool().working) == 0:
                if probable_exit:
                    break
                probable_exit = True
            else:
                probable_exit = False

    @inlineCallbacks
    def sleep(self, time=.05):
        yield deferLater(reactor, time, lambda: None)
