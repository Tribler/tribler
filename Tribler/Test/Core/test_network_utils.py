import socket

from nose.tools import raises
from twisted.internet import reactor
from twisted.internet.protocol import Factory

from Tribler.Core.Utilities.network_utils import get_random_port, autodetect_socket_style, InterruptSocket
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestNetworkUtils(TriblerCoreTest):

    def test_get_random_port(self):
        random_port = get_random_port()
        self.assertIsInstance(random_port, int)
        self.assertTrue(random_port)

    def test_get_random_port_tcp(self):
        listenport = reactor.listenTCP(9283, Factory())
        random_port = get_random_port(socket_type='tcp', min_port=9283, max_port=9283)
        self.assertEqual(random_port, 9284)
        listenport.stopListening()

    def test_get_random_port_udp(self):
        random_port = get_random_port(socket_type='udp')
        self.assertIsInstance(random_port, int)
        self.assertTrue(random_port)

    @raises(AssertionError)
    def test_get_random_port_invalid_type(self):
        get_random_port(socket_type="http")

    def test_autodetect_socket_style(self):
        style = autodetect_socket_style()
        self.assertTrue(style == 0 or autodetect_socket_style() == 1)

    def test_interrupt_socket(self):
        interrupt_socket = InterruptSocket()
        self.assertTrue(interrupt_socket.ip, u"127.0.0.1")
        self.assertIsInstance(interrupt_socket.port, int)
        self.assertIsInstance(interrupt_socket.socket, socket.socket)

        interrupt_socket.interrupt()
        interrupt_socket.interrupt()
        interrupt_socket.close()
