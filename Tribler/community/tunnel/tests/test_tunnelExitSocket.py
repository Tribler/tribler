from unittest import TestCase
from mock import Mock
from Tribler.community.tunnel.exitsocket import TunnelExitSocket

__author__ = 'Chris'


class TestTunnelExitSocket(TestCase):

    def setUp(self):

        self.socket = Mock()
        self.socket.sendto = Mock(return_value=True)

        raw_server = Mock()
        raw_server.create_udpsocket = Mock(return_value=self.socket)
        raw_server.start_listening_udp = Mock(return_value=None)

        self.circuit_id = 123

        self.proxy = Mock()
        self.proxy.tunnel_data_to_origin = Mock()

        self.return_address = ("127.0.0.1", 1337)
        self.exit_socket = TunnelExitSocket(raw_server, self.proxy, self.circuit_id, self.return_address)

    def test_data_came_in(self):
        packet = "Hello world"
        source_address = ("google.com", 80)
        self.exit_socket.data_came_in([(source_address, packet)])

        # Incoming packets must be routed back using the proxy
        self.proxy.tunnel_data_to_origin.assert_called_with(
            circuit_id=self.circuit_id,
            candidate=self.return_address,
            source_address=source_address,
            payload=packet
        )

    def test_sendto(self):
        data = "Hello world"
        destination = ("google.com", 80)
        self.exit_socket.sendto(data, destination)

        # The underlying socket must be called by the ExitSocket
        self.socket.sendto.assert_called_with(data, destination)
