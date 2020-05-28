from asyncio import Future, wait_for
from binascii import unhexlify
from unittest.mock import Mock

from tribler_core.modules.tunnel.socks5.connection import ConnectionState, Socks5Connection
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.tests.tools.test_as_server import AbstractServer


class MockTransport(MockObject):
    """
    This object mocks the transport of the socks5 connection.
    """

    def __init__(self):
        self.connected = True
        self.written_data = []
        self.host = '123.123.123.123'
        self.ip = 123
        self.num_messages = 2
        self.done = Future()

    def close(self):
        self.connected = False

    def write(self, data):
        self.written_data.append(data)
        if len(self.written_data) == self.num_messages and not self.done.done():
            self.done.set_result(None)

    def get_extra_info(self, *_):
        return self.host, self.ip

    async def wait_until_done(self, timeout=1):
        await wait_for(self.done, timeout=timeout)


class TestSocks5Connection(AbstractServer):
    """
    Test the basic functionality of the socks5 connection.
    """

    async def setUp(self):
        await super(TestSocks5Connection, self).setUp()

        self.connection = Socks5Connection(None)
        self.connection.transport = MockTransport()

    async def tearDown(self):
        if self.connection._udp_socket:  # Close opened UDP sockets
            self.connection._udp_socket.close()
        await super(TestSocks5Connection, self).tearDown()

    def test_invalid_version(self):
        """
        Test passing an invalid version to the socks5 server
        """
        self.connection.data_received(unhexlify('040100'))
        self.assertFalse(self.connection.transport.connected)

    def test_method_request(self):
        """
        Test sending a method request to the socks5 server
        """
        self.connection.data_received(unhexlify('050100'))
        self.assertTrue(self.connection.transport.written_data)
        self.assertEqual(self.connection.state, ConnectionState.CONNECTED)

    async def test_udp_associate(self):
        """
        Test sending a udp associate request to the socks5 server
        """
        self.connection.data_received(unhexlify('050100'))
        self.connection.data_received(unhexlify('05030001000000000000'))
        await self.connection.transport.wait_until_done()
        self.assertEqual(self.connection.state, ConnectionState.PROXY_REQUEST_RECEIVED)

    def test_bind(self):
        """
        Test sending a bind request to the socks5 server
        """
        self.connection.data_received(unhexlify('050100'))
        self.connection.data_received(unhexlify('0502000100000000263f'))
        self.assertEqual(len(self.connection.transport.written_data), 2)

    async def test_connect(self):
        """
        Test sending a connect command and proxying data
        """
        future = Future()

        def fake_on_socks5_tcp_data(*args):
            return future.set_result(args)

        self.connection.socksserver = Mock()
        self.connection.socksserver.output_stream.on_socks5_tcp_data = fake_on_socks5_tcp_data
        self.connection.data_received(unhexlify('050100'))
        self.connection.data_received(unhexlify('05010003096c6f63616c686f73740050'))
        self.assertEqual(len(self.connection.transport.written_data), 2)
        self.assertEqual(self.connection.state, ConnectionState.PROXY_REQUEST_RECEIVED)
        self.assertEqual(self.connection.connect_to, ('localhost', 80))
        self.connection.data_received(b'GET / HTTP/1.1')

        args = await wait_for(future, timeout=0.5)
        self.assertEqual(args, (self.connection, ('localhost', 80), b'GET / HTTP/1.1'))

    def test_unknown_command(self):
        """
        Test sending an unknown command to the socks5 server after handshake
        """
        self.connection.data_received(unhexlify('050100'))
        self.connection.data_received(unhexlify('05490003096c6f63616c686f73740050'))
        self.assertEqual(len(self.connection.transport.written_data), 2)
        self.assertEqual(self.connection.state, ConnectionState.CONNECTED)

    def test_invalid_methods(self):
        """
        Test sending an invalid methods packet
        """
        self.connection.data_received(unhexlify('0501'))
        self.assertEqual(len(self.connection.buffer), 2)  # We are still waiting for data
