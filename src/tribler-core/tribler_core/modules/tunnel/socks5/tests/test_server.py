from asyncio import sleep
from unittest.mock import Mock

from aiohttp import ClientSession

import pytest

from tribler_core.modules.tunnel.socks5.aiohttp_connector import Socks5Connector
from tribler_core.modules.tunnel.socks5.client import Socks5Client, Socks5Error
from tribler_core.modules.tunnel.socks5.conversion import UdpPacket, socks5_serializer
from tribler_core.modules.tunnel.socks5.server import Socks5Server


@pytest.fixture(name='socks5_server')
async def fixture_socks5_server(free_port):
    socks5_server = Socks5Server(free_port, Mock())
    yield socks5_server
    await socks5_server.stop()


@pytest.mark.asyncio
async def test_start_server(socks5_server):
    """
    Test writing an invalid version to the socks5 server
    """
    await socks5_server.start()


@pytest.mark.asyncio
async def test_socks5_udp_associate(socks5_server):
    """
    Test is sending a UDP associate request to the server succeeds.
    """
    await socks5_server.start()
    client = Socks5Client(('127.0.0.1', socks5_server.port), Mock())
    await client.associate_udp()
    assert client.transport is not None
    assert client.connection is not None
    assert client.connection.transport is not None


@pytest.mark.asyncio
async def test_socks5_sendto_fail(socks5_server):
    """
    Test if sending a UDP packet without a successful association fails.
    """
    await socks5_server.start()
    client = Socks5Client(('127.0.0.1', socks5_server.port), Mock())
    with pytest.raises(Socks5Error):
        client.sendto(b'\x00', ('127.0.0.1', 123))


@pytest.mark.asyncio
async def test_socks5_sendto_success(socks5_server):
    """
    Test if sending/receiving a UDP packet works correctly.
    """
    await socks5_server.start()
    data = b'\x00'
    target = ('127.0.0.1', 123)
    client = Socks5Client(('127.0.0.1', socks5_server.port), Mock())
    await client.associate_udp()

    client.sendto(data, target)
    await sleep(0.1)
    socks5_server.output_stream.on_socks5_udp_data.assert_called_once()
    connection = socks5_server.output_stream.on_socks5_udp_data.call_args[0][0]
    request = socks5_server.output_stream.on_socks5_udp_data.call_args[0][1]
    assert request.data == data
    assert request.destination == target

    packet = socks5_serializer.pack_serializable(UdpPacket(0, 0, target, data))
    client.callback.assert_not_called()
    connection.send_datagram(packet)
    await sleep(0.1)
    client.callback.assert_called_once_with(data, target)


@pytest.mark.asyncio
async def test_socks5_tcp_connect(socks5_server):
    """
    Test is sending a TCP connect request to the server succeeds.
    """
    await socks5_server.start()
    client = Socks5Client(('127.0.0.1', socks5_server.port), Mock())
    await client.connect_tcp(('127.0.0.1', 123))
    assert client.transport is not None
    assert client.connection is None


@pytest.mark.asyncio
async def test_socks5_write(socks5_server):
    """
    Test is sending a TCP data to the server succeeds.
    """
    await socks5_server.start()
    client = Socks5Client(('127.0.0.1', socks5_server.port), Mock())
    await client.connect_tcp(('127.0.0.1', 123))
    client.write(b' ')
    await sleep(.1)
    socks5_server.output_stream.on_socks5_tcp_data.assert_called_once_with(socks5_server.sessions[0],
                                                                           ('127.0.0.1', 123), b' ')


@pytest.mark.asyncio
async def test_socks5_aiohttp_connector(socks5_server):
    """
    Test if making a HTTP request through Socks5Server using the Socks5Connector works as expected.
    """
    await socks5_server.start()

    def return_data(conn, target, _):
        assert target == ('localhost', 80)
        conn.transport.write(b'HTTP/1.1 200\r\nContent-Type: text/html\r\n\r\nHello')
        conn.transport.close()
    socks5_server.output_stream.on_socks5_tcp_data = return_data

    async with ClientSession(connector=Socks5Connector(('127.0.0.1', socks5_server.port))) as session:
        async with session.get('http://localhost') as response:
            assert (await response.read()) == b'Hello'
