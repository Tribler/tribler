import unittest

from Tribler.community.market.core.message import TraderId


class TraderIdTestSuite(unittest.TestCase):
    """Trader ID test cases."""

    def setUp(self):
        # Object creation
        self.trader_id = TraderId('0')
        self.trader_id2 = TraderId('0')
        self.trader_id3 = TraderId('1')

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            TraderId(1.0)
        with self.assertRaises(ValueError):
            TraderId('non hexadecimal')

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('0', str(self.trader_id))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.trader_id == self.trader_id2)
        self.assertTrue(self.trader_id != self.trader_id3)
        self.assertFalse(self.trader_id == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.trader_id.__hash__(), self.trader_id2.__hash__())
        self.assertNotEqual(self.trader_id.__hash__(), self.trader_id3.__hash__())
