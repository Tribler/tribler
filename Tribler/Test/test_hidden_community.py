import time
from threading import Event
from traceback import print_exc

# This needs to be imported before anything from tribler so the reactor gets initalized on the right thread
from Tribler.Test.test_tunnel_base import TestTunnelBase

from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id
from Tribler.community.tunnel import CIRCUIT_ID_PORT
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity


class TestHiddenCommunity(TestTunnelBase):

    def test_hidden_services(self):
        def take_second_screenshot():
            self.screenshot('Network graph after libtorrent download over hidden services')
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After libtorrent download over hidden services (took %.2f s)" % download_time)
            self.guiUtility.ShowPage('networkgraph')
            self.Call(1, take_second_screenshot)

        def on_fail(expected, reason, do_assert):
            dispersy = self.session.lm.dispersy
            tunnel_community = next(c for c in dispersy.get_communities() if isinstance(c, HiddenTunnelCommunity))

            self.guiUtility.ShowPage('networkgraph')

            def do_asserts():
                self.assert_(len(tunnel_community.active_data_circuits()) >= 4,
                             "At least 4 data circuits should have been created (got %d)" %
                             len(tunnel_community.active_data_circuits()),
                             False)
                self.assert_(expected, reason, do_assert)
                self.quit()

            self.Call(1, do_asserts)

        def do_progress(download, start_time):
            self.CallConditional(140,
                                 lambda: download.get_progress() == 1.0,
                                 lambda: take_screenshot(time.time() - start_time),
                                 'Hidden services download should be finished in 140 seconds (%.1f%% downloaded)' %
                                 (download.get_progress() * 100),
                                 on_fail)

        def start_download(tf):
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=tf, destdir=self.getDestDir(), hops=2)
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
            seeder_session.set_anon_proxy_settings(
                2, ("127.0.0.1", seeder_session.get_tunnel_community_socks5_listen_ports()))
            seeder_session.set_download_states_callback(download_states_callback, False)

            # Start seeding
            tf = self.setupSeeder(hops=2, session=seeder_session)

            # Wait for the introduction point to announce itself to the DHT
            dht = Event()

            def dht_announce(info_hash, community):
                def cb_dht(info_hash, peers, source):
                    self._logger.debug("announced %s to the DHT", info_hash.encode('hex'))
                    dht.set()
                port = community.trsession.get_dispersy_port()
                community.trsession.lm.mainline_dht.get_peers(info_hash, Id(info_hash), cb_dht, bt_port=port)
            for community in tunnel_communities:
                community.dht_announce = lambda ih, com = community: dht_announce(ih, com)
            self.CallConditional(90, dht.is_set, lambda: self.Call(5, lambda: start_download(tf)),
                                 'Introduction point did not get announced')

        self.startTest(setup_seeder, nr_relays=6, nr_exitnodes=4, bypass_dht=True)

    def test_hidden_services_with_exit_nodes(self):
        def take_second_screenshot():
            self.screenshot('Network graph after libtorrent download with hidden services over exitnodes')
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After libtorrent download with hidden services over exitnodes (took %.2f s)" %
                            download_time)
            self.guiUtility.ShowPage('networkgraph')
            self.Call(1, take_second_screenshot)

        def on_fail(expected, reason, do_assert):
            dispersy = self.session.lm.dispersy
            tunnel_community = next(c for c in dispersy.get_communities() if isinstance(c, HiddenTunnelCommunity))

            self.guiUtility.ShowPage('networkgraph')

            def do_asserts():
                self.assert_(len(tunnel_community.active_data_circuits()) >= 4,
                             "At least 4 data circuits should have been created (got %d)" %
                             len(tunnel_community.active_data_circuits()),
                             False)
                self.assert_(expected, reason, do_assert)
                self.quit()

            self.Call(1, do_asserts)

        def do_progress(d, start_time):
            # Check for progress from both seeders
            hs_progress = Event()
            en_progress = Event()

            def cb(ds):
                for peer in ds.get_peerlist():
                    if peer['dtotal'] > 0:
                        if peer['ip'] == '127.0.0.1' and peer['port'] == self.sessions[1].get_listen_port():
                            en_progress.set()
                        elif peer['port'] == CIRCUIT_ID_PORT:
                            hs_progress.set()
                return 5.0, True

            d.set_state_callback(cb, True)

            self.CallConditional(140,
                                 lambda: d.get_progress() == 1.0 and hs_progress.is_set() and en_progress.is_set(),
                                 lambda: take_screenshot(time.time() - start_time),
                                 'Hidden services download should be finished in 140s', on_fail)

        def start_download(tf):
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=tf, destdir=self.getDestDir(), hops=2)

            # Inject IP of the 2nd seeder so that the download starts using both hidden services & exit tunnels
            self.Call(15, lambda: download.add_peer(("127.0.0.1", self.sessions[1].get_listen_port())))

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
            for tc in tunnel_communities[:-1]:
                tc.settings.min_circuits = 0
                tc.settings.max_circuits = 0
            seeder_session = self.sessions[0]
            seeder_session.set_anon_proxy_settings(
                2, ("127.0.0.1", seeder_session.get_tunnel_community_socks5_listen_ports()))
            seeder_session.set_download_states_callback(download_states_callback, False)

            # Start seeding with hidden services
            tf = self.setupSeeder(hops=2, session=seeder_session)

            # Start another seeder from which we'll download using exit nodes
            self.setupSeeder(hops=0, session=self.sessions[1])

            # Wait for the introduction point to announce itself to the DHT
            dht = Event()

            def dht_announce(info_hash, community):
                def cb_dht(info_hash, peers, source):
                    self._logger.debug("announced %s to the DHT", info_hash.encode('hex'))
                    dht.set()
                port = community.trsession.get_dispersy_port()
                community.trsession.lm.mainline_dht.get_peers(info_hash, Id(info_hash), cb_dht, bt_port=port)
            for community in tunnel_communities:
                community.dht_announce = lambda ih, com = community: dht_announce(ih, com)
            self.CallConditional(90, dht.is_set, lambda: self.Call(5, lambda: start_download(tf)),
                                 'Introduction point did not get announced')

        self.startTest(setup_seeder, nr_relays=6, nr_exitnodes=4, bypass_dht=True)
