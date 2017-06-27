import unittest

from Tribler.community.market.core.socket_address import SocketAddress


class SocketAddressTestSuite(unittest.TestCase):
    """Socket address test cases."""

    def setUp(self):
        # Object creation
        self.socket_address = SocketAddress("1.1.1.1", 1)
        self.socket_address2 = SocketAddress("1.1.1.1", 1)
        self.socket_address3 = SocketAddress("2.2.2.2", 1)

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            SocketAddress("0.0.0.0", 0)
