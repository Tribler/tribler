import unittest

from Tribler.community.market.core.bitcoin_address import BitcoinAddress


class BitcoinAddressTestSuite(unittest.TestCase):
    """Bitcoin address test cases."""

    def setUp(self):
        # Object creation
        self.bitcoin_address = BitcoinAddress("0")
        self.bitcoin_address2 = BitcoinAddress("0")
        self.bitcoin_address3 = BitcoinAddress("1")

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            BitcoinAddress(1)

    def test_properties(self):
        # Test for properties
        self.assertEqual("0", self.bitcoin_address.bitcoin_address)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual("0", str(self.bitcoin_address))
        self.assertEqual("1", str(self.bitcoin_address3))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.bitcoin_address == self.bitcoin_address)
        self.assertTrue(self.bitcoin_address == self.bitcoin_address2)
        self.assertFalse(self.bitcoin_address == self.bitcoin_address3)
        self.assertEquals(NotImplemented, self.bitcoin_address.__eq__(0))

    def test_non_equality(self):
        # Test for non equality
        self.assertTrue(self.bitcoin_address != self.bitcoin_address3)
        self.assertFalse(self.bitcoin_address != self.bitcoin_address2)
        self.assertFalse(self.bitcoin_address.__ne__(0))

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.bitcoin_address.__hash__(), self.bitcoin_address2.__hash__())
        self.assertNotEqual(self.bitcoin_address.__hash__(), self.bitcoin_address3.__hash__())


if __name__ == '__main__':
    unittest.main()