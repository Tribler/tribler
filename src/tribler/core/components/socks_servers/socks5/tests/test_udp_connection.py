import pytest

from tribler_core.components.socks_servers.socks5.udp_connection import SocksUDPConnection


@pytest.fixture
async def connection():
    connection = SocksUDPConnection(None, ("1.1.1.1", 1234))
    await connection.open()
    yield connection
    connection.close()


def test_datagram_received(connection):
    """
    Test whether the right operations happen when a datagram is received
    """

    # We don't support IPV6 data
    assert not connection.datagram_received(b'aaa\x04', ("1.1.1.1", 1234))

    # We don't support fragmented data
    assert not connection.datagram_received(b'aa\x01aaa', ("1.1.1.1", 1234))

    # Receiving data from somewhere that is not our remote address
    assert not connection.datagram_received(b'aaaaaa', ("1.2.3.4", 1234))

    # Receiving data from an invalid destination address
    invalid_udp_packet = b'\x00\x00\x00\x03\x1etracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x940x000'
    assert not connection.datagram_received(invalid_udp_packet, ("1.1.1.1", 1234))


def test_send_diagram(connection):
    """
    Test sending a diagram over the SOCKS5 UDP connection
    """
    assert connection.send_datagram(b'a')
    connection.remote_udp_address = None
    assert not connection.send_datagram(b'a')
