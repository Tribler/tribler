from asyncio import sleep
from unittest.mock import Mock

import pytest

from tribler_core.modules.tunnel.socks5 import conversion
from tribler_core.modules.tunnel.socks5.client import Socks5Client, Socks5Error
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
    assert request.payload == data
    assert request.destination == target

    packet = conversion.encode_udp_packet(0, 0, conversion.ADDRESS_TYPE_IPV4, *target, data)
    client.callback.assert_not_called()
    connection.send_datagram(packet)
    await sleep(0.1)
    client.callback.assert_called_once_with(data, target)
