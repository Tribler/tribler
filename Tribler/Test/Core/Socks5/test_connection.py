from Tribler.Core.Socks5.connection import Socks5Connection, ConnectionState
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread
from twisted.internet.defer import inlineCallbacks


class MockTransport(MockObject):
    """
    This object mocks the transport of the socks5 connection.
    """

    def __init__(self):
        self.connected = True
        self.written_data = []
        self.mock_host = MockObject()
        self.mock_host.host = '123.123.123.123'

    def loseConnection(self):
        self.connected = False

    def write(self, data):
        self.written_data.append(data)

    def getHost(self):
        return self.mock_host


class TestSocks5Connection(AbstractServer):
    """
    Test the basic functionality of the socks5 connection.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestSocks5Connection, self).setUp(annotate=annotate)

        self.connection = Socks5Connection(None)
        self.connection.transport = MockTransport()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        if self.connection._udp_socket:  # Close opened UDP sockets
            yield self.connection._udp_socket.close()
        yield super(TestSocks5Connection, self).tearDown(annotate=annotate)

    def test_invalid_version(self):
        """
        Test passing an invalid version to the socks5 server
        """
        self.connection.dataReceived('040100'.decode('hex'))
        self.assertFalse(self.connection.transport.connected)

    def test_method_request(self):
        """
        Test sending a method request to the socks5 server
        """
        self.connection.dataReceived('050100'.decode('hex'))
        self.assertTrue(self.connection.transport.written_data)
        self.assertEqual(self.connection.state, ConnectionState.CONNECTED)

    def test_udp_associate(self):
        """
        Test sending a udp associate request to the socks5 server
        """
        self.connection.dataReceived('050100'.decode('hex'))
        self.connection.dataReceived('05030001000000000000'.decode('hex'))
        self.assertEqual(len(self.connection.transport.written_data), 2)
        self.assertEqual(self.connection.state, ConnectionState.PROXY_REQUEST_RECEIVED)

    def test_bind(self):
        """
        Test sending a bind request to the socks5 server
        """
        self.connection.dataReceived('050100'.decode('hex'))
        self.connection.dataReceived('0502000100000000263f'.decode('hex'))
        self.assertEqual(len(self.connection.transport.written_data), 2)

    def test_connect(self):
        """
        Test sending a connect command (which should be denied, we don't support TCP over our SOCKS5)
        """
        self.connection.dataReceived('050100'.decode('hex'))
        self.connection.dataReceived('05010003096c6f63616c686f73740050'.decode('hex'))
        self.assertEqual(len(self.connection.transport.written_data), 2)

    def test_unknown_command(self):
        """
        Test sending an unknown command to the socks5 server after handshake
        """
        self.connection.dataReceived('050100'.decode('hex'))
        self.connection.dataReceived('05490003096c6f63616c686f73740050'.decode('hex'))
        self.assertEqual(len(self.connection.transport.written_data), 2)
        self.assertEqual(self.connection.state, ConnectionState.CONNECTED)

    def test_invalid_methods(self):
        """
        Test sending an invalid methods packet
        """
        self.connection.dataReceived('0501'.decode('hex'))
        self.assertEqual(len(self.connection.buffer), 2)  # We are still waiting for data
