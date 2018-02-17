import unittest

from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId


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
        self.assertTrue(self.trader_id == self.trader_id)
        self.assertTrue(self.trader_id != self.trader_id3)
        self.assertFalse(self.trader_id == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.trader_id.__hash__(), self.trader_id2.__hash__())
        self.assertNotEqual(self.trader_id.__hash__(), self.trader_id3.__hash__())


class MessageNumberTestSuite(unittest.TestCase):
    """Message number test cases."""

    def setUp(self):
        # Object creation
        self.message_number = MessageNumber(1)
        self.message_number2 = MessageNumber(1)
        self.message_number3 = MessageNumber(3)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('1', str(self.message_number))

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            MessageNumber(1.0)

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.message_number == self.message_number2)
        self.assertTrue(self.message_number == self.message_number)
        self.assertTrue(self.message_number != self.message_number3)
        self.assertFalse(self.message_number == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.message_number.__hash__(), self.message_number2.__hash__())
        self.assertNotEqual(self.message_number.__hash__(), self.message_number3.__hash__())


class MessageIdTestSuite(unittest.TestCase):
    """Message ID test cases."""

    def setUp(self):
        # Object creation
        self.message_id = MessageId(TraderId('0'), MessageNumber(1))
        self.message_id2 = MessageId(TraderId('0'), MessageNumber(1))
        self.message_id3 = MessageId(TraderId('0'), MessageNumber(2))

    def test_properties(self):
        # Test for properties
        self.assertEqual(TraderId('0'), self.message_id.trader_id)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('0.1', str(self.message_id))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.message_id == self.message_id2)
        self.assertTrue(self.message_id == self.message_id)
        self.assertTrue(self.message_id != self.message_id3)
        self.assertFalse(self.message_id == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.message_id.__hash__(), self.message_id2.__hash__())
        self.assertNotEqual(self.message_id.__hash__(), self.message_id3.__hash__())
