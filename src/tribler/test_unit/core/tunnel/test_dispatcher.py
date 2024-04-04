import asyncio
from asyncio import Future
from unittest.mock import Mock, call

from ipv8.messaging.anonymization.tunnel import CIRCUIT_STATE_READY, Circuit
from ipv8.test.base import TestBase
from ipv8.util import succeed

from tribler.core.tunnel.dispatcher import TunnelDispatcher


class TestTunnelDispatcher(TestBase):
    """
    Tests for the TunnelDispatcher class.
    """

    def setUp(self) -> None:
        """
        Create a mocked dispatcher.
        """
        self.dispatcher = TunnelDispatcher(Mock())

    async def tearDown(self) -> None:
        """
        Destroy the dispatcher.
        """
        await self.dispatcher.shutdown_task_manager()

    def test_on_tunnel_in_too_many_hops(self) -> None:
        """
        Test if no data is sent to the SOCKS5 server over a circuit with too many hops.
        """
        self.assertFalse(self.dispatcher.on_incoming_from_tunnel(self.dispatcher.tunnels, Circuit(123, 300),
                                                                 ("0.0.0.0", 1024), b'a'))

    def test_on_tunnel_in_no_sessions(self) -> None:
        """
        Test if no data is sent to the SOCKS5 server when no sessions are available.
        """
        self.dispatcher.set_socks_servers([Mock(sessions=[])])
        self.assertFalse(self.dispatcher.on_incoming_from_tunnel(self.dispatcher.tunnels, Circuit(123, 1),
                                                                 ("0.0.0.0", 1024), b'a'))

    def test_on_tunnel_in_no_unmapped_connection(self) -> None:
        """
        Test if no data is sent to the SOCKS5 server when no connections are available.
        """
        self.dispatcher.set_socks_servers([Mock(sessions=[Mock(udp_connection=None)])])
        self.assertFalse(self.dispatcher.on_incoming_from_tunnel(self.dispatcher.tunnels, Circuit(123, 1),
                                                                 ("0.0.0.0", 1024), b'a'))

    def test_on_tunnel_in_no_mapped_connection(self) -> None:
        """
        Test if no data is sent to the SOCKS5 server when the mapped connection is not available.
        """
        self.dispatcher.cid_to_con[b'a'] = Mock(udp_connection=None)
        self.dispatcher.set_socks_servers([Mock(sessions=[self.dispatcher.cid_to_con[b'a']])])
        self.assertFalse(self.dispatcher.on_incoming_from_tunnel(self.dispatcher.tunnels, Circuit(123, 1),
                                                                 ("0.0.0.0", 1024), b'a'))

    def test_on_tunnel_in_available(self) -> None:
        """
        Test if data is sent to the SOCKS5 server when the mapped connection is available.
        """
        self.dispatcher.cid_to_con[b'a'] = Mock(udp_connection=Mock(send_datagram=Mock(return_value=True)))
        self.dispatcher.set_socks_servers([Mock(sessions=[self.dispatcher.cid_to_con[b'a']])])
        self.assertTrue(self.dispatcher.on_incoming_from_tunnel(self.dispatcher.tunnels, Circuit(123, 1),
                                                                     ("0.0.0.0", 1024), b'a'))

    def test_on_socks_in_udp_no_circuit(self) -> None:
        """
        Test if data cannot be dispatched without a circuit.
        """
        mock_request = Mock(destination=("0.0.0.0", 1024), data=b'a')
        connection = Mock()
        self.dispatcher.set_socks_servers([connection.socksconnection.socksserver])
        self.dispatcher.tunnels.circuits = {}
        self.assertFalse(self.dispatcher.on_socks5_udp_data(connection, mock_request))

    def test_on_socks_in_udp_no_ready_circuit(self) -> None:
        """
        Test if data cannot be dispatched with a circuit that is not ready.
        """
        circuit = Circuit(3, 1)
        mock_request = Mock(destination=("0.0.0.0", 1024), data=b'a')
        connection = Mock()
        self.dispatcher.set_socks_servers([connection.socksconnection.socksserver])
        self.dispatcher.tunnels.circuits = {circuit.circuit_id: circuit}
        self.assertFalse(self.dispatcher.on_socks5_udp_data(connection, mock_request))

    def test_on_socks_in_udp_ready_circuit(self) -> None:
        """
        Test if data is dispatched with a circuit that is ready.
        """
        circuit = Circuit(3, 1)
        circuit.add_hop(Mock())
        mock_request = Mock(destination=("0.0.0.0", 1024), data=b'a')
        connection = Mock()
        self.dispatcher.set_socks_servers([connection.socksconnection.socksserver])
        self.dispatcher.tunnels.circuits = {circuit.circuit_id: circuit}
        self.assertEqual(CIRCUIT_STATE_READY, circuit.state)
        self.assertTrue(self.dispatcher.on_socks5_udp_data(connection, mock_request))

    async def test_on_socks_in_tcp_no_success(self) -> None:
        """
        Test if a TCP connect request is not dispatched to the TunnelCommunity when the request is not successful.
        """
        tcp_connection = Mock()
        self.dispatcher.set_socks_servers([tcp_connection.socksserver])
        self.dispatcher.tunnels.perform_http_request = Mock(return_value=succeed(None))

        await self.dispatcher.on_socks5_tcp_data(tcp_connection, ("0.0.0.0", 1024), b'')

        self.assertIsNone(tcp_connection.transport.write.call_args)

    async def test_on_socks_in_tcp(self) -> None:
        """
        Test if a TCP connect request is correctly dispatched to the TunnelCommunity.
        """
        tcp_connection = Mock()
        self.dispatcher.set_socks_servers([tcp_connection.socksserver])
        self.dispatcher.tunnels.perform_http_request = Mock(return_value=succeed(b'test'))

        await self.dispatcher.on_socks5_tcp_data(tcp_connection, ("0.0.0.0", 1024), b'')

        self.assertEqual(call(b"test"), tcp_connection.transport.write.call_args)

    async def test_on_socks5_tcp_data_with_transport_none(self) -> None:
        """
        Test if connection without a transport does not lead to a successful dispatch.
        """
        tcp_connection = Mock(transport=None)
        self.dispatcher.set_socks_servers([tcp_connection.socksserver])
        self.dispatcher.tunnels.perform_http_request = Mock(return_value=succeed(b'test'))

        result = await self.dispatcher.on_socks5_tcp_data(tcp_connection, ("0.0.0.0", 1024), b'')

        self.assertFalse(result)

    def test_circuit_dead(self) -> None:
        """
        Test if the correct peers are removed when a circuit breaks.
        """
        connection = Mock()
        circuit = Circuit(3, 1)
        self.dispatcher.con_to_cir = {connection: {(i + 1): circuit for i in range(3)}}
        self.dispatcher.cid_to_con = {circuit.circuit_id: connection}

        res = self.dispatcher.circuit_dead(circuit)

        self.assertEqual(3, len(res))
        self.assertEqual(0, len(self.dispatcher.con_to_cir[connection]))
        self.assertNotIn(circuit.circuit_id, self.dispatcher.cid_to_con)

    def test_check_connections(self) -> None:
        """
        Test if closed connections are cleaned up properly.
        """
        connection = Mock(udp_connection=None)
        circuit = Circuit(3, 1)
        self.dispatcher.con_to_cir = {connection: {(i + 1): circuit for i in range(3)}}
        self.dispatcher.cid_to_con = {circuit.circuit_id: connection, 2: Mock()}

        self.dispatcher.check_connections()

        self.assertNotIn(connection, self.dispatcher.con_to_cir)
        self.assertNotIn(circuit.circuit_id, self.dispatcher.cid_to_con)
        self.assertIn(2, self.dispatcher.cid_to_con)

    async def test_on_data_after_select(self) -> None:
        """
        Test if data is forwarded after a circuit select.
        """
        mock_connection = Mock(udp_connection=None)
        circuit = Circuit(3, 1)
        mock_request = Mock(destination=("0.0.0.0", 1024), data=b'a')
        self.dispatcher.set_socks_servers([mock_connection.socksserver])
        self.dispatcher.tunnels.circuits = {}
        self.dispatcher.tunnels.create_circuit = Mock(return_value=circuit)
        self.dispatcher.on_socks5_udp_data = Mock(return_value=None)
        circuit.ready = Future()
        circuit.ready.set_result(True)

        self.dispatcher.select_circuit(mock_connection, mock_request)
        await asyncio.sleep(0)

        self.assertEqual(call(None, mock_request), self.dispatcher.on_socks5_udp_data.call_args)

    async def test_on_data_after_select_no_result(self) -> None:
        """
        Test if no data is forwarded after a failed circuit select.
        """
        mock_connection = Mock(udp_connection=None)
        circuit = Circuit(3, 1)
        mock_request = Mock(destination=("0.0.0.0", 1024), data=b'a')
        self.dispatcher.set_socks_servers([mock_connection.socksserver])
        self.dispatcher.tunnels.circuits = {}
        self.dispatcher.tunnels.create_circuit = Mock(return_value=circuit)
        self.dispatcher.on_socks5_udp_data = Mock(return_value=None)
        circuit.ready = Future()
        circuit.ready.set_result(None)

        self.dispatcher.select_circuit(mock_connection, mock_request)
        await asyncio.sleep(0)

        self.assertIsNone(self.dispatcher.on_socks5_udp_data.call_args)
