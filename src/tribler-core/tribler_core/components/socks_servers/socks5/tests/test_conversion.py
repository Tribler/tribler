import struct

from ipv8.messaging.interfaces.udp.endpoint import DomainAddress
from ipv8.messaging.serialization import PackError

import pytest

from tribler_core.components.socks_servers.socks5.conversion import (
    CommandRequest,
    CommandResponse,
    UdpPacket,
    socks5_serializer,
)


def test_encode_decode_udp_packet():
    rsv = 0
    frag = 0
    address = DomainAddress('tracker1.good-tracker.com', 8084)
    data = b'0x000'
    encoded = socks5_serializer.pack_serializable(UdpPacket(rsv, frag, address, data))
    decoded, _ = socks5_serializer.unpack_serializable(UdpPacket, encoded)

    assert rsv == decoded.rsv
    assert frag == decoded.frag
    assert address == decoded.destination

    address = DomainAddress('tracker1.unicode-tracker\xc4\xe95\x11$\x00', 8084)
    encoded = socks5_serializer.pack_serializable(UdpPacket(rsv, frag, address, data))
    decoded, _ = socks5_serializer.unpack_serializable(UdpPacket, encoded)

    assert rsv == decoded.rsv
    assert frag == decoded.frag
    assert address == decoded.destination


def test_decode_udp_packet_fail():
    # try decoding badly encoded udp packet, should raise an exception in Python3
    badly_encoded_packet = b'\x00\x00\x00\x03 tracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x940x000'
    with pytest.raises(PackError):
        socks5_serializer.unpack_serializable(UdpPacket, badly_encoded_packet)


def test_encode_decode_command_request():
    rsv = 0
    address = DomainAddress('tracker1.good-tracker.com', 8084)
    rep = 0
    version = 5

    encoded = socks5_serializer.pack_serializable(CommandRequest(version, rep, rsv, address))
    decoded, _ = socks5_serializer.unpack_serializable(CommandRequest, encoded)

    assert version == decoded.version
    assert rsv == decoded.rsv
    assert address == decoded.destination

    address = DomainAddress('tracker1.unicode-tracker\xc4\xe95\x11$\x00', 8084)
    encoded = socks5_serializer.pack_serializable(CommandResponse(version, rep, rsv, address))
    decoded, _ = socks5_serializer.unpack_serializable(CommandResponse, encoded)

    assert version == decoded.version
    assert rsv == decoded.rsv
    assert address == decoded.bind


def test_decode_command_request_fail():
    badly_encoded = b'\x05\x00\x00\x03 tracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x94'
    with pytest.raises(PackError):
        socks5_serializer.unpack_serializable(CommandRequest, badly_encoded)

    with pytest.raises(PackError):
        # Invalid address type
        socks5_serializer.unpack_serializable(CommandRequest, struct.pack("!BBBB", 5, 0, 0, 5))

    with pytest.raises(PackError):
        # IPv6
        socks5_serializer.unpack_serializable(CommandRequest, struct.pack("!BBBB", 5, 0, 0, 4))
