from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.community.triblertunnel.community import TriblerTunnelCommunity
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class TestTriblerTunnelCommunity(TestBase):

    def setUp(self):
        super(TestTriblerTunnelCommunity, self).setUp()
        self.initialize(TriblerTunnelCommunity, 1)

    def create_node(self):
        return MockIPv8(u"curve25519", TriblerTunnelCommunity)

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
        mock_download.add_peer = lambda: None
        mock_state.get_status = lambda: 1
        mock_state.get_download = lambda: mock_download

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
