import unittest

from Tribler.community.market.core.wallet_address import WalletAddress


class WalletAddressTestSuite(unittest.TestCase):
    """Bitcoin address test cases."""

    def setUp(self):
        # Object creation
        self.wallet_address = WalletAddress("0")
        self.wallet_address2 = WalletAddress("1")

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            WalletAddress(1)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual("0", str(self.wallet_address))
        self.assertEqual("1", str(self.wallet_address2))
