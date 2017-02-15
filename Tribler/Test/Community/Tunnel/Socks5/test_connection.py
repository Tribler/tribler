from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.tunnel.Socks5.conversion import decode_udp_packet, REP_SUCCEEDED
from Tribler.community.tunnel.Socks5.server import Socks5Connection, SocksUDPConnection
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
        self.dead = False

    def write(self, data):
        self.out.append(decode_udp_packet(data))

    def getHost(self):
        return MockHost()

    def loseConnection(self):
        self.dead = True


class MockRequest(object):
    def __init__(self):
        self.destination = ("0.0.0.0", 0)


class MockSocks5Connection(object):
    def select(self, _):
        return 42


class TestSocks5Connection(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestSocks5Connection, self).setUp(annotate=annotate)
        self.connection = Socks5Connection(MockSocks5Server(),
                                           MockSelectionStrategy(),
                                           1)
        self.connection.transport = MockTransport()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        yield self.connection.close()
        yield super(TestSocks5Connection, self).tearDown(annotate=annotate)

    def test_associate(self):
        """
        Test whether UDP ASSOCIATE requests are answered with a REP_SUCCEEDED
        """
        self.connection.on_udp_associate_request(self.connection,
                                                 MockRequest())

        self.assertGreater(len(self.connection.transport.out), 0)
        self.assertEquals(self.connection.transport.out[0].frag, REP_SUCCEEDED)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_double_close(self):
        """
        When a Socks5Connection connection is closed twice, it should just
        return True
        """
        self.assertFalse(self.connection.transport.dead)

        # First close
        yield self.connection.close()

        self.assertTrue(self.connection.transport.dead)

        # Second close
        self.assertTrue(self.connection.close())


class TestSocksUDPConnection(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestSocksUDPConnection, self).setUp(annotate=annotate)
        self.connection = SocksUDPConnection(MockSocks5Connection(),
                                             ("0.0.0.0", 0))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        yield self.connection.close()
        yield super(TestSocksUDPConnection, self).tearDown(annotate=annotate)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_double_close(self):
        """
        When a SocksUDPConnection connection is closed twice, it should just
        return True
        """
        # First close
        yield self.connection.close()

        self.assertIsNone(self.connection.listen_port)

        # Second close
        self.assertTrue(self.connection.close())
