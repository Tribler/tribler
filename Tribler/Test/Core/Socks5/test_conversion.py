import struct

from Tribler.Core.Socks5.conversion import decode_request, IPV6AddrError
from Tribler.Test.test_as_server import AbstractServer


class TestSocks5Conversion(AbstractServer):

    def test_decode_request(self):
        """
        Test the decoding process of a request
        """
        self.assertIsNone(decode_request(0, struct.pack("!BBBB", 5, 0, 0, 5))[1])  # Invalid address type
        self.assertRaises(IPV6AddrError, decode_request, 0, struct.pack("!BBBB", 5, 0, 0, 4))  # IPv6
