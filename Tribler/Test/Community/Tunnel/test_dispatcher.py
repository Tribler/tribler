from __future__ import absolute_import

from ipv8.messaging.anonymization.tunnel import CIRCUIT_STATE_EXTENDING, CIRCUIT_STATE_READY, CIRCUIT_TYPE_DATA

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.triblertunnel.dispatcher import TunnelDispatcher


class TestTunnelDispatcher(AbstractServer):
    """
    Test the functionality of the tunnel dispatcher.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestTunnelDispatcher, self).setUp()

        self.mock_tunnel_community = MockObject()
        self.mock_tunnel_community.select_circuit = lambda *_: None
        self.mock_tunnel_community.send_data = lambda *_: None
        self.dispatcher = TunnelDispatcher(self.mock_tunnel_community)

        self.mock_circuit = MockObject()
        self.mock_circuit.state = CIRCUIT_STATE_EXTENDING
        self.mock_circuit.circuit_id = 3
        self.mock_circuit.peer = MockObject()
        self.mock_circuit.peer.address = ("1.1.1.1", 1234)
        self.mock_circuit.tunnel_data = lambda *_: None

    def test_on_tunnel_in(self):
        """
        Test whether no data is sent to the SOCKS5 server when we receive data from the tunnels
        """
        mock_circuit = MockObject()
        mock_circuit.goal_hops = 300
        mock_circuit.circuit_id = b'a'
        mock_circuit.ctype = CIRCUIT_TYPE_DATA
        origin = ("0.0.0.0", 1024)
        self.assertFalse(self.dispatcher.on_incoming_from_tunnel(self.mock_tunnel_community,
                                                                 mock_circuit, origin, b'a'))

        mock_circuit.goal_hops = 1
        mock_sock_server = MockObject()
        mock_session = MockObject()
        mock_session._udp_socket = None
        mock_sock_server.sessions = [mock_session]
        self.dispatcher.set_socks_servers([mock_sock_server])
        self.dispatcher.destinations[1] = {b'a': mock_circuit}
        self.assertFalse(self.dispatcher.on_incoming_from_tunnel(self.mock_tunnel_community,
                                                                 mock_circuit, origin, b'a'))

        mock_session._udp_socket = MockObject()
        mock_session._udp_socket.sendDatagram = lambda _: True
        self.assertTrue(self.dispatcher.on_incoming_from_tunnel(self.mock_tunnel_community,
                                                                mock_circuit, origin, b'a'))

    def test_on_socks_in(self):
        """
        Test whether data is correctly dispatched to a circuit
        """
        mock_socks_server = MockObject()
        self.dispatcher.set_socks_servers([mock_socks_server])

        mock_udp_connection = MockObject()
        mock_udp_connection.socksconnection = MockObject()
        mock_udp_connection.socksconnection.socksserver = mock_socks_server

        mock_request = MockObject()
        mock_request.destination = ("0.0.0.0", 1024)
        mock_request.payload = 'a'

        # No circuit is selected
        self.assertFalse(self.dispatcher.on_socks5_udp_data(mock_udp_connection, mock_request))

        self.mock_tunnel_community.select_circuit = lambda *_: self.mock_circuit

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
