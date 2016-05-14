import unittest

from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid


class TickTestSuite(unittest.TestCase):
    """Tick test cases."""

    def test_tick(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timeout = Timeout(float("inf"))
        timeout2 = Timeout(0.0)
        timestamp = Timestamp(float("inf"))
        timestamp2 = Timestamp(0.0)

        tick = Tick(message_id, price, quantity, timeout, timestamp, True)
        tick2 = Tick(message_id, price, quantity, timeout2, timestamp2, False)

        # Test for properties
        self.assertEqual(price, tick.price)
        self.assertEqual(quantity, tick.quantity)
        self.assertEqual(timeout, tick.timeout)
        self.assertEqual(timestamp, tick.timestamp)

        # Test 'is ask' function
        self.assertTrue(tick.is_ask())
        self.assertFalse(tick2.is_ask())

        # Test for is valid
        self.assertTrue(tick.is_valid())
        self.assertFalse(tick2.is_valid())

        # Test for to network
        self.assertEquals(((), ('trader_id', 'message_number', 63400, 30, float("inf"), float("inf"))),
                          tick.to_network())

        # Test for quantity setter
        tick.quantity = Quantity(60)
        self.assertEqual(Quantity(60), tick.quantity)

    def test_ask(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)

        ask = Ask.create(message_id, price, quantity, timeout, timestamp)

        # Test for properties
        self.assertEquals(message_id, ask.message_id)
        self.assertEquals(price, ask.price)
        self.assertEquals(quantity, ask.quantity)
        self.assertEquals(float(timeout), float(ask.timeout))
        self.assertEquals(timestamp, ask.timestamp)

        # Test for from network
        data = Ask.from_network(type('Data', (object,), {"trader_id": 'trader_id', "message_number": 'message_number',
                                                         "price": 63400, "quantity": 30, "timeout": 1462224447.117,
                                                         "timestamp": 1462224447.117}))

        self.assertEquals(message_id, data.message_id)
        self.assertEquals(price, data.price)
        self.assertEquals(quantity, data.quantity)
        self.assertEquals(float(timeout), float(data.timeout))
        self.assertEquals(timestamp, data.timestamp)

    def test_bid(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)

        bid = Bid.create(message_id, price, quantity, timeout, timestamp)

        # Test for properties
        self.assertEquals(message_id, bid.message_id)
        self.assertEquals(price, bid.price)
        self.assertEquals(quantity, bid.quantity)
        self.assertEquals(float(timeout), float(bid.timeout))
        self.assertEquals(timestamp, bid.timestamp)

        # Test for from network
        data = Bid.from_network(type('Data', (object,), {"trader_id": 'trader_id', "message_number": 'message_number',
                                                         "price": 63400, "quantity": 30, "timeout": 1462224447.117,
                                                         "timestamp": 1462224447.117}))

        self.assertEquals(message_id, data.message_id)
        self.assertEquals(price, data.price)
        self.assertEquals(quantity, data.quantity)
        self.assertEquals(float(timeout), float(data.timeout))
        self.assertEquals(timestamp, data.timestamp)


if __name__ == '__main__':
    unittest.main()
