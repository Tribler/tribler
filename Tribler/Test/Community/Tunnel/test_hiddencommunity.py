import time

from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING
from Tribler.Test.Community.Tunnel.test_tunnel_base import AbstractTestTunnelCommunity
from Tribler.Test.Core.base_test import MockObject
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestHiddenCommunity(AbstractTestTunnelCommunity):

    @blocking_call_on_reactor_thread
    def test_cleanup_on_download_remove(self):
        circuit_id = 42L
        infohash = '\00'*20

        self.tunnel_community.settings = MockObject()
        self.tunnel_community.settings.dht_lookup_interval = 30
        self.tunnel_community.infohash_ip_circuits[infohash].append((circuit_id, time.time()))
        self.tunnel_community.download_states[infohash] = DLSTATUS_DOWNLOADING

        self.tunnel_community.monitor_downloads([])

        self.assertNotIn(infohash, self.tunnel_community.infohash_ip_circuits)

    @blocking_call_on_reactor_thread
    def test_create_intro_no_download(self):
        """
        Test the creation of an introduction point with an unexisting download
        """
        self.tunnel_community.find_download = lambda _: None
        self.tunnel_community.create_introduction_point('a' * 20)
