from __future__ import absolute_import

import struct

from Tribler.Core.Socks5.conversion import decode_request
from Tribler.Test.test_as_server import AbstractServer


class TestSocks5Conversion(AbstractServer):

    def test_decode_request(self):
        """
        Test the decoding process of a request
        """
        self.assertIsNone(decode_request(0, struct.pack("!BBBB", 5, 0, 0, 5))[1])  # Invalid address type
        self.assertIsNone(decode_request(0, struct.pack("!BBBB", 5, 0, 0, 4))[1])  # IPv6
