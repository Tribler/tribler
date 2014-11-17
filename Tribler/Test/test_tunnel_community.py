# Written by Niels Zeilemaker
# see LICENSE.txt for license information
import os
import sys
import time

from threading import Event
from traceback import print_exc
from twisted.internet import reactor

from Tribler.Core.simpledefs import dlstatus_strings
from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import blockingCallFromThread
from Tribler.community.tunnel.community import TunnelCommunity, TunnelSettings
from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id


class TestTunnelCommunity(TestGuiAsServer):

    def test_anon_download(self):
        def take_second_screenshot():
            self.screenshot()
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After an anonymous libtorrent download (took %.2f s)" % download_time)
            self.guiUtility.ShowPage('networkgraph')
            self.Call(1, take_second_screenshot)

        def on_fail(expected, reason, do_assert):
            dispersy = self.session.lm.dispersy
            tunnel_community = next(c for c in dispersy.get_communities() if isinstance(c, TunnelCommunity))

            self.guiUtility.ShowPage('networkgraph')

            def do_asserts():
                self.assert_(len(tunnel_community.circuits) >= 4,
                             "At least 4 circuits should have been created (got %d)" % len(tunnel_community.circuits),
                             False)
                self.assert_(expected, reason, do_assert)

            self.Call(1, do_asserts)

        def do_progress(download, start_time):
            self.CallConditional(120,
                lambda: download.get_progress() == 1.0,
                lambda: take_screenshot(time.time() - start_time),
                'Anonymous download should be finished in 120 seconds (%.1f%% downloaded)' % (download.get_progress() * 100),
                on_fail
            )

        def do_create_local_torrent(_):
            tf = self.setupSeeder()
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=tf, destdir=self.getDestDir(),
                                                           hops=3, try_hidden_services=False)

            self.guiUtility.ShowPage('my_files')
            self.Call(5, lambda : download.add_peer(("127.0.0.1", self.session2.get_listen_port())))

            do_progress(download, start_time)

        self.startTest(do_create_local_torrent)

    def test_anon_tunnel(self):
        got_data = Event()
        this = self

        def on_incoming_from_tunnel(socks_server, community, circuit, origin, data):
            this.assert_(data == "4242", "Data is not 4242, it is '%s'" % data)
            this.assert_(origin == ("127.0.0.1", 12345), "Origin is not 127.0.0.1:12345, it is '%s:%d'" % (origin[0], origin[1]))
            got_data.set()

        def exit_data(community, circuit_id, sock_addr, destination, data):
            self.assert_(data == "42", "Data is not 42, it is '%s'" % data)
            self.assert_(destination == ("127.0.0.1", 12345), "Destination is not 127.0.0.1:12345, it is '%s:%d'" % (destination[0], destination[1]))
            community.tunnel_data_to_origin(circuit_id, sock_addr, ("127.0.0.1", 12345), "4242")

        def start_test(tunnel_communities):
            # assuming that the last tunnel community is that loaded by the tribler gui
            tunnel_community = tunnel_communities[-1]
            first_circuit = tunnel_community.active_data_circuits().values()[0]
            first_circuit.tunnel_data(("127.0.0.1", 12345), "42")
            self.CallConditional(30, got_data.is_set, self.quit)

        def replace_socks(tunnel_communities):
            for tunnel_community in tunnel_communities:
                socks_server = tunnel_community.socks_server
                socks_server.on_incoming_from_tunnel = lambda community, circuit, origin, data, socks_server = socks_server: on_incoming_from_tunnel(socks_server, community, circuit, origin, data)
                tunnel_community.exit_data = lambda circuit_id, sock_addr, destination, data, community = tunnel_community: exit_data(community, circuit_id, sock_addr, destination, data)
            tunnel_communities[-1].circuits_needed[3] = 4

            self.CallConditional(30, lambda: len(tunnel_communities[-1].active_data_circuits()) == 4,
                                     lambda: start_test(tunnel_communities))

        self.startTest(replace_socks)

    def test_hidden_services(self):
        def take_second_screenshot():
            self.screenshot()
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After an anonymous libtorrent download (took %.2f s)" % download_time)
            self.guiUtility.ShowPage('networkgraph')
            self.Call(1, take_second_screenshot)

        def on_fail(expected, reason, do_assert):
            dispersy = self.session.lm.dispersy
            tunnel_community = next(c for c in dispersy.get_communities() if isinstance(c, TunnelCommunity))

            self.guiUtility.ShowPage('networkgraph')

            def do_asserts():
                self.assert_(len(tunnel_community.circuits) >= 4, "At least 4 circuits should have been created", False)
                self.assert_(expected, reason, do_assert)

            self.Call(1, do_asserts)

        def do_progress(download, start_time):
            self.CallConditional(120,
                lambda: download.get_progress() == 1.0,
                lambda: take_screenshot(time.time() - start_time),
                'Anonymous download should be finished in 120 seconds (%.1f%% downloaded)' % (download.get_progress() * 100),
                on_fail
            )

        def start_download(tf):
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=tf, destdir=self.getDestDir(),
                                                           hops=3, try_hidden_services=True)
            self.guiUtility.ShowPage('my_files')
            do_progress(download, start_time)

        def setup_seeder(tunnel_communities):
            # Setup the first session to be the seeder
            def download_states_callback(dslist):
                try:
                    tunnel_communities[0].monitor_downloads(dslist)
                except:
                    print_exc()
                return (1.0, [])
            tunnel_communities[0].settings.min_circuits = 0
            tunnel_communities[0].settings.max_circuits = 0
            seeder_session = self.sessions[0]
            seeder_session.set_anon_proxy_settings(2, ("127.0.0.1", seeder_session.get_tunnel_community_socks5_listen_ports()))
            seeder_session.set_download_states_callback(download_states_callback, False)

            # Create an anonymous torrent
            from Tribler.Core.TorrentDef import TorrentDef
            tdef = TorrentDef()
            tdef.add_content(os.path.join(BASE_DIR, "data", "video.avi"))
            tdef.set_tracker("http://fake.net/announce")
            tdef.set_private()  # disable dht
            tdef.set_anonymous(True)
            tdef.finalize()
            tf = os.path.join(seeder_session.get_state_dir(), "gen.torrent")
            tdef.save(tf)

            # Start seeding
            from Tribler.Core.DownloadConfig import DownloadStartupConfig
            dscfg = DownloadStartupConfig()
            dscfg.set_dest_dir(os.path.join(BASE_DIR, "data"))  # basedir of the file we are seeding
            dscfg.set_hops(3)
            d = seeder_session.start_download(tdef, dscfg)
            d.set_state_callback(self.seeder_state_callback)

            # Wait for the introduction point to announce itself to the DHT
            dht = Event()
            def dht_announce(info_hash, community):
                def cb(info_hash, peers, source):
                    print >> sys.stderr, "announced %s to the DHT" % info_hash.encode('hex')
                    dht.set()
                port = community.trsession.get_swift_tunnel_listen_port()
                community.trsession.lm.mainline_dht.get_peers(info_hash, Id(info_hash), cb, bt_port=port)
            for community in tunnel_communities:
                community.dht_announce = lambda ih, com = community: dht_announce(ih, com)
            self.CallConditional(60, dht.is_set, lambda: self.Call(10, lambda: start_download(tf)),
                                'Introduction point did not get announced')

        self.startTest(setup_seeder)

    def startTest(self, callback, min_timeout=5):
        self.getStateDir()  # getStateDir copies the bootstrap file into the statedir

        def setup_proxies():
            tunnel_communities = []
            for i in range(3, 7):
                tunnel_communities.append(create_proxy(i))

            # Connect the proxies to the Tribler instance
            for community in self.lm.dispersy.get_communities():
                if isinstance(community, TunnelCommunity):
                    tunnel_communities.append(community)
                    community.settings.min_circuits = 3
                    # Cancel 50 MB test download
                    community.cancel_pending_task("start_test")

            candidates = []
            for session in self.sessions:
                dispersy = session.get_dispersy_instance()
                candidates.append(Candidate(dispersy.lan_address, tunnel=False))

            for community in tunnel_communities:
                for candidate in candidates:
                    # We are letting dispersy deal with addins the community's candidate to itself.
                    community.add_discovered_candidate(candidate)

            callback(tunnel_communities)

        def create_proxy(index):
            from Tribler.Core.Session import Session

            self.setUpPreSession()
            config = self.config.copy()
            config.set_libtorrent(True)
            config.set_swift_path(os.path.join('..', '..', 'swift.exe'))
            config.set_swift_proc(True)
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
                settings = TunnelSettings()
                settings.do_test = False
                return dispersy.define_auto_load(TunnelCommunity, dispersy_member, (session, settings), load=True)[0]

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
        tdef.set_private()  # disable dht
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

    def quit(self):
        if self.session2:
            self._shutdown_session(self.session2)

        for session in self.sessions:
            self._shutdown_session(session)

        self.session2 = None
        self.sessions = []

        TestGuiAsServer.quit(self)

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)

        for session in self.sessions:
            self._shutdown_session(session)

        os.unlink("bootstraptribler.txt")
        time.sleep(10)
        TestGuiAsServer.tearDown(self)
