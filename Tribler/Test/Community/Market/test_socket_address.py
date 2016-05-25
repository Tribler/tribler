import unittest

from Tribler.community.market.socket_address import SocketAddress


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

    def test_properties(self):
        # Test for properties
        self.assertEqual("1.1.1.1", self.socket_address.ip)
        self.assertEqual(1, self.socket_address.port)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual("1.1.1.1:1", str(self.socket_address))
        self.assertEqual("2.2.2.2:1", str(self.socket_address3))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.socket_address == self.socket_address)
        self.assertTrue(self.socket_address == self.socket_address2)
        self.assertFalse(self.socket_address == self.socket_address3)
        self.assertEquals(NotImplemented, self.socket_address.__eq__(0))

    def test_non_equality(self):
        # Test for non equality
        self.assertTrue(self.socket_address != self.socket_address3)
        self.assertFalse(self.socket_address != self.socket_address2)
        self.assertFalse(self.socket_address.__ne__(0))

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.socket_address.__hash__(), self.socket_address2.__hash__())
        self.assertNotEqual(self.socket_address.__hash__(), self.socket_address3.__hash__())


if __name__ == '__main__':
    unittest.main()
