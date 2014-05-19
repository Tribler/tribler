# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import os
import sys
import time

from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR
from Tribler.Core.simpledefs import dlstatus_strings


class TestAnonTunnelCommunity(TestGuiAsServer):

    def test_anon_download(self):
        def take_second_screenshot():
            self.screenshot()
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After an anonymous libtorrent download (took %.2f s)" % download_time)
            self.guiUtility.ShowPage('anonymity')
            self.Call(1, take_second_screenshot)

        def on_fail(expected, message, do_assert):
            def screenshot_on_fail():
                self.screenshot()
                self.assert_(expected, message, True)
                self.quit()

            self.guiUtility.ShowPage('anonymity')
            self.Call(1, screenshot_on_fail)


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
        def setup_proxies():
            for i in range(3, 11):
                create_proxy(i)

            callback()

        def create_proxy(index):
            from Tribler.Core.Session import Session
            from Tribler.community.anontunnel.community import ProxyCommunity, ProxySettings
            from Tribler.community.anontunnel import exitstrategies, crypto

            self.setUpPreSession()
            config = self.config.copy()
            config.set_libtorrent(True)
            config.set_dispersy(True)
            config.set_state_dir(self.getStateDir(index))

            session = Session(config, ignore_singleton=True)
            session.start()
            self.sessions.append(session)

            while not session.lm.initComplete:
                time.sleep(1)

            dispersy = session.lm.dispersy

            def load_community(session):
                keypair = dispersy.crypto.generate_key(u"NID_secp160k1")
                dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))

                settings = ProxySettings()

                proxy_community = dispersy.define_auto_load(ProxyCommunity, dispersy_member, (settings, None), load=True)[0]
                exit_strategy = exitstrategies.DefaultExitStrategy(session.lm.rawserver, proxy_community)
                proxy_community.observers.append(exit_strategy)

                return proxy_community

            self.community = dispersy.callback.call(load_community, (session,))

        TestGuiAsServer.startTest(self, setup_proxies)

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
