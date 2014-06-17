from unittest import TestCase
from mock import Mock
from Tribler.community.anontunnel.exitsocket import ShortCircuitExitSocket
from Tribler.community.anontunnel.payload import DataMessage

__author__ = 'Chris'


class TestShortCircuitExitSocket(TestCase):
    def setUp(self):

        self.socket = Mock()
        self.socket.sendto = Mock(return_value=True)

        raw_server = Mock()
        raw_server.create_udpsocket = Mock(return_value=self.socket)
        raw_server.start_listening_udp = Mock(return_value=None)

        self.circuit_id = 123

        self.proxy = Mock()
        self.proxy.on_data = Mock()

        self.return_address = ("127.0.0.1", 1337)
        self.exit_socket = ShortCircuitExitSocket(raw_server, self.proxy, self.circuit_id, self.return_address)

    def test_data_came_in(self):
        packet = "Hello world"
        source_address = ("google.com", 80)
        self.exit_socket.data_came_in([(source_address, packet)])

        args, kwargs = self.proxy.on_data.call_args
        circuit_id, none, message = args
        expected_message = DataMessage(("0.0.0.0", 0), packet, source_address)

        self.assertEqual(self.circuit_id, circuit_id)
        self.assertIsNone(none)
        self.assertEqual(expected_message.data, message.data)
        self.assertEqual(expected_message.destination, message.destination)
        self.assertEqual(expected_message.origin, message.origin)

    def test_sendto(self):
        data = "Hello world"
        destination = ("google.com", 80)
        self.exit_socket.sendto(data, destination)

        # The underlying socket must be called by the ExitSocket
        self.socket.sendto.assert_called_with(data, destination)