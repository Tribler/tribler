import unittest

from twisted.internet.defer import inlineCallbacks

from Tribler.community.tunnel.Socks5.conversion import decode_udp_packet, REP_SUCCEEDED
from Tribler.community.tunnel.Socks5.server import Socks5Connection
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class MockSocks5Server(object):
    def connectionLost(self, _):
        pass


class MockSelectionStrategy(object):
    def select(self, *_):
        pass


class MockHost(object):
    def __init__(self):
        self.host = "0.0.0.0"


class MockTransport(object):
    """
    Store sent UDP packets as UdpRequests in self.out
    """

    def __init__(self):
        self.out = []

    def write(self, data):
        self.out.append(decode_udp_packet(data))

    def getHost(self):
        return MockHost()

    def loseConnection(self):
        pass


class MockRequest(object):
    def __init__(self):
        self.destination = ("0.0.0.0", 0)


class TestSocks5Connection(unittest.TestCase):
    def setUp(self):
        self.connection = Socks5Connection(MockSocks5Server(),
                                           MockSelectionStrategy(),
                                           1)
        self.connection.transport = MockTransport()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self):
        yield self.connection._udp_socket.listen_port.stopListening()

    def test_associate(self):
        """
        Test whether UDP ASSOCIATE requests are answered with a REP_SUCCEEDED
        """
        self.connection.on_udp_associate_request(self.connection,
                                                 MockRequest())

        self.assertGreater(len(self.connection.transport.out), 0)
        self.assertEquals(self.connection.transport.out[0].frag, REP_SUCCEEDED)
