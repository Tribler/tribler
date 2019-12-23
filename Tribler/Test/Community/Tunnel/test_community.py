from asyncio import Future, sleep
from os.path import join
from tempfile import mkdtemp
from unittest.mock import Mock

from anydex.wallet.tc_wallet import TrustchainWallet

from ipv8.attestation.trustchain.community import TrustChainCommunity
from ipv8.messaging.anonymization.tunnel import CIRCUIT_STATE_READY, CIRCUIT_TYPE_RP_DOWNLOADER, \
    CIRCUIT_TYPE_RP_SEEDER, PEER_FLAG_EXIT_ANY
from ipv8.peer import Peer
from ipv8.test.base import TestBase
from ipv8.test.messaging.anonymization.test_community import MockDHTProvider
from ipv8.test.mocking.exit_socket import MockTunnelExitSocket
from ipv8.test.mocking.ipv8 import MockIPv8

from Tribler.Core.Utilities.utilities import succeed
from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.triblertunnel.community import TriblerTunnelCommunity


class TestTriblerTunnelCommunity(TestBase):

    def setUp(self):
        super(TestTriblerTunnelCommunity, self).setUp()
        self.initialize(TriblerTunnelCommunity, 1)

    def create_node(self):
        mock_ipv8 = MockIPv8(u"curve25519", TriblerTunnelCommunity, socks_listen_ports=[],
                             exitnode_cache=join(mkdtemp(suffix="_tribler_test_cache"), 'cache.dat'))
        mock_ipv8.overlay.settings.max_circuits = 1

        # Load the TrustChain community
        mock_ipv8.trustchain = TrustChainCommunity(mock_ipv8.my_peer, mock_ipv8.endpoint, mock_ipv8.network,
                                      working_directory=u":memory:")
        mock_ipv8.overlay.bandwidth_wallet = TrustchainWallet(mock_ipv8.trustchain)
        mock_ipv8.overlay.dht_provider = MockDHTProvider(Peer(mock_ipv8.overlay.my_peer.key,
                                                              mock_ipv8.overlay.my_estimated_wan))

        return mock_ipv8

    async def create_intro(self, node_nr, service):
        """
        Create an 1 hop introduction point for some node for some service.
        """
        self.nodes[node_nr].overlay.join_swarm(service, 1, seeding=True)
        self.nodes[node_nr].overlay.create_introduction_point(service)

        await self.deliver_messages()

        for node in self.nodes:
            exit_sockets = node.overlay.exit_sockets
            for exit_socket in exit_sockets:
                exit_sockets[exit_socket] = MockTunnelExitSocket(exit_sockets[exit_socket])

    async def assign_exit_node(self, node_nr):
        """
        Give a node a dedicated exit node to play with.
        """
        exit_node = self.create_node()
        self.nodes.append(exit_node) # So it could be properly removed on exit
        exit_node.overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        public_peer = Peer(exit_node.my_peer.public_key, exit_node.my_peer.address)
        self.nodes[node_nr].network.add_verified_peer(public_peer)
        self.nodes[node_nr].network.discover_services(public_peer, exit_node.overlay.master_peer.mid)
        self.nodes[node_nr].overlay.candidates[public_peer] = exit_node.overlay.settings.peer_flags
        self.nodes[node_nr].overlay.build_tunnels(1)
        await self.deliver_messages()
        exit_sockets = exit_node.overlay.exit_sockets
        for exit_socket in exit_sockets:
            exit_sockets[exit_socket] = MockTunnelExitSocket(exit_sockets[exit_socket])

    async def test_backup_exitnodes(self):
        """
        Check if exitnodes are serialized and deserialized to and from disk properly.
        """
        # 1. Add and exit node
        exit_node = self.create_node()
        exit_node.overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        self.add_node_to_experiment(exit_node)
        self.nodes[0].overlay.candidates[exit_node.my_peer] = exit_node.overlay.settings.peer_flags
        self.assertGreaterEqual(len(self.nodes[0].overlay.get_candidates(PEER_FLAG_EXIT_ANY)), 1)
        # 2. Unload
        self.nodes[0].overlay.cache_exitnodes_to_disk()
        self.nodes[0].network.verified_peers = []
        self.nodes[0].overlay.candidates.clear()
        # 3. Load again
        self.nodes[0].overlay.restore_exitnodes_from_disk()
        # 4. Check if exit node was contacted
        await self.deliver_messages()
        self.assertGreaterEqual(len(self.nodes[0].overlay.get_candidates(PEER_FLAG_EXIT_ANY)), 1)

    def test_readd_bittorrent_peers(self):
        """
        Test the readd bittorrent peers method
        """
        mock_torrent = MockObject()
        mock_torrent.add_peer = lambda _: succeed(None)
        mock_torrent.tdef = MockObject()
        mock_torrent.tdef.get_infohash = lambda: b'a' * 20
        self.nodes[0].overlay.bittorrent_peers = {mock_torrent: [None]}
        self.nodes[0].overlay.readd_bittorrent_peers()

        self.assertNotIn(mock_torrent, self.nodes[0].overlay.bittorrent_peers)

    def test_remove_circuit(self):
        """
        Test removing a circuit
        """

        # Non-existing circuit
        self.nodes[0].overlay.remove_circuit(3)
        self.assertNotIn(3, self.nodes[0].overlay.circuits)

    def test_monitor_downloads_stop_ip(self):
        """
        Test whether we stop building IPs when a download doesn't exist anymore
        """
        def mocked_remove_circuit(circuit_id, *_, **__):
            mocked_remove_circuit.circuit_id = circuit_id
        mocked_remove_circuit.circuit_id = -1

        mock_circuit = MockObject()
        mock_circuit.circuit_id = 0
        mock_circuit.ctype = 'IP_SEEDER'
        mock_circuit.state = 'READY'
        mock_circuit.info_hash = b'a'
        mock_circuit.goal_hops = 1

        self.nodes[0].overlay.remove_circuit = mocked_remove_circuit
        self.nodes[0].overlay.circuits[0] = mock_circuit
        self.nodes[0].overlay.join_swarm(b'a', 1)
        self.nodes[0].overlay.download_states[b'a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertEqual(mocked_remove_circuit.circuit_id, 0)

    def test_monitor_downloads_recreate_ip(self):
        """
        Test whether an old introduction point is recreated
        """
        mock_state = MockObject()
        mock_download = MockObject()
        mock_tdef = MockObject()
        mock_tdef.get_infohash = lambda: b'a'
        mock_download.get_def = lambda: mock_tdef
        mock_download.add_peer = lambda _: succeed(None)
        mock_download.get_state = lambda: mock_state
        mock_download.config = MockObject()
        mock_download.config.get_hops = lambda: 1
        mock_download.apply_ip_filter = lambda _: None
        mock_state.get_status = lambda: 4
        mock_state.get_download = lambda: mock_download

        def mock_create_ip(*_, **__):
            mock_create_ip.called = True
        mock_create_ip.called = False
        self.nodes[0].overlay.create_introduction_point = mock_create_ip

        self.nodes[0].overlay.download_states[b'a'] = 3
        self.nodes[0].overlay.monitor_downloads([mock_state])
        self.assertTrue(mock_create_ip.called)

    def test_monitor_downloads_leave_swarm(self):
        """
        Test whether we leave the swarm when a download is stopped
        """
        self.nodes[0].overlay.swarms[b'a'] = None
        self.nodes[0].overlay.download_states[b'a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertNotIn(b'a', self.nodes[0].overlay.swarms)

    def test_monitor_downloads_intro(self):
        """
        Test whether rendezvous points are removed when a download is stopped
        """
        def mocked_remove_circuit(circuit_id, *_, **__):
            mocked_remove_circuit.circuit_id = circuit_id
        mocked_remove_circuit.circuit_id = -1

        mock_circuit = MockObject()
        mock_circuit.circuit_id = 0
        mock_circuit.ctype = 'RP_DOWNLOADER'
        mock_circuit.state = 'READY'
        mock_circuit.info_hash = b'a'
        mock_circuit.goal_hops = 1

        self.nodes[0].overlay.remove_circuit = mocked_remove_circuit
        self.nodes[0].overlay.circuits[0] = mock_circuit
        self.nodes[0].overlay.join_swarm(b'a', 1)
        self.nodes[0].overlay.swarms[b'a'].add_connection(mock_circuit, None)
        self.nodes[0].overlay.download_states[b'a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertEqual(mocked_remove_circuit.circuit_id, 0)

    def test_monitor_downloads_stop_all(self):
        """
        Test whether circuits are removed when all downloads are stopped
        """
        def mocked_remove_circuit(circuit_id, *_, **__):
            mocked_remove_circuit.circuit_id = circuit_id
        mocked_remove_circuit.circuit_id = -1

        mock_circuit = MockObject()
        mock_circuit.circuit_id = 0
        mock_circuit.ctype = 'DATA'
        mock_circuit.state = 'READY'
        mock_circuit.info_hash = b'a'
        mock_circuit.goal_hops = 1

        self.nodes[0].overlay.remove_circuit = mocked_remove_circuit
        self.nodes[0].overlay.circuits[0] = mock_circuit
        self.nodes[0].overlay.join_swarm(b'a', 1)
        self.nodes[0].overlay.download_states[b'a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertEqual(mocked_remove_circuit.circuit_id, 0)

    def test_update_ip_filter(self):
        circuit = Mock()
        circuit.circuit_id = 123
        circuit.ctype = CIRCUIT_TYPE_RP_DOWNLOADER
        circuit.state = CIRCUIT_STATE_READY
        circuit.bytes_down = 0
        self.nodes[0].overlay.circuits[circuit.circuit_id] = circuit

        download = Mock()
        download.config.get_hops = lambda: 1
        self.nodes[0].overlay.get_download = lambda _: download

        lt_session = Mock()
        self.nodes[0].overlay.tribler_session = Mock()
        self.nodes[0].overlay.tribler_session.ltmgr.get_session = lambda _: lt_session
        self.nodes[0].overlay.tribler_session.ltmgr.update_ip_filter = Mock()

        self.nodes[0].overlay.update_ip_filter(0)
        ips = ['1.1.1.1']
        self.nodes[0].overlay.tribler_session.ltmgr.update_ip_filter.assert_called_with(lt_session, ips)

        circuit.ctype = CIRCUIT_TYPE_RP_SEEDER
        self.nodes[0].overlay.update_ip_filter(0)
        ips = [self.nodes[0].overlay.circuit_id_to_ip(circuit.circuit_id), '1.1.1.1']
        self.nodes[0].overlay.tribler_session.ltmgr.update_ip_filter.assert_called_with(lt_session, ips)

    async def test_update_torrent(self):
        """
        Test updating a torrent when a circuit breaks
        """
        self.nodes[0].overlay.find_circuits = lambda: True
        self.nodes[0].overlay.readd_bittorrent_peers = lambda: None
        mock_handle = MockObject()
        mock_handle.get_peer_info = lambda: {2, 3}
        mock_download = MockObject()
        mock_download.get_handle = lambda: succeed(mock_handle)
        peers = {1, 2}
        await self.nodes[0].overlay.update_torrent(peers, mock_download)
        self.assertIn(mock_download, self.nodes[0].overlay.bittorrent_peers)

        # Test adding peers
        self.nodes[0].overlay.bittorrent_peers[mock_download] = {4}
        await self.nodes[0].overlay.update_torrent(peers, mock_download)

    async def test_payouts(self):
        """
        Test whether nodes are correctly paid after transferring data
        """
        self.add_node_to_experiment(self.create_node())
        self.add_node_to_experiment(self.create_node())

        # Build a tunnel
        self.nodes[2].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()
        self.nodes[0].overlay.build_tunnels(2)
        await self.deliver_messages(timeout=.5)

        self.assertEqual(self.nodes[0].overlay.tunnels_ready(2), 1.0)

        # Destroy the circuit
        for circuit_id, circuit in self.nodes[0].overlay.circuits.items():
            circuit.bytes_down = 250 * 1024 * 1024
            self.nodes[0].overlay.remove_circuit(circuit_id, destroy=True)

        await sleep(0.5)

        # Verify whether the downloader (node 0) correctly paid the relay and exit nodes.
        self.assertTrue(self.nodes[0].overlay.bandwidth_wallet.get_bandwidth_tokens() < 0)
        self.assertTrue(self.nodes[1].overlay.bandwidth_wallet.get_bandwidth_tokens() > 0)
        self.assertTrue(self.nodes[2].overlay.bandwidth_wallet.get_bandwidth_tokens() > 0)

    async def test_circuit_reject_too_many(self):
        """
        Test whether a circuit is rejected by an exit node if it already joined the max number of circuits
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        self.nodes[1].overlay.settings.max_joined_circuits = 0
        await self.introduce_nodes()
        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages()

        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 0.0)

    async def test_payouts_e2e(self):
        """
        Check if payouts work for an e2e-linked circuit
        """
        self.add_node_to_experiment(self.create_node())
        self.add_node_to_experiment(self.create_node())

        service = b'0' * 20

        self.nodes[0].overlay.join_swarm(service, 1, seeding=False)

        await self.introduce_nodes()
        await self.create_intro(2, service)
        await self.assign_exit_node(0)

        await self.nodes[0].overlay.do_peer_discovery()

        await self.deliver_messages(timeout=0.5)

        # Destroy the e2e-circuit
        removed_circuits = []
        for circuit_id, circuit in self.nodes[0].overlay.circuits.items():
            if circuit.ctype == CIRCUIT_TYPE_RP_DOWNLOADER:
                circuit.bytes_down = 250 * 1024 * 1024
                self.nodes[0].overlay.remove_circuit(circuit_id, destroy=True)
                removed_circuits.append(circuit_id)

        await sleep(0.5)

        # Verify whether the downloader (node 0) correctly paid the subsequent nodes.
        self.assertTrue(self.nodes[0].overlay.bandwidth_wallet.get_bandwidth_tokens() < 0)
        self.assertTrue(self.nodes[1].overlay.bandwidth_wallet.get_bandwidth_tokens() >= 0)
        self.assertTrue(self.nodes[2].overlay.bandwidth_wallet.get_bandwidth_tokens() > 0)

        # Ensure balances remain unchanged after calling remove_circuit a second time
        balances = [self.nodes[i].overlay.bandwidth_wallet.get_bandwidth_tokens() for i in range(3)]
        for circuit_id in removed_circuits:
            self.nodes[0].overlay.remove_circuit(circuit_id, destroy=True)
        for i in range(3):
            self.assertEqual(self.nodes[i].overlay.bandwidth_wallet.get_bandwidth_tokens(), balances[i])

    async def test_payouts_invalid_block(self):
        """
        Test whether we do not payout if we received an invalid payout block
        """
        self.add_node_to_experiment(self.create_node())

        # Build a tunnel
        self.nodes[1].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()
        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages(timeout=.5)

        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 1.0)

        # Perform an invalid payout
        payout_amount = -250 * 1024 * 1024
        self.nodes[0].overlay.do_payout(self.nodes[1].my_peer, 1234, payout_amount, 1)

        await self.deliver_messages(timeout=.5)

        # Node 1 should not have counter-signed this block and thus not received tokens
        self.assertFalse(self.nodes[1].overlay.bandwidth_wallet.get_bandwidth_tokens())

    async def test_decline_competing_slot(self):
        """
        Test whether a circuit is not created when a node does not have enough balance for a competing slot
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()
        self.nodes[1].overlay.random_slots = []
        self.nodes[1].overlay.competing_slots = [(1000, 1234)]
        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages()

        # Assert whether we didn't create the circuit
        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 0.0)

    async def test_win_competing_slot(self):
        """
        Test whether a circuit is created when a node has enough balance for a competing slot
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()
        self.nodes[1].overlay.random_slots = []
        self.nodes[1].overlay.competing_slots = [(-1000, 1234)]
        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages()

        # Assert whether we didn't create the circuit
        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 1.0)

    async def test_empty_competing_slot(self):
        """
        Test whether a circuit is created when a node takes an empty competing slot
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()
        self.nodes[1].overlay.random_slots = []
        self.nodes[1].overlay.competing_slots = [(0, None)]
        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages()

        # Assert whether we did create the circuit
        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 1.0)

    async def test_win_competing_slot_exit(self):
        """
        Test whether a two-hop circuit is created when a node has enough balance for a competing slot at the exit
        """
        self.add_node_to_experiment(self.create_node())
        self.add_node_to_experiment(self.create_node())
        self.nodes[2].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()
        self.nodes[2].overlay.random_slots = []
        self.nodes[2].overlay.competing_slots = [(-1000, 1234)]
        self.nodes[0].overlay.build_tunnels(2)
        await self.deliver_messages()

        # Assert whether we did create the circuit
        self.assertEqual(self.nodes[0].overlay.tunnels_ready(2), 1.0)

    async def test_win_competing_slot_relay(self):
        """
        Test whether a two-hop circuit is created when a node has enough balance for a competing slot
        """
        self.add_node_to_experiment(self.create_node())
        self.add_node_to_experiment(self.create_node())
        self.nodes[2].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()
        self.nodes[1].overlay.random_slots = []
        self.nodes[1].overlay.competing_slots = [(-1000, 1234)]
        self.nodes[0].overlay.build_tunnels(2)
        await self.deliver_messages()

        # Assert whether we did create the circuit
        self.assertEqual(self.nodes[0].overlay.tunnels_ready(2), 1.0)

    async def test_payout_on_competition_kick(self):
        """
        Test whether a payout is initiated when an existing node is kicked out from a competing slot
        """
        self.add_node_to_experiment(self.create_node())
        self.add_node_to_experiment(self.create_node())
        self.nodes[2].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()

        # Make sure that there's a token disbalance between node 0 and 1
        his_pubkey = self.nodes[1].overlay.my_peer.public_key.key_to_bin()
        await self.nodes[0].overlay.bandwidth_wallet.trustchain.sign_block(
            self.nodes[1].overlay.my_peer, public_key=his_pubkey,
            block_type=b'tribler_bandwidth', transaction={b'up': 0, b'down': 1024 * 1024})

        self.nodes[2].overlay.random_slots = []
        self.nodes[2].overlay.competing_slots = [(0, None)]
        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages()

        # Let some artificial data flow over the circuit
        list(self.nodes[0].overlay.circuits.values())[0].bytes_down = 250 * 1024 * 1024

        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 1.0)
        self.assertTrue(self.nodes[2].overlay.exit_sockets)

        self.nodes[1].overlay.build_tunnels(1)
        await self.deliver_messages()
        self.assertTrue(self.nodes[2].overlay.exit_sockets)
        self.assertEqual(self.nodes[1].overlay.tunnels_ready(1), 1.0)

        # Check whether the exit node has been paid
        self.assertGreaterEqual(self.nodes[2].overlay.bandwidth_wallet.get_bandwidth_tokens(), 250 * 1024 * 1024)

    async def test_create_circuit_without_wallet(self):
        """
        Test whether creating a circuit without bandwidth wallet, fails
        """
        self.add_node_to_experiment(self.create_node())
        await self.nodes[0].overlay.bandwidth_wallet.shutdown_task_manager()
        self.nodes[0].overlay.bandwidth_wallet = None
        self.nodes[1].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()

        # Initialize the slots
        self.nodes[1].overlay.random_slots = []
        self.nodes[1].overlay.competing_slots = [(0, None)]

        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages()

        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 0.0)

    async def test_reject_callback(self):
        """
        Test whether the rejection callback is correctly invoked when a circuit request is rejected
        """
        reject_future = Future()
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags |= PEER_FLAG_EXIT_ANY
        await self.introduce_nodes()

        # Make sure that there's a token disbalance between node 0 and 1
        his_pubkey = self.nodes[1].overlay.my_peer.public_key.key_to_bin()
        await self.nodes[0].overlay.bandwidth_wallet.trustchain.sign_block(
            self.nodes[1].overlay.my_peer, public_key=his_pubkey,
            block_type=b'tribler_bandwidth', transaction={b'up': 0, b'down': 1024 * 1024})

        def on_reject(_, balance):
            self.assertEqual(balance, -1024 * 1024)
            reject_future.set_result(None)

        self.nodes[1].overlay.reject_callback = on_reject

        # Initialize the slots
        self.nodes[1].overlay.random_slots = []
        self.nodes[1].overlay.competing_slots = [(100000000, 12345)]

        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages()

        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 0.0)

        # Node 0 should be rejected and the reject callback should be invoked by node 1
        await reject_future
