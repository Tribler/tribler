from __future__ import annotations

import os
from asyncio import TimeoutError as AsyncTimeoutError, wait_for, sleep
from collections import defaultdict
from unittest.mock import Mock

import pytest
from ipv8.keyvault.public.libnaclkey import LibNaCLPK
from ipv8.messaging.anonymization.tunnel import (
    CIRCUIT_STATE_READY,
    CIRCUIT_TYPE_RP_DOWNLOADER,
    CIRCUIT_TYPE_RP_SEEDER,
    PEER_FLAG_EXIT_BT,
)
from ipv8.messaging.serialization import ADDRESS_TYPE_IPV4
from ipv8.peer import Peer
from ipv8.test.base import TestBase
from ipv8.test.messaging.anonymization import test_community
from ipv8.test.messaging.anonymization.test_community import MockDHTProvider
from ipv8.test.mocking.exit_socket import MockTunnelExitSocket
from ipv8.util import succeed

from tribler.core.components.ipv8.adapters_tests import TriblerMockIPv8
from tribler.core.components.tunnel.community.tunnel_community import PEER_FLAG_EXIT_HTTP, TriblerTunnelCommunity
from tribler.core.components.tunnel.settings import TunnelCommunitySettings
from tribler.core.tests.tools.base_test import MockObject
from tribler.core.tests.tools.tracker.http_tracker import HTTPTracker
from tribler.core.utilities.network_utils import NetworkUtils
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import DownloadStatus


@pytest.mark.usefixtures("tmp_path")
class TestTriblerTunnelCommunity(TestBase):  # pylint: disable=too-many-public-methods

    @pytest.fixture(autouse=True)
    def init_tmp(self, tmp_path):
        self.tmp_path = tmp_path

    def setUp(self):
        self.initialize(TriblerTunnelCommunity, 1)
        self.tmp_path = self.tmp_path

    async def tearDown(self):
        test_community.global_dht_services = defaultdict(list)  # Reset the global_dht_services variable
        await super().tearDown()

    def create_node(self, *args, **kwargs):
        config = TunnelCommunitySettings()
        mock_ipv8 = TriblerMockIPv8("curve25519", TriblerTunnelCommunity,
                                    settings={'remove_tunnel_delay': 0},
                                    config=config,
                                    exitnode_cache=Path(self.temporary_directory()) / "exitnode_cache.dat"
                                    )
        mock_ipv8.overlay.settings.max_circuits = 1

        mock_ipv8.overlay.dht_provider = MockDHTProvider(Peer(mock_ipv8.overlay.my_peer.key,
                                                              mock_ipv8.overlay.my_estimated_wan))

        return mock_ipv8

    @staticmethod
    def get_free_port():
        return NetworkUtils(remember_checked_ports_enabled=True).get_random_free_port()

    async def create_intro(self, node_nr, service):
        """
        Create an 1 hop introduction point for some node for some service.
        """
        self.nodes[node_nr].overlay.join_swarm(service, 1, seeding=True)
        self.nodes[node_nr].overlay.create_introduction_point(service)

        await self.deliver_messages()

        for node in self.nodes:
            exit_sockets = node.overlay.exit_sockets
            for circuit_id in exit_sockets:
                exit_sockets[circuit_id] = MockTunnelExitSocket(exit_sockets[circuit_id])

    async def assign_exit_node(self, node_nr):
        """
        Give a node a dedicated exit node to play with.
        """
        exit_node = self.create_node()
        self.nodes.append(exit_node)  # So it could be properly removed on exit
        exit_node.overlay.settings.peer_flags = {PEER_FLAG_EXIT_BT}
        public_peer = Peer(exit_node.my_peer.public_key, exit_node.my_peer.address)
        self.nodes[node_nr].network.add_verified_peer(public_peer)
        self.nodes[node_nr].network.discover_services(public_peer, exit_node.overlay.community_id)
        self.nodes[node_nr].overlay.candidates[public_peer] = exit_node.overlay.settings.peer_flags
        self.nodes[node_nr].overlay.build_tunnels(1)
        await self.deliver_messages()
        exit_sockets = exit_node.overlay.exit_sockets
        for circuit_id in exit_sockets:
            exit_sockets[circuit_id] = MockTunnelExitSocket(exit_sockets[circuit_id])

    async def test_backup_exitnodes(self):
        """
        Check if exitnodes are serialized and deserialized to and from disk properly.
        """
        # 1. Add and exit node
        exit_node = self.create_node()
        exit_node.overlay.settings.peer_flags = {PEER_FLAG_EXIT_BT}
        self.add_node_to_experiment(exit_node)
        self.nodes[0].overlay.candidates[exit_node.my_peer] = exit_node.overlay.settings.peer_flags
        self.assertGreaterEqual(len(self.nodes[0].overlay.get_candidates(PEER_FLAG_EXIT_BT)), 1)
        # 2. Unload
        self.nodes[0].overlay.cache_exitnodes_to_disk()
        self.nodes[0].network.verified_peers = set()
        self.nodes[0].overlay.candidates.clear()
        # 3. Load again
        self.nodes[0].overlay.restore_exitnodes_from_disk()
        # 4. Check if exit node was contacted
        await self.deliver_messages(timeout=0.1)
        self.assertGreaterEqual(len(self.nodes[0].overlay.get_candidates(PEER_FLAG_EXIT_BT)), 1)

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

    def test_monitor_downloads_ignore_hidden(self):
        """
        Test whether hidden downloads get ignored by monitor_downloads.
        """
        mock_state = MockObject()
        mock_download = MockObject()
        mock_download.hidden = True
        mock_download.get_state = lambda: mock_state
        mock_state.get_download = lambda: mock_download

        self.overlay(0).monitor_downloads([mock_state])
        self.assertFalse(self.overlay(0).download_states)

    def test_monitor_downloads_stop_ip(self):
        """
        Test whether we stop building IPs when a download doesn't exist anymore
        """
        mock_circuit = MockObject()
        mock_circuit.circuit_id = 0
        mock_circuit.ctype = 'IP_SEEDER'
        mock_circuit.state = 'READY'
        mock_circuit.info_hash = b'a'
        mock_circuit.goal_hops = 1
        mock_circuit.last_activity = 0

        self.nodes[0].overlay.remove_circuit = Mock()
        self.nodes[0].overlay.circuits[0] = mock_circuit
        self.nodes[0].overlay.join_swarm(b'a', 1)
        self.nodes[0].overlay.download_states[b'a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.nodes[0].overlay.remove_circuit.assert_called_with(0, 'leaving hidden swarm', destroy=4)

    def test_monitor_downloads_recreate_ip(self):
        """
        Test whether an old introduction point is recreated
        """
        mock_state = MockObject()
        mock_download = MockObject()
        mock_tdef = MockObject()
        mock_tdef.get_infohash = lambda: b'a'
        mock_download.hidden = False
        mock_download.get_def = lambda: mock_tdef
        mock_download.add_peer = lambda _: succeed(None)
        mock_download.get_state = lambda: mock_state
        mock_download.config = MockObject()
        mock_download.config.get_hops = lambda: 1
        mock_download.apply_ip_filter = lambda _: None
        mock_state.get_status = lambda: DownloadStatus.SEEDING
        mock_state.get_download = lambda: mock_download

        def mock_create_ip(*_, **__):
            mock_create_ip.called = True

        mock_create_ip.called = False
        self.nodes[0].overlay.create_introduction_point = mock_create_ip

        self.nodes[0].overlay.download_states[b'a'] = DownloadStatus.DOWNLOADING
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
        mock_circuit.last_activity = 0

        self.nodes[0].overlay.remove_circuit = mocked_remove_circuit
        self.nodes[0].overlay.circuits[0] = mock_circuit
        self.nodes[0].overlay.join_swarm(b'a', 1)
        self.nodes[0].overlay.swarms[b'a'].add_connection(mock_circuit, None)
        self.nodes[0].overlay.download_states[b'a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        self.assertEqual(mocked_remove_circuit.circuit_id, 0)

    async def test_monitor_downloads_stop_all(self):
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
        mock_circuit.last_activity = 0

        self.nodes[0].overlay.remove_circuit = mocked_remove_circuit
        self.nodes[0].overlay.circuits[0] = mock_circuit
        self.nodes[0].overlay.join_swarm(b'a', 1)
        self.nodes[0].overlay.download_states[b'a'] = 3
        self.nodes[0].overlay.monitor_downloads([])
        # Since circuit removal is async, we should yield the event loop
        await sleep(0)
        self.assertEqual(mocked_remove_circuit.circuit_id, 0)

    def test_update_ip_filter(self):
        circuit = Mock()
        circuit.circuit_id = 123
        circuit.ctype = CIRCUIT_TYPE_RP_DOWNLOADER
        circuit.state = CIRCUIT_STATE_READY
        circuit.bytes_down = 0
        circuit.last_activity = 0
        circuit.goal_hops = 1
        self.nodes[0].overlay.circuits[circuit.circuit_id] = circuit

        self.nodes[0].overlay.remove_circuit = Mock()

        download = Mock(handle=None)
        download.config.get_hops = lambda: 1
        self.nodes[0].overlay.get_download = lambda _: download

        lt_session = Mock()
        self.nodes[0].overlay.download_manager = Mock()
        self.nodes[0].overlay.download_manager.get_session = lambda _: lt_session
        self.nodes[0].overlay.download_manager.update_ip_filter = Mock()
        self.nodes[0].overlay.download_manager.get_downloads = lambda: [download]

        self.nodes[0].overlay.update_ip_filter(0)
        ips = ['1.1.1.1']
        self.nodes[0].overlay.download_manager.update_ip_filter.assert_called_with(lt_session, ips)

        circuit.ctype = CIRCUIT_TYPE_RP_SEEDER
        self.nodes[0].overlay.update_ip_filter(0)
        ips = [self.nodes[0].overlay.circuit_id_to_ip(circuit.circuit_id), '1.1.1.1']
        self.nodes[0].overlay.download_manager.update_ip_filter.assert_called_with(lt_session, ips)

    def test_update_torrent(self):
        """
        Test updating a torrent when a circuit breaks
        """
        self.nodes[0].overlay.find_circuits = lambda: True
        self.nodes[0].overlay.readd_bittorrent_peers = lambda: None
        mock_handle = MockObject()
        mock_handle.get_peer_info = lambda: {Mock(ip=('2.2.2.2', 2)), Mock(ip=('3.3.3.3', 3))}
        mock_handle.is_valid = lambda: True
        mock_download = MockObject()
        mock_download.handle = mock_handle
        peers = {('1.1.1.1', 1), ('2.2.2.2', 2)}
        self.nodes[0].overlay.update_torrent(peers, mock_download)
        self.assertIn(mock_download, self.nodes[0].overlay.bittorrent_peers)

        # Test adding peers
        self.nodes[0].overlay.bittorrent_peers[mock_download] = {('4.4.4.4', 4)}
        self.nodes[0].overlay.update_torrent(peers, mock_download)

    async def test_circuit_reject_too_many(self):
        """
        Test whether a circuit is rejected by an exit node if it already joined the max number of circuits
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags = {PEER_FLAG_EXIT_BT}
        self.nodes[1].overlay.settings.max_joined_circuits = 0
        await self.introduce_nodes()
        self.nodes[0].overlay.build_tunnels(1)
        await self.deliver_messages()

        self.assertEqual(self.nodes[0].overlay.tunnels_ready(1), 0.0)

    async def test_perform_http_request(self):
        """
        Test whether we can make a http request through a circuit
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags = {PEER_FLAG_EXIT_HTTP}
        await self.introduce_nodes()

        http_port = TestTriblerTunnelCommunity.get_free_port()
        http_tracker = HTTPTracker(http_port)
        http_tracker.tracker_info.add_info_about_infohash('0', 0, 0)
        await http_tracker.start()
        response = await self.nodes[0].overlay.perform_http_request(('127.0.0.1', http_tracker.port),
                                                                    b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n')

        self.assertEqual(response.split(b'\r\n')[0], b'HTTP/1.1 200 OK')
        self.assertEqual(response.split(b'\r\n\r\n')[1],
                         (await http_tracker.handle_scrape_request(Mock(query={'info_hash': '0'}))).body)
        await http_tracker.stop()

    async def test_perform_http_request_multipart(self):
        """
        Test whether getting a large HTTP response works
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags = {PEER_FLAG_EXIT_HTTP}
        await self.introduce_nodes()

        http_port = TestTriblerTunnelCommunity.get_free_port()
        http_tracker = HTTPTracker(http_port)
        http_tracker.tracker_info.add_info_about_infohash('0', 0, 0)
        http_tracker.tracker_info.infohashes['0']['downloaded'] = os.urandom(10000)
        await http_tracker.start()
        response = await self.nodes[0].overlay.perform_http_request(('127.0.0.1', http_tracker.port),
                                                                    b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n')

        self.assertEqual(response.split(b'\r\n')[0], b'HTTP/1.1 200 OK')
        self.assertEqual(response.split(b'\r\n\r\n')[1],
                         (await http_tracker.handle_scrape_request(Mock(query={'info_hash': '0'}))).body)
        await http_tracker.stop()

    async def test_perform_http_request_not_allowed(self):
        """
        Test whether we can make HTTP requests that don't have a bencoded response
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags = {PEER_FLAG_EXIT_HTTP}
        await self.introduce_nodes()

        http_port = TestTriblerTunnelCommunity.get_free_port()
        http_tracker = HTTPTracker(http_port)
        await http_tracker.start()
        with self.assertRaises(AsyncTimeoutError):
            await wait_for(self.nodes[0].overlay.perform_http_request(('127.0.0.1', http_tracker.port),
                                                                      b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n'),
                           timeout=.3)
        await http_tracker.stop()

    async def test_perform_http_request_no_http_exits(self):
        """
        Test whether we can make HTTP requests when we have no exits
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags = set()
        await self.introduce_nodes()

        with self.assertRaises(RuntimeError):
            await self.nodes[0].overlay.perform_http_request(('127.0.0.1', 0),
                                                             b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n')

    async def test_perform_http_request_failed(self):
        """
        Test whether if a failed HTTP request is handled correctly
        """
        self.add_node_to_experiment(self.create_node())
        self.nodes[1].overlay.settings.peer_flags = {PEER_FLAG_EXIT_HTTP}
        await self.introduce_nodes()

        with self.assertRaises(AsyncTimeoutError):
            await wait_for(self.nodes[0].overlay.perform_http_request(('127.0.0.1', 1234),
                                                                      b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n'),
                           timeout=.3)

    def test_cache_exitnodes_to_disk(self):
        """ Test whether we can cache exit nodes to disk """
        self.overlay(0).candidates = {Peer(LibNaCLPK(b'\x00' * 64), ("0.1.2.3", 1029)): {PEER_FLAG_EXIT_BT}}
        self.overlay(0).exitnode_cache = self.tmp_path / 'exitnode_cache.dat'
        self.overlay(0).cache_exitnodes_to_disk()

        assert self.overlay(0).exitnode_cache.read_bytes() == bytes([ADDRESS_TYPE_IPV4]) + bytes(range(6))

    def test_cache_exitnodes_to_disk_os_error(self):
        """ Test whether we can handle an OSError when caching exit nodes to disk and raise no errors """
        self.overlay(0).candidates = {Peer(LibNaCLPK(b'\x00' * 64), ("0.1.2.3", 1029)): {PEER_FLAG_EXIT_BT}}
        self.overlay(0).exitnode_cache = Mock(write_bytes=Mock(side_effect=FileNotFoundError))
        self.overlay(0).cache_exitnodes_to_disk()

        assert self.overlay(0).exitnode_cache.write_bytes.called

    async def test_should_join_circuit(self):
        """ Test whether we can join a circuit"""
        community: TriblerTunnelCommunity = self.overlay(0)
        assert await community.should_join_circuit(create_payload=Mock(), previous_node_address=Mock())
