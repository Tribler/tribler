from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.Core.Socks5.test_connection import MockTransport
from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.tunnel import CIRCUIT_TYPE_DATA, CIRCUIT_STATE_EXTENDING, CIRCUIT_STATE_READY
from Tribler.community.tunnel.dispatcher import TunnelDispatcher
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class TestTunnelDispatcher(AbstractServer):
    """
    Test the functionality of the tunnel dispatcher.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestTunnelDispatcher, self).setUp(annotate=annotate)

        self.mock_tunnel_community = MockObject()
        self.selection_strategy = MockObject()
        self.selection_strategy.select = lambda *_: None
        self.mock_tunnel_community.selection_strategy = self.selection_strategy
        self.dispatcher = TunnelDispatcher(self.mock_tunnel_community)

        self.mock_circuit = MockObject()
        self.mock_circuit.state = CIRCUIT_STATE_EXTENDING
        self.mock_circuit.circuit_id = 3
        self.mock_circuit.tunnel_data = lambda *_: None

    def test_on_tunnel_in(self):
        """
        Test whether no data is sent to the SOCKS5 server when we receive data from the tunnels
        """
        mock_circuit = MockObject()
        mock_circuit.goal_hops = 300
        mock_circuit.ctype = CIRCUIT_TYPE_DATA
        mock_circuit.circuit_id = 3
        origin = ("0.0.0.0", 1024)
        self.assertFalse(self.dispatcher.on_incoming_from_tunnel(self.mock_tunnel_community, mock_circuit, origin, 'a'))

        mock_circuit.goal_hops = 1
        mock_sock_server = MockObject()
        mock_session = MockObject()
        mock_session._udp_socket = None
        mock_sock_server.sessions = [mock_session]
        self.dispatcher.set_socks_servers([mock_sock_server])
        self.dispatcher.destinations[1] = {'a': mock_circuit}
        self.assertFalse(self.dispatcher.on_incoming_from_tunnel(self.mock_tunnel_community, mock_circuit, origin, 'a'))

        mock_session._udp_socket = MockObject()
        mock_session._udp_socket.sendDatagram = lambda _: True
        mock_session._udp_socket.remote_udp_address = ("host.example.com", 1234)
        mock_session._udp_socket.transport = MockTransport()
        self.assertTrue(self.dispatcher.on_incoming_from_tunnel(self.mock_tunnel_community, mock_circuit, origin, 'a'))

    def test_on_socks_in(self):
        """
        Test whether data is correctly dispatched to a circuit
        """
        mock_socks_server = MockObject()
        self.dispatcher.set_socks_servers([mock_socks_server])

        mock_udp_connection = MockObject()
        mock_udp_connection.remote_udp_address = ("host.example.com", 1234)
        mock_udp_connection.transport = MockTransport()
        mock_udp_connection.socksconnection = MockObject()
        mock_udp_connection.socksconnection.socksserver = mock_socks_server

        mock_request = MockObject()
        mock_request.destination = ("0.0.0.0", 1024)
        mock_request.payload = 'a'

        # No circuit is selected
        self.assertFalse(self.dispatcher.on_socks5_udp_data(mock_udp_connection, mock_request))

        self.selection_strategy.select = lambda *_: self.mock_circuit

        # Circuit is not ready
        self.assertFalse(self.dispatcher.on_socks5_udp_data(mock_udp_connection, mock_request))

        self.mock_circuit.state = CIRCUIT_STATE_READY

        # Circuit ready, should be able to tunnel data
        self.assertTrue(self.dispatcher.on_socks5_udp_data(mock_udp_connection, mock_request))

    def test_circuit_dead(self):
        """
        Test whether the correct peers are removed when a circuit breaks
        """
        self.dispatcher.destinations = {1: {'a': self.mock_circuit, 'b': self.mock_circuit},
                                        2: {'c': self.mock_circuit, 'a': self.mock_circuit}}
        res = self.dispatcher.circuit_dead(self.mock_circuit)
        self.assertTrue(res)
        self.assertEqual(len(res), 3)
