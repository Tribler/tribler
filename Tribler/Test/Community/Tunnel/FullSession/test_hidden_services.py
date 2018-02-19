from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.simpledefs import DLSTATUS_SEEDING
from Tribler.Test.Community.Tunnel.FullSession.test_tunnel_base import TestTunnelBase
from Tribler.Test.twisted_thread import deferred


class TestHiddenServices(TestTunnelBase):

    def setUp(self, autoload_discovery=True):
        TestTunnelBase.setUp(self, autoload_discovery=autoload_discovery)
        self.test_deferred = Deferred()

    @deferred(timeout=180)
    @inlineCallbacks
    def test_hidden_services(self):
        yield self.setup_nodes(num_relays=4, num_exitnodes=2, seed_hops=1)

        yield self.deliver_messages

        for c in self.tunnel_communities:
            self.assertEqual(7, len(c.network.verified_peers))
        self.assertEqual(7, len(self.tunnel_community_seeder.network.verified_peers))

        def download_state_callback(ds):
            self.tunnel_community.monitor_downloads([ds])
            download = ds.get_download()
            import time
            print time.time(), ds.get_status(), download.get_progress()
            if download.get_progress() == 1.0 and ds.get_status() == DLSTATUS_SEEDING:
                self.test_deferred.callback(None)
                return 0.0, False

            return 2.0, False

        self.tunnel_community.build_tunnels(1)

        while len(self.tunnel_community_seeder.my_intro_points) < 1:
            yield self.deliver_messages()

        download = self.start_anon_download(hops=1)
        download.set_state_callback(download_state_callback)

        yield self.test_deferred
