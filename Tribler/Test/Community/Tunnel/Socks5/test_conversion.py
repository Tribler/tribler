import struct

from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.community.tunnel.Socks5.conversion import decode_request, IPV6AddrError


class TestSocks5Conversion(TriblerCoreTest):

    def test_decode_request(self):
        """
        Test the decoding process of a request
        """
        self.assertIsNone(decode_request(0, struct.pack("!BBBB", 5, 0, 0, 5))[1])  # Invalid address type
        self.assertRaises(IPV6AddrError, decode_request, 0, struct.pack("!BBBB", 5, 0, 0, 4))  # IPv6
