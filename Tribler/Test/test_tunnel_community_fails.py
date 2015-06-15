# Written by Niels Zeilemaker
# see LICENSE.txt for license information
import time

# This needs to be imported before anything from tribler so the reactor gets initalied on the right thread
from Tribler.Test.test_tunnel_base import TestTunnelBase

from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity


class TestTunnelCommunityFails(TestTunnelBase):

    def test_anon_download_exitnode_changeofmind(self):

        def changed_my_mind(tunnel_communities):
            for tunnel_community in tunnel_communities:
                # Disables exitnode flag during runtime
                tunnel_community.settings.become_exitnode = False

        def compare_progress(lastprogress, download):
            progress = download.get_progress()
            self.assert_(progress == lastprogress,
                         "Expected no progress, but actual progress was progress=%s, lastprogress=%s" % (progress,
                                                                                                         lastprogress))
            self.quit()

        def check_progress(download, start_time):
            lastprogress = download.get_progress()
            self.Call(10, lambda d=download, lp=lastprogress: compare_progress(lp, d))

        def do_create_local_torrent(tunnel_communities):
            tf = self.setupSeeder()
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=tf, destdir=self.getDestDir(), hops=2)

            self.guiUtility.ShowPage('my_files')
            self.Call(5, lambda: download.add_peer(("127.0.0.1", self.session2.get_listen_port())))
            self.Call(20, lambda: changed_my_mind(tunnel_communities))
            self.Call(40, lambda d=download, s=start_time: check_progress(d, s))

        self.startTest(do_create_local_torrent, nr_exitnodes=4, nr_relays=6)

    def test_anon_download_without_relays(self):
        def take_second_screenshot():
            self.screenshot('Networkgraph after an anonymous libtorrent download without relays')
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After an anonymous libtorrent download without relays")
            self.guiUtility.ShowPage('networkgraph')
            self.Call(1, take_second_screenshot)

        def on_success(download, start_time):
            take_screenshot(time.time() - start_time)

        def on_fail(expected, reason, do_assert):
            dispersy = self.session.lm.dispersy
            tunnel_community = next(c for c in dispersy.get_communities() if isinstance(c, HiddenTunnelCommunity))

            self.guiUtility.ShowPage('networkgraph')

            def do_asserts():
                self.assert_(len(tunnel_community.active_data_circuits()) == 0,
                             "No data circuits should have been created (got %d)" %
                             len(tunnel_community.active_data_circuits()),
                             False)
                self.assert_(expected, reason, do_assert)

            self.Call(1, do_asserts)

        def check_progress(download, start_time):
            self.CallConditional(1,
                                 lambda: download.get_progress() == 0.0,
                                 lambda: on_success(download, start_time),
                                 'Anonymous download without relays should not have any progress (%.1f%% downloaded)' %
                                 (download.get_progress() * 100), on_fail)

        def do_create_local_torrent(_):
            tf = self.setupSeeder()
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=tf, destdir=self.getDestDir(), hops=2)

            self.guiUtility.ShowPage('my_files')
            self.Call(5, lambda: download.add_peer(("127.0.0.1", self.session2.get_listen_port())))
            self.Call(60, lambda: check_progress(download, start_time))

        self.startTest(do_create_local_torrent, nr_exitnodes=5, nr_relays=0)

    def test_anon_download_without_exitnodes(self):
        def take_second_screenshot():
            self.screenshot('Network graph after an anonymous libtorrent download without exitnodes')
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After an anonymous libtorrent download without exitnodes")
            self.guiUtility.ShowPage('networkgraph')
            self.Call(1, take_second_screenshot)

        def on_success(download, start_time):
            take_screenshot(time.time() - start_time)

        def on_fail(expected, reason, do_assert):
            dispersy = self.session.lm.dispersy
            tunnel_community = next(c for c in dispersy.get_communities() if isinstance(c, HiddenTunnelCommunity))

            self.guiUtility.ShowPage('networkgraph')

            def do_asserts():
                self.assert_(len(tunnel_community.active_data_circuits()) == 0,
                             "No data circuits should have been created (got %d)" %
                             len(tunnel_community.active_data_circuits()),
                             False)
                self.assert_(expected, reason, do_assert)

            self.Call(1, do_asserts)

        def check_progress(download, start_time):
            self.CallConditional(1,
                                 lambda: download.get_progress() == 0.0,
                                 lambda: on_success(download, start_time),
                                 'Anonymous download without exit nodes should not make progress (%.1f%% downloaded)' %
                                 (download.get_progress() * 100), on_fail)

        def do_create_local_torrent(_):
            tf = self.setupSeeder()
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=tf, destdir=self.getDestDir(), hops=2)

            self.guiUtility.ShowPage('my_files')
            self.Call(5, lambda: download.add_peer(("127.0.0.1", self.session2.get_listen_port())))
            self.Call(60, lambda: check_progress(download, start_time))

        self.startTest(do_create_local_torrent, nr_exitnodes=0, nr_relays=5)
