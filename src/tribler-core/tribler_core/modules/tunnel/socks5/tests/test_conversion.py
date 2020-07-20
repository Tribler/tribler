import struct

import pytest

from tribler_core.modules.tunnel.socks5.conversion import (
    ADDRESS_TYPE_DOMAIN_NAME,
    InvalidAddressException,
    decode_request,
    decode_udp_packet,
    encode_reply,
    encode_udp_packet,
)


def test_decode_request():
    """
    Test the decoding process of a request
    """
    assert decode_request(0, struct.pack("!BBBB", 5, 0, 0, 5))[1] is None  # Invalid address type
    assert decode_request(0, struct.pack("!BBBB", 5, 0, 0, 4))[1] is None  # IPv6


def test_encode_decode_udp_packet():
    rsv = 0
    frag = 0
    address_type = ADDRESS_TYPE_DOMAIN_NAME
    address = 'tracker1.good-tracker.com'
    port = 8084
    payload = b'0x000'
    encoded = encode_udp_packet(rsv, frag, address_type, address, port, payload)
    decoded = decode_udp_packet(encoded)

    assert rsv == decoded.rsv
    assert frag == decoded.frag
    assert address_type == decoded.address_type
    assert address == decoded.destination_host

    address = 'tracker1.unicode-tracker\xc4\xe95\x11$\x00'
    encoded = encode_udp_packet(rsv, frag, address_type, address, port, payload)
    decoded = decode_udp_packet(encoded)

    assert rsv == decoded.rsv
    assert frag == decoded.frag
    assert address_type == decoded.address_type
    assert address == decoded.destination_host


def test_encode_decode_udp_packet_py3():
    # try decoding badly encoded udp packet, should raise an exception in Python3
    badly_encoded_packet = b'\x00\x00\x00\x03 tracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x940x000'
    with pytest.raises(InvalidAddressException):
        decode_udp_packet(badly_encoded_packet)


def test_encode_decode_packet():
    rsv = 0
    address_type = ADDRESS_TYPE_DOMAIN_NAME
    bind_address = 'tracker1.good-tracker.com'
    bind_port = 8084
    rep = 0
    version = 5

    encoded = encode_reply(version, rep, rsv, address_type, bind_address, bind_port)
    _, decoded = decode_request(0, encoded)

    assert version == decoded.version
    assert rsv == decoded.rsv
    assert address_type == decoded.address_type
    assert bind_address == decoded.destination_host

    bind_address = 'tracker1.unicode-tracker\xc4\xe95\x11$\x00'
    encoded = encode_reply(version, rep, rsv, address_type, bind_address, bind_port)
    _, decoded = decode_request(0, encoded)

    assert version == decoded.version
    assert rsv == decoded.rsv
    assert address_type == decoded.address_type
    assert bind_address == decoded.destination_host


def test_encode_decode_packet_py3():
    # try decoding badly encoded packet, should return None in Python3
    badly_encoded = b'\x05\x00\x00\x03 tracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x94'
    _, decoded = decode_request(0, badly_encoded)
    assert decoded is None
