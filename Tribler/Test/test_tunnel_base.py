# Written by Niels Zeilemaker
# see LICENSE.txt for license information
import time
import os

# This needs to be imported before anything from tribler so the reactor gets initalized on the right thread
from Tribler.Test.test_as_server import TestGuiAsServer, TESTS_DATA_DIR

from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.Core.simpledefs import dlstatus_strings
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import blockingCallFromThread
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.crypto import NoCrypto
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity


class TestTunnelBase(TestGuiAsServer):

    def startTest(self, callback, min_timeout=5, nr_relays=8, nr_exitnodes=4, crypto_enabled=True, bypass_dht=False):

        self.getStateDir()   # getStateDir copies the bootstrap file into the statedir

        def setup_proxies():
            tunnel_communities = []
            baseindex = 3
            for i in range(baseindex, baseindex + nr_relays):  # Normal relays
                tunnel_communities.append(create_proxy(i, False, crypto_enabled))

            baseindex += nr_relays + 1
            for i in range(baseindex, baseindex + nr_exitnodes):  # Exit nodes
                tunnel_communities.append(create_proxy(i, True, crypto_enabled))

            if bypass_dht:
                # Replace pymdht with a fake one
                class FakeDHT(object):

                    def __init__(self, dht_dict, mainline_dht):
                        self.dht_dict = dht_dict
                        self.mainline_dht = mainline_dht

                    def get_peers(self, lookup_id, _, callback_f, bt_port=0):
                        if bt_port != 0:
                            self.dht_dict[lookup_id] = self.dht_dict.get(lookup_id, []) + [('127.0.0.1', bt_port)]
                        callback_f(lookup_id, self.dht_dict.get(lookup_id, None), None)

                    def stop(self):
                        self.mainline_dht.stop()

                dht_dict = {}
                for session in self.sessions + [self.session]:
                    session.lm.mainline_dht = FakeDHT(dht_dict, session.lm.mainline_dht)

            # Connect the proxies to the Tribler instance
            for community in self.lm.dispersy.get_communities():
                if isinstance(community, HiddenTunnelCommunity):
                    self._logger.debug("Hidden tunnel community appended to the list")
                    tunnel_communities.append(community)

            candidates = []
            for session in self.sessions:
                self._logger.debug("Appending candidate from this session to the list")
                dispersy = session.get_dispersy_instance()
                candidates.append(Candidate(dispersy.lan_address, tunnel=False))

            for community in tunnel_communities:
                for candidate in candidates:
                    self._logger.debug("Add appended candidate as discovered candidate to this community")
                    # We are letting dispersy deal with addins the community's candidate to itself.
                    community.add_discovered_candidate(candidate)

            callback(tunnel_communities)

        def create_proxy(index, become_exit_node, crypto_enabled):
            from Tribler.Core.Session import Session

            self.setUpPreSession()
            config = self.config.copy()
            config.set_libtorrent(True)
            config.set_dispersy(True)
            config.set_state_dir(self.getStateDir(index))

            session = Session(config, ignore_singleton=True, autoload_discovery=False)
            upgrader = session.prestart()
            while not upgrader.is_done:
                time.sleep(0.1)
            session.start()
            self.sessions.append(session)

            while not session.lm.initComplete:
                time.sleep(1)

            dispersy = session.get_dispersy_instance()

            def load_community(session):
                keypair = dispersy.crypto.generate_key(u"curve25519")
                dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
                settings = TunnelSettings(tribler_session=session)
                if not crypto_enabled:
                    settings.crypto = NoCrypto()
                settings.become_exitnode = become_exit_node

                return dispersy.define_auto_load(HiddenTunnelCommunity,
                                                 dispersy_member,
                                                 (session, settings),
                                                 load=True)[0]

            return blockingCallFromThread(reactor, load_community, session)

        TestGuiAsServer.startTest(self, setup_proxies, autoload_discovery=False)

    def setupSeeder(self, hops=0, session=None):
        from Tribler.Core.Session import Session
        from Tribler.Core.TorrentDef import TorrentDef
        from Tribler.Core.DownloadConfig import DownloadStartupConfig

        self.setUpPreSession()
        self.config.set_libtorrent(True)

        self.config2 = self.config.copy()
        self.config2.set_state_dir(self.getStateDir(2))
        if session is None:
            self.session2 = Session(self.config2, ignore_singleton=True, autoload_discovery=False)
            upgrader = self.session2.prestart()
            while not upgrader.is_done:
                time.sleep(0.1)
            self.session2.start()
            session = self.session2

        tdef = TorrentDef()
        tdef.add_content(os.path.join(TESTS_DATA_DIR, "video.avi"))
        tdef.set_tracker("http://fake.net/announce")
        tdef.set_private()  # disable dht
        tdef.finalize()
        torrentfn = os.path.join(session.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(TESTS_DATA_DIR)  # basedir of the file we are seeding
        dscfg.set_hops(hops)
        d = session.start_download(tdef, dscfg)
        d.set_state_callback(self.seeder_state_callback)

        return torrentfn

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("seeder: %s %s %s", repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()], ds.get_progress())
        return 5.0, False

    def setUp(self):
        TestGuiAsServer.setUp(self)
        self.sessions = []
        self.session2 = None

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)

        for session in self.sessions:
            self._shutdown_session(session)

        time.sleep(10)
        TestGuiAsServer.tearDown(self)

    def quit(self):
        if self.session2:
            self._shutdown_session(self.session2)

        for session in self.sessions:
            self._shutdown_session(session)

        self.session2 = None
        self.sessions = []

        TestGuiAsServer.quit(self)
