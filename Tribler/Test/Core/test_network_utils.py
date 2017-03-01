import random
import socket
from nose.tools import raises
from twisted.internet.protocol import Factory

from Tribler.Core.Utilities.network_utils import get_random_port, autodetect_socket_style, InterruptSocket
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.twisted_thread import reactor, deferred


class TriblerCoreTestNetworkUtils(TriblerCoreTest):

    def test_get_random_port(self):
        random_port = get_random_port()
        self.assertIsInstance(random_port, int)
        self.assertTrue(random_port)

    @deferred(timeout=5)
    def test_get_random_port_tcp(self):
        rand_port_num = random.randint(*self.get_bucket_range_port())
        listenport = reactor.listenTCP(rand_port_num, Factory())
        random_port = get_random_port(socket_type='tcp', min_port=rand_port_num, max_port=rand_port_num)
        self.assertGreaterEqual(random_port, rand_port_num+1)
        return listenport.stopListening()

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
