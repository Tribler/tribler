from __future__ import absolute_import

from binascii import unhexlify

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Socks5.connection import ConnectionState, Socks5Connection
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer


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

    @inlineCallbacks
    def setUp(self):
        yield super(TestSocks5Connection, self).setUp()

        self.connection = Socks5Connection(None)
        self.connection.transport = MockTransport()

    @inlineCallbacks
    def tearDown(self):
        if self.connection._udp_socket:  # Close opened UDP sockets
            yield self.connection._udp_socket.close()
        yield super(TestSocks5Connection, self).tearDown()

    def test_invalid_version(self):
        """
        Test passing an invalid version to the socks5 server
        """
        self.connection.dataReceived(unhexlify('040100'))
        self.assertFalse(self.connection.transport.connected)

    def test_method_request(self):
        """
        Test sending a method request to the socks5 server
        """
        self.connection.dataReceived(unhexlify('050100'))
        self.assertTrue(self.connection.transport.written_data)
        self.assertEqual(self.connection.state, ConnectionState.CONNECTED)

    def test_udp_associate(self):
        """
        Test sending a udp associate request to the socks5 server
        """
        self.connection.dataReceived(unhexlify('050100'))
        self.connection.dataReceived(unhexlify('05030001000000000000'))
        self.assertEqual(len(self.connection.transport.written_data), 2)
        self.assertEqual(self.connection.state, ConnectionState.PROXY_REQUEST_RECEIVED)

    def test_bind(self):
        """
        Test sending a bind request to the socks5 server
        """
        self.connection.dataReceived(unhexlify('050100'))
        self.connection.dataReceived(unhexlify('0502000100000000263f'))
        self.assertEqual(len(self.connection.transport.written_data), 2)

    def test_connect(self):
        """
        Test sending a connect command (which should be denied, we don't support TCP over our SOCKS5)
        """
        self.connection.dataReceived(unhexlify('050100'))
        self.connection.dataReceived(unhexlify('05010003096c6f63616c686f73740050'))
        self.assertEqual(len(self.connection.transport.written_data), 2)

    def test_unknown_command(self):
        """
        Test sending an unknown command to the socks5 server after handshake
        """
        self.connection.dataReceived(unhexlify('050100'))
        self.connection.dataReceived(unhexlify('05490003096c6f63616c686f73740050'))
        self.assertEqual(len(self.connection.transport.written_data), 2)
        self.assertEqual(self.connection.state, ConnectionState.CONNECTED)

    def test_invalid_methods(self):
        """
        Test sending an invalid methods packet
        """
        self.connection.dataReceived(unhexlify('0501'))
        self.assertEqual(len(self.connection.buffer), 2)  # We are still waiting for data
