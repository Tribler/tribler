import struct

from ipv8.messaging.interfaces.udp.endpoint import DomainAddress
from ipv8.messaging.serialization import PackError
from ipv8.test.base import TestBase

from tribler.core.socks5.conversion import (
    CommandRequest,
    CommandResponse,
    UdpPacket,
    socks5_serializer,
)


class TestConversion(TestBase):
    """
    Tests for the conversion logic.
    """

    def test_decode_non_unicode_packet(self) -> None:
        """
        Test decoding a non-unicode udp packet.
        """
        encoded = b"\x00\x00\x00\x03\x19tracker1.good-tracker.com\x1f\x940x000"
        decoded, _ = socks5_serializer.unpack_serializable(UdpPacket, encoded)

        self.assertEqual(0, decoded.rsv)
        self.assertEqual(0, decoded.frag)
        self.assertEqual(DomainAddress('tracker1.good-tracker.com', 8084), decoded.destination)

    def test_decode_unicode_packet(self) -> None:
        """
        Test decoding a unicode udp packet.
        """
        encoded = b"\x00\x00\x00\x03 tracker1.unicode-tracker\xc3\x84\xc3\xa95\x11$\x00\x1f\x940x000"
        decoded, _ = socks5_serializer.unpack_serializable(UdpPacket, encoded)

        self.assertEqual(0, decoded.rsv)
        self.assertEqual(0, decoded.frag)
        self.assertEqual(DomainAddress('tracker1.unicode-tracker\xc4\xe95\x11$\x00', 8084), decoded.destination)

    def test_decode_udp_packet_fail(self) -> None:
        """
        Test if decoding a badly encoded udp packet raises an exception.
        """
        encoded = b'\x00\x00\x00\x03 tracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x940x000'

        with self.assertRaises(PackError):
            socks5_serializer.unpack_serializable(UdpPacket, encoded)

    def test_decode_non_unicode_command_request(self) -> None:
        """
        Test if command requests from non-unicode trackers can be decoded.
        """
        encoded = b"\x05\x00\x00\x03\x19tracker1.good-tracker.com\x1f\x94"
        decoded, _ = socks5_serializer.unpack_serializable(CommandRequest, encoded)

        self.assertEqual(5, decoded.version)
        self.assertEqual(0, decoded.rsv)
        self.assertEqual(DomainAddress('tracker1.good-tracker.com', 8084), decoded.destination)

    def test_decode_unicode_command_request(self) -> None:
        """
        Test if command requests from unicode trackers can be decoded.
        """
        encoded = b"\x05\x00\x00\x03 tracker1.unicode-tracker\xc3\x84\xc3\xa95\x11$\x00\x1f\x94"
        decoded, _ = socks5_serializer.unpack_serializable(CommandResponse, encoded)

        self.assertEqual(5, decoded.version)
        self.assertEqual(0, decoded.rsv)
        self.assertEqual(DomainAddress('tracker1.unicode-tracker\xc4\xe95\x11$\x00', 8084), decoded.bind)

    def test_decode_command_request_fail_encoding(self) -> None:
        """
        Test if decoding a badly encoded command request raises an exception.
        """
        encoded = b'\x05\x00\x00\x03 tracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x94'
        with self.assertRaises(PackError):
            socks5_serializer.unpack_serializable(CommandRequest, encoded)

    def test_decode_command_request_fail_invalid_address(self) -> None:
        """
        Test if decoding a command request with an invalid address type raises an exception.
        """
        with self.assertRaises(PackError):
            socks5_serializer.unpack_serializable(CommandRequest, struct.pack("!BBBB", 5, 0, 0, 5))

    def test_decode_command_request_fail_ipv6(self) -> None:
        """
        Test if decoding a command request with an ipv6 address raises an exception.
        """
        with self.assertRaises(PackError):
            socks5_serializer.unpack_serializable(CommandRequest, struct.pack("!BBBB", 5, 0, 0, 4))
