import os
import time
from twisted.internet.defer import returnValue, inlineCallbacks

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import dlstatus_strings
from Tribler.Test.test_as_server import TESTS_DATA_DIR, TestAsServer
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.crypto import NoCrypto
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class HiddenTunnelCommunityTests(HiddenTunnelCommunity):
    """
    We are using a seperate community so we do not act as an exit node for the outside world.
    """

    @classmethod
    def get_master_members(cls, dispersy):
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000400f4771c58e65f2cc0385a14027a937a0eb54df0e" \
                     "4ae2f72acd8f8286066a48a5e8dcff81c7dfa369fbc33bfe9823587057557cf168b41586dc9ff7615a7e5213f3ec6" \
                     "c9b4f9f57f00dbc0dd8ca8b9f6d76fd63a432a56d5938ce9dd7bd291daa92bec52ffcd58d9718836163868f493063" \
                     "77c3b8bf36d43ea99122c3276e1a89fb5b9b2ff3f7f6f1702d057dca3e8c0"
        master_key_hex = master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]


class TestTunnelBase(TestAsServer):

    def setUp(self, autoload_discovery=True):
        """
        Setup various variables and load the tunnel community in the main downloader session.
        """
        TestAsServer.setUp(self, autoload_discovery=autoload_discovery)
        self.seed_tdef = None
        self.sessions = []
        self.session2 = None
        self.crypto_enabled = True
        self.bypass_dht = False
        self.seed_config = None
        self.tunnel_community_seeder = None

        self.tunnel_community = self.load_tunnel_community_in_session(self.session, exitnode=True)
        self.tunnel_communities = []

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_dispersy(True)
        self.config.set_libtorrent(True)

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)

        for session in self.sessions:
            self._shutdown_session(session)

        TestAsServer.tearDown(self)

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
        self.setup_tunnel_seeder(seed_hops)

        # Add the tunnel community of the downloader session
        self.tunnel_communities.append(self.tunnel_community)

        # Connect the candidates with each other in all available tunnel communities
        candidates = []
        for session in self.sessions:
            self._logger.debug("Appending candidate from this session to the list")
            candidates.append(Candidate(session.get_dispersy_instance().lan_address, tunnel=False))

        communities_to_inject = self.tunnel_communities
        if self.tunnel_community_seeder is not None:
            communities_to_inject.append(self.tunnel_community_seeder)

        for community in communities_to_inject:
            for candidate in candidates:
                self._logger.debug("Add appended candidate as discovered candidate to this community")
                # We are letting dispersy deal with adding the community's candidate to itself.
                community.add_discovered_candidate(candidate)

    @blocking_call_on_reactor_thread
    def load_tunnel_community_in_session(self, session, exitnode=False):
        """
        Load the tunnel community in a given session. We are using our own tunnel community here instead of the one
        used in Tribler.
        """
        dispersy = session.get_dispersy_instance()
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        settings = TunnelSettings(tribler_session=session)
        if not self.crypto_enabled:
            settings.crypto = NoCrypto()
        settings.become_exitnode = exitnode

        return dispersy.define_auto_load(HiddenTunnelCommunityTests, dispersy_member, (session, settings), load=True)[0]

    @inlineCallbacks
    def create_proxy(self, index, exitnode=False):
        """
        Create a single proxy and load the tunnel community in the session of that proxy.
        """
        from Tribler.Core.Session import Session

        self.setUpPreSession()
        config = self.config.copy()
        config.set_libtorrent(True)
        config.set_dispersy(True)
        config.set_state_dir(self.getStateDir(index))

        session = Session(config, ignore_singleton=True, autoload_discovery=False)
        session.prestart()
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
        self.seed_config.set_megacache(True)
        if self.session2 is None:
            self.session2 = Session(self.seed_config, ignore_singleton=True, autoload_discovery=False)
            self.session2.prestart()
            self.session2.start()

        tdef = TorrentDef()
        tdef.add_content(os.path.join(TESTS_DATA_DIR, "video.avi"))
        tdef.set_tracker("http://localhost/announce")
        tdef.set_private()  # disable dht
        tdef.finalize()
        torrentfn = os.path.join(self.session2.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)
        self.seed_tdef = tdef

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(TESTS_DATA_DIR)  # basedir of the file we are seeding
        dscfg.set_hops(hops)
        d = self.session2.start_download_from_tdef(tdef, dscfg)
        d.set_state_callback(self.seeder_state_callback)

        if hops > 0:  # Safe seeding enabled
            self.tunnel_community_seeder = self.load_tunnel_community_in_session(self.session2)

    def seeder_state_callback(self, ds):
        """
        The callback of the seeder download. For now, this only logs the state of the download that's seeder and is
        useful for debugging purposes.
        """
        d = ds.get_download()
        self._logger.debug("seeder: %s %s %s", repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()], ds.get_progress())
        return 5.0, False

    def start_anon_download(self, hops=1):
        """
        Start an anonymous download in the main Tribler session.
        """
        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(self.getDestDir())
        dscfg.set_hops(hops)
        download = self.session.start_download_from_tdef(self.seed_tdef, dscfg)
        download.add_peer(("127.0.0.1", self.session2.get_listen_port()))
        return download
