from __future__ import absolute_import

import struct
import sys
from unittest import skipIf

from ipv8.util import ensure_str

from Tribler.Core.Socks5.conversion import ADDRESS_TYPE_DOMAIN_NAME, InvalidAddressException, decode_request, \
    decode_udp_packet, encode_reply, encode_udp_packet
from Tribler.Test.test_as_server import AbstractServer


class TestSocks5Conversion(AbstractServer):

    def test_decode_request(self):
        """
        Test the decoding process of a request
        """
        self.assertIsNone(decode_request(0, struct.pack("!BBBB", 5, 0, 0, 5))[1])  # Invalid address type
        self.assertIsNone(decode_request(0, struct.pack("!BBBB", 5, 0, 0, 4))[1])  # IPv6

    def test_encode_decode_udp_packet(self):
        rsv = 0
        frag = 0
        address_type = ADDRESS_TYPE_DOMAIN_NAME
        address = u'tracker1.good-tracker.com'
        port = 8084
        payload = b'0x000'
        encoded = encode_udp_packet(rsv, frag, address_type, address, port, payload)
        decoded = decode_udp_packet(encoded)

        self.assertEqual(rsv, decoded.rsv)
        self.assertEqual(frag, decoded.frag)
        self.assertEqual(address_type, decoded.address_type)
        self.assertEqual(ensure_str(address), ensure_str(decoded.destination_host))

        address = u'tracker1.unicode-tracker\xc4\xe95\x11$\x00'
        encoded = encode_udp_packet(rsv, frag, address_type, address, port, payload)
        decoded = decode_udp_packet(encoded)

        self.assertEqual(rsv, decoded.rsv)
        self.assertEqual(frag, decoded.frag)
        self.assertEqual(address_type, decoded.address_type)
        self.assertEqual(ensure_str(address), ensure_str(decoded.destination_host))

    @skipIf(sys.version_info.major < 3, "Test for Python3 decoding of UDP packet")
    def test_encode_decode_udp_packet_py3(self):
        # try decoding badly encoded udp packet, should raise an exception in Python3
        badly_encoded_packet = b'\x00\x00\x00\x03 tracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x940x000'
        self.assertRaises(InvalidAddressException, decode_udp_packet, badly_encoded_packet)

    def test_encode_decode_packet(self):
        rsv = 0
        address_type = ADDRESS_TYPE_DOMAIN_NAME
        bind_address = u'tracker1.good-tracker.com'
        bind_port = 8084
        rep = 0
        version = 5

        encoded = encode_reply(version, rep, rsv, address_type, bind_address, bind_port)
        _, decoded = decode_request(0, encoded)

        self.assertEqual(version, decoded.version)
        self.assertEqual(rsv, decoded.rsv)
        self.assertEqual(address_type, decoded.address_type)
        self.assertEqual(ensure_str(bind_address), ensure_str(decoded.destination_host))

        bind_address = u'tracker1.unicode-tracker\xc4\xe95\x11$\x00'
        encoded = encode_reply(version, rep, rsv, address_type, bind_address, bind_port)
        _, decoded = decode_request(0, encoded)

        self.assertEqual(version, decoded.version)
        self.assertEqual(rsv, decoded.rsv)
        self.assertEqual(address_type, decoded.address_type)
        self.assertEqual(ensure_str(bind_address), ensure_str(decoded.destination_host))

    @skipIf(sys.version_info.major < 3, "Test for Python3 decoding of UDP packet")
    def test_encode_decode_packet_py3(self):
        # try decoding badly encoded packet, should return None in Python3
        badly_encoded = b'\x05\x00\x00\x03 tracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x94'
        _, decoded = decode_request(0, badly_encoded)
        self.assertIsNone(decoded)
