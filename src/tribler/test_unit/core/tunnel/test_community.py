from __future__ import annotations

from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import gather, sleep, wait_for
from collections import defaultdict
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, call, patch

from ipv8.keyvault.public.libnaclkey import LibNaCLPK
from ipv8.messaging.anonymization.tunnel import (
    CIRCUIT_STATE_CLOSING,
    CIRCUIT_TYPE_IP_SEEDER,
    CIRCUIT_TYPE_RP_DOWNLOADER,
    CIRCUIT_TYPE_RP_SEEDER,
    PEER_FLAG_EXIT_BT,
    Circuit,
)
from ipv8.messaging.serialization import ADDRESS_TYPE_IPV4
from ipv8.peer import Peer
from ipv8.test.base import TestBase
from ipv8.test.messaging.anonymization import mock as dht_mocks
from ipv8.test.messaging.anonymization.mock import MockDHTProvider
from ipv8.test.mocking.endpoint import AutoMockEndpoint
from ipv8.test.mocking.exit_socket import MockTunnelExitSocket
from ipv8.test.mocking.ipv8 import MockIPv8
from ipv8.util import succeed

import tribler
from tribler.core.libtorrent.download_manager.download_state import DownloadStatus
from tribler.core.notifier import Notifier
from tribler.core.tunnel.community import PEER_FLAG_EXIT_HTTP, TriblerTunnelCommunity, TriblerTunnelSettings

if TYPE_CHECKING:
    from ipv8.community import CommunitySettings


class TestTriblerTunnelCommunity(TestBase[TriblerTunnelCommunity]):
    """
    Tests for the TriblerTunnelCommunity class.
    """

    def setUp(self) -> None:
        """
        Create a new TriblerTunnelCommunity.
        """
        super().setUp()
        self.fake_cache_file = BytesIO()
        self.fake_cache_file.read = self.fake_cache_file.getvalue
        self.initialize(TriblerTunnelCommunity, 1)

    async def tearDown(self) -> None:
        """
        Reset the global_dht_services variable.
        """
        dht_mocks.global_dht_services = defaultdict(list)
        await super().tearDown()

    def create_node(self, settings: CommunitySettings | None = None, create_dht: bool = False,
                    enable_statistics: bool = False) -> MockIPv8:
        """
        Set up a fake dht provider.
        """
        exit_cache = Mock(open=Mock(return_value=Mock(__enter__=Mock(return_value=self.fake_cache_file),
                                                      __exit__=Mock())),
                          write_bytes=self.fake_cache_file.write)
        config = TriblerTunnelSettings(remove_tunnel_delay=0, max_circuits=1, socks_servers=[], notifier=Notifier(),
                                       exitnode_cache=exit_cache, download_manager=None)
        mock_ipv8 = MockIPv8("curve25519", TriblerTunnelCommunity, config)
        config.dht_provider = MockDHTProvider(Peer(mock_ipv8.overlay.my_peer.key, mock_ipv8.overlay.my_estimated_wan))
        mock_ipv8.overlay.cancel_all_pending_tasks()
        return mock_ipv8

    async def create_intro(self, i: int, service: bytes) -> None:
        """
        Create an 1 hop introduction point for some node for some service.
        """
        self.overlay(i).join_swarm(service, 1, seeding=True)
        self.overlay(i).create_introduction_point(service)

        await self.deliver_messages()

        for node in self.nodes:
            exit_sockets = node.overlay.exit_sockets
            for circuit_id in exit_sockets:
                exit_sockets[circuit_id] = MockTunnelExitSocket(exit_sockets[circuit_id])

    async def assign_exit_node(self, i: int) -> None:
        """
        Give a node a dedicated exit node to play with.
        """
        exit_node = self.create_node()
        self.nodes.append(exit_node)  # So it could be properly removed on exit
        exit_node.overlay.settings.peer_flags = {PEER_FLAG_EXIT_BT}
        public_peer = Peer(exit_node.my_peer.public_key, exit_node.my_peer.address)
        self.network(i).add_verified_peer(public_peer)
        self.network(i).discover_services(public_peer, exit_node.overlay.community_id)
        self.overlay(i).candidates[public_peer] = exit_node.overlay.settings.peer_flags
        self.overlay(i).build_tunnels(1)
        await self.deliver_messages()
        exit_sockets = exit_node.overlay.exit_sockets
        for circuit_id in exit_sockets:
            exit_sockets[circuit_id] = MockTunnelExitSocket(exit_sockets[circuit_id])

    async def test_backup_exitnodes(self) -> None:
        """
        Check if exitnodes are serialized and deserialized to and from disk properly.
        """
        # 1. Add and exit node
        exit_node = self.create_node()
        exit_node.overlay.settings.peer_flags.add(PEER_FLAG_EXIT_BT)
        self.add_node_to_experiment(exit_node)
        self.overlay(0).candidates[exit_node.my_peer] = exit_node.overlay.settings.peer_flags
        self.assertGreaterEqual(len(self.nodes[0].overlay.get_candidates(PEER_FLAG_EXIT_BT)), 1)

        # 2. Unload
        self.overlay(0).cache_exitnodes_to_disk()
        self.network(0).verified_peers = set()
        self.overlay(0).candidates.clear()

        # 3. Load again
        self.overlay(0).restore_exitnodes_from_disk()

        # 4. Check if exit node was contacted
        await self.deliver_messages(timeout=0.1)

        self.assertGreaterEqual(len(self.overlay(0).get_candidates(PEER_FLAG_EXIT_BT)), 1)

    def test_readd_bittorrent_peers(self) -> None:
        """
        Test the readd bittorrent peers method.
        """
        mock_torrent = Mock(add_peer=Mock(return_value=succeed(None)),
                            tdef=Mock(get_infohash=Mock(return_value=b'a' * 20)))
        self.overlay(0).bittorrent_peers = {mock_torrent: [None]}

        self.overlay(0).readd_bittorrent_peers()

        self.assertNotIn(mock_torrent, self.overlay(0).bittorrent_peers)

    async def test_remove_non_existing_circuit(self) -> None:
        """
        Test removing a non-existing circuit.
        """
        await self.overlay(0).remove_circuit(3, remove_now=True)

        self.assertNotIn(3, self.overlay(0).circuits)

    async def test_remove_existing_circuit(self) -> None:
        """
        Test removing an existing circuit.
        """
        self.overlay(0).circuits[3] = Circuit(3)

        await self.overlay(0).remove_circuit(3, remove_now=True)

        self.assertNotIn(3, self.overlay(0).circuits)

    async def test_remove_existing_circuit_later(self) -> None:
        """
        Test removing an existing circuit.
        """
        circuit = Circuit(3)
        circuit.add_hop(Mock())
        self.overlay(0).circuits[3] = circuit
        self.overlay(0).settings.remove_tunnel_delay = 5.0

        _ = self.overlay(0).remove_circuit(3, remove_now=False)

        self.assertIn(3, self.overlay(0).circuits)
        self.assertEqual(CIRCUIT_STATE_CLOSING, circuit.state)

    def test_monitor_downloads_ignore_hidden(self) -> None:
        """
        Test if hidden downloads get ignored by monitor_downloads.
        """
        mock_state = Mock()
        mock_download = Mock(hidden=True, get_state=Mock(return_value=mock_state))
        mock_state.get_download = lambda: mock_download

        self.overlay(0).monitor_downloads([mock_state])

        self.assertFalse(self.overlay(0).download_states)

    async def test_monitor_downloads_stop_ip(self) -> None:
        """
        Test if we stop building IPs when a download doesn't exist anymore.
        """
        self.overlay(0).settings.download_manager = Mock(get_last_download_states=Mock(return_value=[]),
                                                         get_downloads=Mock(return_value=[]))
        circuit = Circuit(0, 1, CIRCUIT_TYPE_IP_SEEDER, info_hash=b'a')
        remote_endpoint = AutoMockEndpoint()
        circuit.add_hop(Mock(address=remote_endpoint.get_address()))
        circuit.last_activity = 0

        self.overlay(0).circuits[0] = circuit
        self.overlay(0).join_swarm(b'a', 1)
        self.overlay(0).download_states[b'a'] = 3

        self.overlay(0).monitor_downloads([])
        await gather(*self.overlay(0).get_anonymous_tasks("remove_circuit"))

        self.assertNotIn(0, self.overlay(0).circuits)

    def test_monitor_downloads_recreate_ip(self) -> None:
        """
        Test if an old introduction point is recreated.
        """
        mock_state = Mock(get_status=Mock(return_value=DownloadStatus.SEEDING))
        mock_tdef = Mock(get_infohash=Mock(return_value=b'a'))
        mock_download = Mock(get_def=Mock(return_value=mock_tdef), add_peer=Mock(return_value=succeed(None)),
                             get_state=Mock(return_value=mock_state), config=Mock(get_hops=Mock(return_value=1)),
                             apply_ip_filter=Mock(return_value=None))
        mock_state.get_download = Mock(return_value=mock_download)
        self.overlay(0).create_introduction_point = Mock()
        self.overlay(0).download_states[b'a'] = DownloadStatus.DOWNLOADING

        self.overlay(0).monitor_downloads([mock_state])

        self.assertEqual(call(self.overlay(0).get_lookup_info_hash(b'a')),
                         self.overlay(0).create_introduction_point.call_args)

    def test_monitor_downloads_leave_swarm(self) -> None:
        """
        Test if we leave the swarm when a download is stopped.
        """
        self.overlay(0).swarms[b'a'] = None
        self.overlay(0).download_states[b'a'] = 3

        self.overlay(0).monitor_downloads([])

        self.assertNotIn(b'a', self.overlay(0).swarms)

    async def test_monitor_downloads_intro(self) -> None:
        """
        Test if rendezvous points are removed when a download is stopped.
        """
        self.overlay(0).settings.download_manager = Mock(get_last_download_states=Mock(return_value=[]),
                                                         get_downloads=Mock(return_value=[]))
        circuit = Circuit(0, 1, CIRCUIT_TYPE_RP_DOWNLOADER, info_hash=b"a")
        remote_endpoint = AutoMockEndpoint()
        circuit.add_hop(Mock(address=remote_endpoint.get_address()))
        circuit.last_activity = 0

        self.overlay(0).circuits[0] = circuit
        self.overlay(0).join_swarm(b'a', 1)
        self.overlay(0).swarms[b'a'].add_connection(circuit, None)
        self.overlay(0).download_states[b'a'] = 3

        self.overlay(0).monitor_downloads([])
        await gather(*self.overlay(0).get_anonymous_tasks("remove_circuit"))

        self.assertNotIn(0, self.overlay(0).circuits)

    async def test_monitor_downloads_stop_all(self) -> None:
        """
        Test if circuits are removed when all downloads are stopped.
        """
        self.overlay(0).settings.download_manager = Mock(get_last_download_states=Mock(return_value=[]),
                                                         get_downloads=Mock(return_value=[]))
        circuit = Circuit(0, 1, CIRCUIT_TYPE_RP_DOWNLOADER, info_hash=b"a")
        remote_endpoint = AutoMockEndpoint()
        circuit.add_hop(Mock(address=remote_endpoint.get_address()))

        self.overlay(0).circuits[0] = circuit
        self.overlay(0).join_swarm(b"a", 1)
        self.overlay(0).download_states[b"a"] = 3

        self.overlay(0).monitor_downloads([])
        await gather(*self.overlay(0).get_anonymous_tasks("remove_circuit"))

        self.assertNotIn(0, self.overlay(0).circuits)

    async def test_update_ip_filter(self) -> None:
        """
        Test if the ip filter is updated properly.
        """
        circuit = Circuit(123, 1, CIRCUIT_TYPE_RP_DOWNLOADER)
        remote_endpoint = AutoMockEndpoint()
        circuit.add_hop(Mock(address=remote_endpoint.get_address()))
        circuit.bytes_down = 0
        circuit.last_activity = 0
        self.overlay(0).circuits[circuit.circuit_id] = circuit

        download = Mock(handle=None, config=Mock(get_hops=Mock(return_value=1)))
        self.overlay(0).get_download = Mock(return_value=download)

        lt_session = Mock()
        self.overlay(0).settings.download_manager = Mock(get_session=Mock(return_value=lt_session),
                                                         update_ip_filter=Mock(),
                                                         get_downloads=Mock(return_value=[download]))

        self.overlay(0).update_ip_filter(0)
        self.overlay(0).settings.download_manager.update_ip_filter.assert_called_with(lt_session, [])

        circuit.ctype = CIRCUIT_TYPE_RP_SEEDER
        self.overlay(0).update_ip_filter(0)
        ips = [self.overlay(0).circuit_id_to_ip(circuit.circuit_id)]

        self.overlay(0).settings.download_manager.update_ip_filter.assert_called_with(lt_session, ips)

    def test_update_torrent(self) -> None:
        """
        Test updating a torrent when a circuit breaks.
        """
        self.overlay(0).find_circuits = Mock(return_value=True)
        self.overlay(0).readd_bittorrent_peers = Mock(return_value=None)
        download = Mock(handle=Mock(get_peer_info=Mock(return_value={Mock(ip=('2.2.2.2', 2)), Mock(ip=('3.3.3.3', 3))}),
                                    is_valid=Mock(return_value=True)))
        peers = {('1.1.1.1', 1), ('2.2.2.2', 2)}
        self.overlay(0).update_torrent(peers, download)
        self.assertIn(download, self.nodes[0].overlay.bittorrent_peers)

        # Test adding peers
        self.overlay(0).bittorrent_peers[download] = {('4.4.4.4', 4)}
        self.overlay(0).update_torrent(peers, download)

    async def test_circuit_reject_too_many(self) -> None:
        """
        Test if a circuit is rejected by an exit node if it already joined the max number of circuits.
        """
        self.add_node_to_experiment(self.create_node())
        self.overlay(1).settings.peer_flags = {PEER_FLAG_EXIT_BT}
        self.overlay(1).settings.max_joined_circuits = 0
        await self.introduce_nodes()

        self.overlay(0).build_tunnels(1)
        await self.deliver_messages()

        self.assertEqual(self.overlay(0).tunnels_ready(1), 0.0)

    async def test_perform_http_request(self) -> None:
        """
        Test if we can make a http request through a circuit.
        """
        remote_endpoint = AutoMockEndpoint()
        writer = Mock()
        reader = Mock(readline=AsyncMock(side_effect=[b"HTTP/1.1 200 OK\r\n", b"\r\n"]),
                      read=AsyncMock(return_value=b"i11e\r\n"))
        open_connection = AsyncMock(return_value=(reader, writer))

        self.add_node_to_experiment(self.create_node())
        self.overlay(1).settings.peer_flags = {PEER_FLAG_EXIT_HTTP}
        await self.introduce_nodes()
        self.overlay(0).create_circuit(1, exit_flags=[PEER_FLAG_EXIT_HTTP])
        await sleep(0)

        with patch.dict(tribler.core.tunnel.community.__dict__, {"open_connection": open_connection}):
            response = await self.overlay(0).perform_http_request(remote_endpoint.get_address(),
                                                                  b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n')

        self.assertEqual(response.split(b'\r\n')[0], b'HTTP/1.1 200 OK')

    async def test_perform_http_request_not_allowed(self) -> None:
        """
        Test if we can't make HTTP requests that don't have a bencoded response.
        """
        remote_endpoint = AutoMockEndpoint()
        writer = Mock()
        reader = Mock(readline=AsyncMock(side_effect=[b"HTTP/1.1 200 OK\r\n", b"\r\n"]),
                      read=AsyncMock(return_value=b"\r\n"))
        open_connection = AsyncMock(return_value=(reader, writer))

        self.add_node_to_experiment(self.create_node())
        self.overlay(1).settings.peer_flags = {PEER_FLAG_EXIT_HTTP}
        await self.introduce_nodes()
        self.overlay(0).create_circuit(1, exit_flags=[PEER_FLAG_EXIT_HTTP])
        await sleep(0)
        await gather(*self.overlay(1).get_anonymous_tasks("on_packet_from_circuit"))

        with patch.dict(tribler.core.tunnel.community.__dict__, {"open_connection": open_connection}),\
                self.assertRaises(AsyncTimeoutError):
            await wait_for(self.overlay(0).perform_http_request(remote_endpoint.get_address(),
                                                                b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n'),
                           timeout=.05)

    async def test_perform_http_request_no_http_exits(self) -> None:
        """
        Test if we can't make HTTP requests when we have no exits.
        """
        remote_endpoint = AutoMockEndpoint()
        self.add_node_to_experiment(self.create_node())
        self.overlay(1).settings.peer_flags = set()
        await self.introduce_nodes()

        with self.assertRaises(RuntimeError), self.overlay(0).request_cache.passthrough():
            await self.overlay(0).perform_http_request(remote_endpoint.get_address(),
                                                       b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n')

    async def test_perform_http_request_failed(self) -> None:
        """
        Test if a HTTP request raises a timeout error when the request times out.
        """
        remote_endpoint = AutoMockEndpoint()
        self.add_node_to_experiment(self.create_node())
        self.overlay(1).settings.peer_flags = {PEER_FLAG_EXIT_HTTP}
        await self.introduce_nodes()

        with self.assertRaises(AsyncTimeoutError):
            await wait_for(self.overlay(0).perform_http_request(remote_endpoint.get_address(),
                                                                b'GET /scrape?info_hash=0 HTTP/1.1\r\n\r\n'),
                           timeout=0)

    def test_cache_exitnodes_to_disk(self) -> None:
        """
        Test if we can cache exit nodes to disk.
        """
        self.overlay(0).candidates = {Peer(LibNaCLPK(b'\x00' * 64), ("0.1.2.3", 1029)): {PEER_FLAG_EXIT_BT}}
        self.overlay(0).cache_exitnodes_to_disk()

        self.assertEqual(bytes([ADDRESS_TYPE_IPV4]) + bytes(range(6)), self.fake_cache_file.read())

    def test_cache_exitnodes_to_disk_os_error(self) -> None:
        """
        Test if we can handle an OSError when caching exit nodes to disk and raise no errors.
        """
        self.overlay(0).candidates = {Peer(LibNaCLPK(b'\x00' * 64), ("0.1.2.3", 1029)): {PEER_FLAG_EXIT_BT}}
        self.overlay(0).settings.exitnode_cache = Mock(write_bytes=Mock(side_effect=FileNotFoundError))
        self.overlay(0).cache_exitnodes_to_disk()

        self.assertTrue(self.overlay(0).settings.exitnode_cache.write_bytes.called)

    async def test_should_join_circuit(self) -> None:
        """
        Test if we can join a circuit.
        """
        self.assertTrue(self.overlay(0).should_join_circuit(create_payload=Mock(), previous_node_address=Mock()))
