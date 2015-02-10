from threading import Event
from unittest import TestCase
from mock import Mock
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.tunnel.exitsocket import ShortCircuitExitSocket, TunnelExitSocket
from Tribler.community.tunnel.exitstrategies import DefaultExitStrategy
from Tribler.community.tunnel.payload import DataMessage
from Tribler.community.tunnel.routing import Circuit, Hop

__author__ = 'Chris'


class TestDefaultExitStrategy(TestCase):

    def setUp(self):
        self.socket = Mock()
        self.socket.sendto = Mock(return_value=True)

        raw_server = Mock()
        raw_server.create_udpsocket = Mock(return_value=self.socket)
        raw_server.start_listening_udp = Mock(return_value=None)

        self.raw_server = raw_server
        self.__create_counter = 0

    def __create_circuit(self, hops):
        circuit = Circuit(self.__create_counter, hops)
        for _ in range(hops):
            circuit.add_hop(Hop(None))

        self.__create_counter += 1
        return circuit

    def test_on_exiting_from_tunnel(self):
        proxy = Mock()
        proxy.circuits = [
            self.__create_circuit(0),
            self.__create_circuit(1),
        ]

        proxy.on_data = Mock()

        return_candidate = Mock()
        destination = ("google.com", 80)
        data = "Hello world"

        strategy = DefaultExitStrategy(self.raw_server, proxy)
        strategy.on_exiting_from_tunnel(proxy.circuits[0].circuit_id, return_candidate, destination, data)
        self.socket.sendto.assert_called_with(data, destination)

    def on_create(self):
        proxy = Mock()
        proxy.circuits = [
            self.__create_circuit(0),
            self.__create_circuit(1),
        ]

        destination = ("google.com", 80)

        strategy = DefaultExitStrategy(self.raw_server, proxy)

        exit_socket = strategy.create(proxy, self.raw_server, proxy.circuits[0].circuit_id, destination)
        self.assertIsInstance(exit_socket, ShortCircuitExitSocket)

        exit_socket = strategy.create(proxy, self.raw_server, proxy.circuits[1].circuit_id, destination)
        self.assertIsInstance(exit_socket, TunnelExitSocket)

    def on_get_socket(self):
        proxy = Mock()
        proxy.circuits = [
            self.__create_circuit(0),
            self.__create_circuit(1),
        ]

        destination = ("google.com", 80)

        strategy = DefaultExitStrategy(self.raw_server, proxy)

        exit_socket = strategy.get_exit_socket(proxy.circuits[0].circuit_id, destination)
        exit_socket2 = strategy.get_exit_socket(proxy.circuits[0].circuit_id, destination)
        self.assertEqual(exit_socket, exit_socket2,
                         "Subsequent exit packets to the same destination should use the exact same exit socket")
