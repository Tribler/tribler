# Written by Niels Zeilemaker
# see LICENSE.txt for license information
import os
import sys
import time

from twisted.internet import reactor

from Tribler.Core.simpledefs import dlstatus_strings
from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import blockingCallFromThread


class TestAnonTunnelCommunity(TestGuiAsServer):

    def test_anon_download(self):
        def take_second_screenshot():
            self.screenshot()
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After an anonymous libtorrent download (took %.2f s)" % download_time)
            self.guiUtility.ShowPage('networkgraph')
            self.Call(1, take_second_screenshot)

        def on_fail(expected, reason, do_assert):
            from Tribler.community.anontunnel.community import ProxyCommunity
            from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr

            dispersy = self.session.lm.dispersy
            ''' :type : Dispersy '''
            proxy_community = next(c for c in dispersy.get_communities() if isinstance(c, ProxyCommunity))

            self.guiUtility.ShowPage('networkgraph')

            def do_asserts():
                self.assert_(LibtorrentMgr.getInstance().ltsession_anon is not None, "Anon session should have been created", False)
                self.assert_(len(proxy_community.circuits) >= 4, "At least 4 circuits should have been created", False)
                self.assert_(expected, reason, do_assert)

            self.Call(1, do_asserts)

        def do_create_local_torrent():
            torrentfilename = self.setupSeeder()
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=torrentfilename, destdir=self.getDestDir(), anon_mode=True)

            self.guiUtility.ShowPage('my_files')
            self.Call(5, lambda: download.add_peer(("127.0.0.1", self.session2.get_listen_port())))
            self.CallConditional(
                150,
                lambda: download.get_progress() == 1.0,
                lambda: take_screenshot(time.time() - start_time),
                'Anonymous download should be finished in 150 seconds',
                on_fail
            )

        self.startTest(do_create_local_torrent)

    def startTest(self, callback, min_timeout=5):
        self.getStateDir()  # getStateDir copies the bootstrap file into the statedir

        from Tribler.community.anontunnel.community import ProxyCommunity, ProxySettings
        def setup_proxies():
            proxy_communities = []
            for i in range(3, 11):
                proxy_communities.append(create_proxy(i))


            # Connect the proxies to the Tribler instance
            for community in self.lm.dispersy.get_communities():
                if isinstance(community, ProxyCommunity):
                    proxy_communities.append(community)

            candidates = []
            for session in self.sessions:
                dispersy = session.get_dispersy_instance()
                candidates.append(Candidate(dispersy.lan_address, tunnel=False))

            for community in proxy_communities:
                for candidate in candidates:
                    # We are letting dispersy deal with addins the community's candidate to itself.
                    community.add_discovered_candidate(candidate)

            callback()

        def create_proxy(index):
            from Tribler.Core.Session import Session
            from Tribler.community.anontunnel import exitstrategies, crypto

            self.setUpPreSession()
            config = self.config.copy()
            config.set_dispersy(True)
            config.set_state_dir(self.getStateDir(index))
            config.set_dispersy_tunnel_over_swift(True)

            session = Session(config, ignore_singleton=True)
            session.start()
            self.sessions.append(session)

            while not session.lm.initComplete:
                time.sleep(1)

            dispersy = session.get_dispersy_instance()

            def load_community(session):
                keypair = dispersy.crypto.generate_key(u"NID_secp160k1")
                dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))

                proxy_community = dispersy.define_auto_load(ProxyCommunity, dispersy_member, (None, None, session.lm.rawserver), load=True)[0]
                exit_strategy = exitstrategies.DefaultExitStrategy(session.lm.rawserver, proxy_community)
                proxy_community.observers.append(exit_strategy)

                return proxy_community

            return blockingCallFromThread(reactor, load_community, session)

        TestGuiAsServer.startTest(self, setup_proxies, force_is_unit_testing=False)

    def setupSeeder(self):
        from Tribler.Core.Session import Session
        from Tribler.Core.TorrentDef import TorrentDef
        from Tribler.Core.DownloadConfig import DownloadStartupConfig

        self.setUpPreSession()
        self.config.set_libtorrent(True)

        self.config2 = self.config.copy()
        self.config2.set_state_dir(self.getStateDir(2))
        self.session2 = Session(self.config2, ignore_singleton=True)
        self.session2.start()

        tdef = TorrentDef()
        tdef.add_content(os.path.join(BASE_DIR, "data", "video.avi"))
        tdef.set_tracker("http://fake.net/announce")
        tdef.finalize()
        torrentfn = os.path.join(self.session2.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(os.path.join(BASE_DIR, "data"))  # basedir of the file we are seeding
        d = self.session2.start_download(tdef, dscfg)
        d.set_state_callback(self.seeder_state_callback)

        return torrentfn

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        print >> sys.stderr, "test: seeder:", repr(d.get_def().get_name()), dlstatus_strings[ds.get_status()], ds.get_progress()
        return (5.0, False)

    def setUp(self):
        with open("bootstraptribler.txt", "w") as f:
            f.write("127.0.0.1 1")

        TestGuiAsServer.setUp(self)
        self.sessions = []
        self.session2 = None

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)

        for session in self.sessions:
            self._shutdown_session(session)

        os.unlink("bootstraptribler.txt")
        time.sleep(10)
        TestGuiAsServer.tearDown(self)
