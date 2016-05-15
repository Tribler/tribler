import unittest

from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.timestamp import Timestamp


class TraderIdTestSuite(unittest.TestCase):
    """Trader ID test cases."""

    def setUp(self):
        # Object creation
        self.trader_id = TraderId('trader_id')
        self.trader_id2 = TraderId('trader_id')
        self.trader_id3 = TraderId('trader_id_2')

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('trader_id', str(self.trader_id))

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
        self.message_number = MessageNumber('message_number')
        self.message_number2 = MessageNumber('message_number')
        self.message_number3 = MessageNumber('message_number_2')

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('message_number', str(self.message_number))

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
        self.message_id = MessageId(TraderId('trader_id'), MessageNumber('message_number'))
        self.message_id2 = MessageId(TraderId('trader_id'), MessageNumber('message_number'))
        self.message_id3 = MessageId(TraderId('trader_id'), MessageNumber('message_number2'))

    def test_properties(self):
        # Test for properties
        self.assertEqual(TraderId('trader_id'), self.message_id.trader_id)
        self.assertEqual(MessageNumber('message_number'), self.message_id.message_number)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('trader_id.message_number', str(self.message_id))

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


class MessageTestSuite(unittest.TestCase):
    """Message test cases."""

    def setUp(self):
        # Object creation
        self.message = Message(MessageId(TraderId('trader_id'), MessageNumber('message_number')), Timestamp(float("inf")))

    def test_properties(self):
        # Test for properties
        self.assertEqual(MessageId(TraderId('trader_id'), MessageNumber('message_number')), self.message.message_id)
        self.assertEqual(Timestamp(float("inf")), self.message.timestamp)

if __name__ == '__main__':
    unittest.main()