# Written by Niels Zeilemaker
# see LICENSE.txt for license information
import time

# This needs to be imported before anything from tribler so the reactor gets initalied on the right thread
from Tribler.Test.test_tunnel_base import TestTunnelBase

from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity


class TestTunnelCommunityPositive(TestTunnelBase):

    def test_anon_tunnel(self):
        from threading import Event
        got_data = Event()

        def on_incoming_from_tunnel(socks_server, community, circuit, origin, data):
            self.assert_(data == "4242", "Data is not 4242, it is '%s'" % data.encode("HEX"))
            self.assert_(origin == ("127.0.0.1", 12345),
                         "Origin is not 127.0.0.1:12345, it is '%s:%d'" % (origin[0], origin[1]))
            got_data.set()

        def exit_data(community, circuit_id, sock_addr, destination, data):
            self.assert_(data == "42", "Data is not 42, it is '%s'" % data.encode("HEX"))
            self.assert_(destination == ("127.0.0.1", 12345), "Destination is not 127.0.0.1:12345, it is '%s:%d'" %
                         (destination[0], destination[1]))
            community.tunnel_data_to_origin(circuit_id, sock_addr, ("127.0.0.1", 12345), "4242")

        def start_test(tunnel_communities):
            # assuming that the last tunnel community is that loaded by the tribler gui
            tunnel_community = tunnel_communities[-1]
            first_circuit = tunnel_community.active_data_circuits().values()[0]
            first_circuit.tunnel_data(("127.0.0.1", 12345), "42")
            self.CallConditional(10, got_data.is_set, self.quit)

        def replace_socks(tunnel_communities):
            for tunnel_community in tunnel_communities:
                socks_server = tunnel_community.socks_server
                socks_server.on_incoming_from_tunnel = lambda community, circuit, origin, data, \
                    socks_server = socks_server: on_incoming_from_tunnel(socks_server, community, circuit, origin, data)
                tunnel_community.exit_data = lambda circuit_id, sock_addr, destination, data, \
                    community = tunnel_community: exit_data(community, circuit_id, sock_addr, destination, data)
            tunnel_communities[-1].circuits_needed[3] = 4
            self.CallConditional(20, lambda: len(tunnel_communities[-1].active_data_circuits()) >= 4,
                                 lambda: start_test(tunnel_communities))

        self.startTest(replace_socks)

    def test_anon_download(self):
        def take_second_screenshot():
            self.screenshot('Network graph after an anonymous libtorrent download ')
            self.quit()

        def take_screenshot(download_time):
            self.screenshot("After an anonymous libtorrent download (took %.2f s)" % download_time)
            self.guiUtility.ShowPage('networkgraph')
            self.callLater(1, take_second_screenshot)

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

            self.callLater(1, do_asserts)

        def do_progress(download, start_time):
            self.CallConditional(40,
                                 lambda: download.get_progress() == 1.0,
                                 lambda: take_screenshot(time.time() - start_time),
                                 'Anonymous download should be finished in 40 seconds (%.1f%% downloaded)' % (
                                     download.get_progress() * 100),
                                 on_fail
                                 )

        def do_create_local_torrent(_):
            tf = self.setupSeeder()
            start_time = time.time()
            download = self.guiUtility.frame.startDownload(torrentfilename=tf, destdir=self.getDestDir(), hops=2)

            self.guiUtility.ShowPage('my_files')
            self.callLater(5, lambda: download.add_peer(("127.0.0.1", self.session2.get_listen_port())))

            do_progress(download, start_time)

        self.startTest(do_create_local_torrent)
