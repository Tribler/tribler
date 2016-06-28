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

    def test_conversion(self):
        # Test for conversions
        self.assertEqual("0", str(self.bitcoin_address))
        self.assertEqual("1", str(self.bitcoin_address3))


if __name__ == '__main__':
    unittest.main()
