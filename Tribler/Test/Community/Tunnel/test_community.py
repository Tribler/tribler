from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.exit_socket import MockTunnelExitSocket
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.community.triblerchain.community import TriblerChainCommunity
from Tribler.community.triblertunnel.community import TriblerTunnelCommunity
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import CIRCUIT_TYPE_RENDEZVOUS
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread
from twisted.internet.defer import inlineCallbacks


# Map of info_hash -> peer list
global_dht_services = {}


class MockDHTProvider(object):

    def __init__(self, address):
        self.address = address

    def lookup(self, info_hash, cb):
        if info_hash in global_dht_services:
            cb(info_hash, global_dht_services[info_hash], None)

    def announce(self, info_hash):
        if info_hash in global_dht_services:
            global_dht_services[info_hash].append(self.address)
        else:
            global_dht_services[info_hash] = [self.address]


class TestTriblerTunnelCommunity(TestBase):

    def setUp(self):
        super(TestTriblerTunnelCommunity, self).setUp()
        self.private_nodes = []
        self.initialize(TriblerTunnelCommunity, 1)

    def tearDown(self):
        super(TestTriblerTunnelCommunity, self).tearDown()

        for node in self.private_nodes:
            node.unload()

    def create_node(self):
        mock_ipv8 = MockIPv8(u"curve25519", TriblerTunnelCommunity, socks_listen_ports=[])
        mock_ipv8.overlay._use_main_thread = False

        # Load the TriblerChain community
        overlay = TriblerChainCommunity(mock_ipv8.my_peer, mock_ipv8.endpoint, mock_ipv8.network,
                                        working_directory=u":memory:")
        mock_ipv8.overlay.triblerchain_community = overlay
        mock_ipv8.overlay.dht_provider = MockDHTProvider(mock_ipv8.endpoint.wan_address)

        return mock_ipv8

    @inlineCallbacks
    def create_intro(self, node_nr, service):
        """
        Create an 1 hop introduction point for some node for some service.
        """
        lookup_service = self.nodes[node_nr].overlay.get_lookup_info_hash(service)
        self.nodes[node_nr].overlay.hops[lookup_service] = 1
        self.nodes[node_nr].overlay.create_introduction_point(lookup_service)

        yield self.deliver_messages()

        for node in self.nodes:
            exit_sockets = node.overlay.exit_sockets
            for exit_socket in exit_sockets:
                exit_sockets[exit_socket] = MockTunnelExitSocket(exit_sockets[exit_socket])

    @inlineCallbacks
    def assign_exit_node(self, node_nr):
        """
        Give a node a dedicated exit node to play with.
        """
        exit_node = self.create_node()
        self.private_nodes.append(exit_node)
        exit_node.overlay.settings.become_exitnode = True
        public_peer = Peer(exit_node.my_peer.public_key, exit_node.my_peer.address)
        self.nodes[node_nr].network.add_verified_peer(public_peer)
        self.nodes[node_nr].network.discover_services(public_peer, exit_node.overlay.master_peer.mid)
        self.nodes[node_nr].overlay.update_exit_candidates(public_peer, True)
        self.nodes[node_nr].overlay.build_tunnels(1)
        yield self.deliver_messages()
        exit_sockets = exit_node.overlay.exit_sockets
        for exit_socket in exit_sockets:
            exit_sockets[exit_socket] = MockTunnelExitSocket(exit_sockets[exit_socket])

    @blocking_call_on_reactor_thread
    def test_download_remove(self):
        """
        Test the effects of removing a download in the tunnel community
        """
        self.nodes[0].overlay.num_hops_by_downloads[1] = 1
        mock_download = MockObject()
        mock_download.get_hops = lambda: 1
        self.nodes[0].overlay.on_download_removed(mock_download)

        self.assertEqual(self.nodes[0].overlay.num_hops_by_downloads[1], 0)

    @blocking_call_on_reactor_thread
    def test_readd_bittorrent_peers(self):
        """
        Test the readd bittorrent peers method
        """
        mock_torrent = MockObject()
        mock_torrent.add_peer = lambda _: None
        mock_torrent.tdef = MockObject()
        mock_torrent.tdef.get_infohash = lambda: 'a' * 20
        self.nodes[0].overlay.bittorrent_peers = {mock_torrent: [None]}
        self.nodes[0].overlay.readd_bittorrent_peers()

        self.assertNotIn(mock_torrent, self.nodes[0].overlay.bittorrent_peers)

    @blocking_call_on_reactor_thread
    def test_remove_circuit(self):
        """
        Test removing a circuit
        """

        # Non-existing circuit
        self.nodes[0].overlay.remove_circuit(3)
        self.assertNotIn(3, self.nodes[0].overlay.circuits)

    @blocking_call_on_reactor_thread
    def test_monitor_downloads_stop_ip(self):
        """
        Test whether we stop building IPs when a download doesn't exist anymore
        """
        self.nodes[0].overlay.infohash_ip_circuits['a'] = 3
        self.nodes[0].overlay.download_states['a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertNotIn('a', self.nodes[0].overlay.infohash_ip_circuits)

    @blocking_call_on_reactor_thread
    def test_monitor_downloads_recreate_ip(self):
        """
        Test whether an old introduction point is recreated
        """
        tribler_session = MockObject()
        tribler_session.notifier = MockObject()
        tribler_session.notifier.notify = lambda *_: None
        self.nodes[0].overlay.tribler_session = tribler_session

        mock_state = MockObject()
        mock_download = MockObject()
        mock_tdef = MockObject()
        mock_tdef.get_infohash = lambda: 'a'
        mock_download.get_hops = lambda: 1
        mock_download.get_def = lambda: mock_tdef
        mock_download.add_peer = lambda x: None
        mock_state.get_status = lambda: 1
        mock_state.get_download = lambda: mock_download
        tribler_session.get_downloads = lambda: [mock_download, ]

        real_ih = self.nodes[0].overlay.get_lookup_info_hash('a')
        self.nodes[0].overlay.infohash_ip_circuits[real_ih] = [(3, 0)]
        self.nodes[0].overlay.download_states['a'] = 3
        self.nodes[0].overlay.monitor_downloads([mock_state])
        self.assertNotEqual(self.nodes[0].overlay.infohash_ip_circuits[real_ih][0][1], 0)

    @blocking_call_on_reactor_thread
    def test_monitor_downloads_ih_pex(self):
        """
        Test whether we remove peers from the PEX info when a download is stopped
        """
        self.nodes[0].overlay.infohash_pex['a'] = 3
        self.nodes[0].overlay.download_states['a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertNotIn('a', self.nodes[0].overlay.infohash_pex)

    @blocking_call_on_reactor_thread
    def test_monitor_downloads_intro(self):
        """
        Test whether rendezvous points are removed when a download is stopped
        """
        def mocked_remove_circuit(*_dummy1, **_dummy2):
            mocked_remove_circuit.called = True
        mocked_remove_circuit.called = False

        self.nodes[0].overlay.remove_circuit = mocked_remove_circuit
        self.nodes[0].overlay.my_download_points[3] = ('a',)
        self.nodes[0].overlay.download_states['a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertTrue(mocked_remove_circuit.called)

    @blocking_call_on_reactor_thread
    def test_monitor_downloads_stop_all(self):
        """
        Test whether circuits are removed when all downloads are stopped
        """
        def mocked_remove_circuit(*_dummy1, **_dummy2):
            mocked_remove_circuit.called = True
        mocked_remove_circuit.called = False

        self.nodes[0].overlay.remove_circuit = mocked_remove_circuit
        self.nodes[0].overlay.my_intro_points[3] = ['a']
        self.nodes[0].overlay.download_states['a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertTrue(mocked_remove_circuit.called)

    @blocking_call_on_reactor_thread
    def test_update_torrent(self):
        """
        Test updating a torrent when a circuit breaks
        """
        self.nodes[0].overlay.active_data_circuits = lambda: True
        self.nodes[0].overlay.readd_bittorrent_peers = lambda *_: None
        mock_handle = MockObject()
        mock_handle.get_peer_info = lambda: {2, 3}
        peers = {1, 2}
        self.nodes[0].overlay.update_torrent(peers, mock_handle, 'a')
        self.assertIn('a', self.nodes[0].overlay.bittorrent_peers)

        # Test adding peers
        self.nodes[0].overlay.bittorrent_peers['a'] = {4}
        self.nodes[0].overlay.update_torrent(peers, mock_handle, 'a')

    @twisted_wrapper
    def test_payouts(self):
        """
        Test whether nodes are correctly paid after transferring data
        """
        self.add_node_to_experiment(self.create_node())
        self.add_node_to_experiment(self.create_node())

        # Build a tunnel
        self.nodes[2].overlay.settings.become_exitnode = True
        yield self.introduce_nodes()
        self.nodes[0].overlay.build_tunnels(2)
        yield self.deliver_messages()

        self.assertEqual(self.nodes[0].overlay.tunnels_ready(2), 1.0)

        # Destroy the circuit
        for circuit_id, circuit in self.nodes[0].overlay.circuits.items():
            circuit.bytes_down = 250 * 1024 * 1024
            self.nodes[0].overlay.remove_circuit(circuit_id, destroy=True)

        yield self.deliver_messages()

        # Verify whether the downloader (node 0) correctly paid the relay and exit nodes.
        self.assertTrue(self.nodes[0].overlay.triblerchain_community.get_bandwidth_tokens() < 0)
        self.assertTrue(self.nodes[1].overlay.triblerchain_community.get_bandwidth_tokens() > 0)
        self.assertTrue(self.nodes[2].overlay.triblerchain_community.get_bandwidth_tokens() > 0)

    @twisted_wrapper
    def test_payouts_e2e(self):
        """
        Check if payouts work for an e2e-linked circuit
        """
        self.add_node_to_experiment(self.create_node())
        self.add_node_to_experiment(self.create_node())

        service = '0' * 20

        self.nodes[0].overlay.register_service(service, 1, None, 0)

        yield self.introduce_nodes()
        yield self.create_intro(2, service)
        yield self.assign_exit_node(0)

        self.nodes[0].overlay.do_dht_lookup(service)

        yield self.deliver_messages(timeout=.2)

        # Destroy the e2e-circuit
        for circuit_id, circuit in self.nodes[0].overlay.circuits.items():
            if circuit.ctype == CIRCUIT_TYPE_RENDEZVOUS:
                circuit.bytes_down = 250 * 1024 * 1024
                self.nodes[0].overlay.remove_circuit(circuit_id, destroy=True)

        yield self.deliver_messages()

        # Verify whether the downloader (node 0) correctly paid the subsequent nodes.
        self.assertTrue(self.nodes[0].overlay.triblerchain_community.get_bandwidth_tokens() < 0)
        self.assertTrue(self.nodes[1].overlay.triblerchain_community.get_bandwidth_tokens() > 0)
        self.assertTrue(self.nodes[2].overlay.triblerchain_community.get_bandwidth_tokens() > 0)
