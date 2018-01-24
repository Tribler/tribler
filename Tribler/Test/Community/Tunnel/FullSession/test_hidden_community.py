from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id
from Tribler.Core.simpledefs import DLSTATUS_SEEDING
from Tribler.Test.Community.Tunnel.FullSession.test_tunnel_base import TestTunnelBase, HiddenTunnelCommunityTests
from Tribler.Test.twisted_thread import deferred


class FakeDHT(object):
    """
    We are bypassing the original DHT in Tribler because that DHT is too unreliable to use for this test.
    """

    def __init__(self, dht_dict):
        self.dht_dict = dht_dict

    def get_peers(self, lookup_id, _, callback_f, bt_port=0):
        """
        This mocked method simply adds a peer to the DHT dictionary and invokes the callback.
        """
        if bt_port != 0:
            self.dht_dict[lookup_id] = self.dht_dict.get(lookup_id, []) + [('127.0.0.1', bt_port)]
        callback_f(lookup_id, self.dht_dict.get(lookup_id, None), None)


class TestHiddenTunnelCommunity(TestTunnelBase):
    """
    This class contains tests for the hidden tunnel community.
    """
    TUNNEL_CLASS = HiddenTunnelCommunityTests

    def setUp(self, autoload_discovery=True):
        TestTunnelBase.setUp(self, autoload_discovery=autoload_discovery)
        self.test_deferred = Deferred()
        self.dht_deferred = Deferred()
        self.dht_dict = {}

    def configure_hidden_seeder(self):
        """
        Setup the hidden seeder. This includes setting the right circuit parameters, creating the download callback and
        waiting for the creation of an introduction point for the download.
        """
        def download_states_callback(dslist):
            self.tunnel_community_seeder.monitor_downloads(dslist)
            return []

        self.tunnel_community_seeder.settings.min_circuits = 0
        self.tunnel_community_seeder.settings.max_circuits = 0
        self.session2.config.set_anon_proxy_settings(
            2, ("127.0.0.1", self.session2.config.get_tunnel_community_socks5_listen_ports()))
        self.session2.set_download_states_callback(download_states_callback)

        # Wait for the introduction point to announce itself to the DHT
        def dht_announce(info_hash, community):
            def cb_dht(info_hash, peers, source):
                self._logger.debug("announced %s to the DHT", info_hash.encode('hex'))
                self.dht_deferred.callback(None)
            port = community.tribler_session.config.get_dispersy_port()
            if not community.tribler_session.lm.mainline_dht:
                community.tribler_session.lm.mainline_dht = FakeDHT(self.dht_dict)
            community.tribler_session.lm.mainline_dht.get_peers(info_hash, Id(info_hash), cb_dht, bt_port=port)

        for community in self.tunnel_communities:
            community.dht_announce = lambda ih, com=community: dht_announce(ih, com)
            community.settings.dht_lookup_interval = 0

        return self.dht_deferred

    def setup_dht_bypass(self):
        for session in self.sessions + [self.session]:
            session.lm.mainline_dht = FakeDHT(self.dht_dict)

    @deferred(timeout=50)
    @inlineCallbacks
    def test_hidden_services(self):
        """
        Testing the hidden services
        """
        yield self.setup_nodes(num_relays=4, num_exitnodes=2, seed_hops=1)
        self.setup_dht_bypass()
        yield self.configure_hidden_seeder()

        def download_state_callback(ds):
            self.tunnel_community.monitor_downloads([ds])
            download = ds.get_download()
            if download.get_progress() == 1.0 and ds.get_status() == DLSTATUS_SEEDING:
                self.test_deferred.callback(None)
                return 0.0, False
            return 2.0, False

        self.tunnel_community.build_tunnels(1)
        from twisted.internet import reactor, task
        while not list(self.tunnel_community.active_data_circuits()):
            yield task.deferLater(reactor, .05, lambda: None)

        download = self.start_anon_download(hops=1)
        download.set_state_callback(download_state_callback)

        yield self.test_deferred
