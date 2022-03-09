from asyncio import Future, wait_for
from binascii import unhexlify
from unittest.mock import Mock

import pytest

from tribler_core.components.socks_servers.socks5.connection import ConnectionState, Socks5Connection
from tribler_core.tests.tools.base_test import MockObject


class MockTransport(MockObject):
    """
    This object mocks the transport of the socks5 connection.
    """

    def __init__(self, loop):
        self.connected = True
        self.written_data = []
        self.host = '123.123.123.123'
        self.ip = 123
        self.num_messages = 2
        self.done = Future(loop=loop)

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


@pytest.fixture
def connection(loop):
    connection = Socks5Connection(None)
    connection.transport = MockTransport(loop)
    yield connection
    if connection.udp_connection:  # Close opened UDP sockets
        connection.udp_connection.close()


def test_invalid_version(connection):
    """
    Test passing an invalid version to the socks5 server
    """
    connection.data_received(unhexlify('040100'))
    assert not connection.transport.connected


@pytest.mark.asyncio
def test_method_request(connection):
    """
    Test sending a method request to the socks5 server
    """
    connection.data_received(unhexlify('050100'))
    assert connection.transport.written_data
    assert connection.state == ConnectionState.CONNECTED


@pytest.mark.asyncio
async def test_udp_associate(connection):
    """
    Test sending a udp associate request to the socks5 server
    """
    connection.data_received(unhexlify('050100'))
    connection.data_received(unhexlify('05030001000000000000'))
    await connection.transport.wait_until_done()
    assert connection.state == ConnectionState.PROXY_REQUEST_RECEIVED


def test_bind(connection):
    """
    Test sending a bind request to the socks5 server
    """
    connection.data_received(unhexlify('050100'))
    connection.data_received(unhexlify('0502000100000000263f'))
    assert len(connection.transport.written_data) == 2


@pytest.mark.asyncio
async def test_connect(connection):
    """
    Test sending a connect command and proxying data
    """
    future = Future()

    def fake_on_socks5_tcp_data(*args):
        return future.set_result(args)

    connection.socksserver = Mock()
    connection.socksserver.output_stream.on_socks5_tcp_data = fake_on_socks5_tcp_data
    connection.data_received(unhexlify('050100'))
    connection.data_received(unhexlify('05010003096c6f63616c686f73740050'))
    assert len(connection.transport.written_data) == 2

    assert connection.state == ConnectionState.PROXY_REQUEST_RECEIVED
    assert connection.connect_to == ('localhost', 80)
    connection.data_received(b'GET / HTTP/1.1')

    args = await wait_for(future, timeout=0.5)
    assert args == (connection, ('localhost', 80), b'GET / HTTP/1.1')


def test_unknown_command(connection):
    """
    Test sending an unknown command to the socks5 server after handshake
    """
    connection.data_received(unhexlify('050100'))
    connection.data_received(unhexlify('05490003096c6f63616c686f73740050'))
    assert len(connection.transport.written_data) == 2
    assert connection.state == ConnectionState.CONNECTED


def test_invalid_methods(connection):
    """
    Test sending an invalid methods packet
    """
    connection.data_received(unhexlify('0501'))
    assert len(connection.buffer) == 2  # We are still waiting for data
