import unittest

from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.timestamp import Timestamp


class MessageTestSuite(unittest.TestCase):
    """Message test cases."""

    def test_trader_id(self):
        # Object creation
        trader_id = TraderId('trader_id')
        trader_id2 = TraderId('trader_id')
        trader_id3 = TraderId('trader_id_2')

        # Test for conversions
        self.assertEqual('trader_id', str(trader_id))

        # Test for equality
        self.assertTrue(trader_id == trader_id2)
        self.assertTrue(trader_id == trader_id)
        self.assertTrue(trader_id != trader_id3)
        self.assertFalse(trader_id == 6)

        # Test for hashes
        self.assertEqual(trader_id.__hash__(), trader_id2.__hash__())
        self.assertNotEqual(trader_id.__hash__(), trader_id3.__hash__())

    def test_message_number(self):
        # Object creation
        message_number = MessageNumber('message_number')
        message_number2 = MessageNumber('message_number')
        message_number3 = MessageNumber('message_number_2')

        # Test for conversions
        self.assertEqual('message_number', str(message_number))

        # Test for equality
        self.assertTrue(message_number == message_number2)
        self.assertTrue(message_number == message_number)
        self.assertTrue(message_number != message_number3)
        self.assertFalse(message_number == 6)

        # Test for hashes
        self.assertEqual(message_number.__hash__(), message_number2.__hash__())
        self.assertNotEqual(message_number.__hash__(), message_number3.__hash__())

    def test_message_id(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_number2 = MessageNumber('message_number2')
        message_id = MessageId(trader_id, message_number)
        message_id2 = MessageId(trader_id, message_number)
        message_id3 = MessageId(trader_id, message_number2)

        # Test for properties
        self.assertEqual(trader_id, message_id.trader_id)
        self.assertEqual(message_number, message_id.message_number)

        # Test for conversions
        self.assertEqual('trader_id.message_number', str(message_id))

        # Test for equality
        self.assertTrue(message_id == message_id2)
        self.assertTrue(message_id == message_id)
        self.assertTrue(message_id != message_id3)
        self.assertFalse(message_id == 6)

        # Test for hashes
        self.assertEqual(message_id.__hash__(), message_id2.__hash__())
        self.assertNotEqual(message_id.__hash__(), message_id3.__hash__())

    def test_message(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        timestamp = Timestamp(float("inf"))
        message = Message(message_id, timestamp)
        message2 = Message(message_id, timestamp)

        # Test for properties
        self.assertEqual(message_id, message.message_id)
        self.assertEqual(timestamp, message.timestamp)

        # Test for is tick
        self.assertTrue(message.is_tick())
        self.assertFalse(message2.is_tick())

if __name__ == '__main__':
    unittest.main()