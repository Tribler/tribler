import unittest

from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import Order, OrderId, OrderNumber


class TickTestSuite(unittest.TestCase):
    """Tick test cases."""

    def setUp(self):
        self.inf = Timeout(float("inf"))
        # Object creation
        self.tick = Tick(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                         OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(63400), Quantity(30),
                         self.inf, Timestamp(float("inf")), True)
        self.tick2 = Tick(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                          OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(63400), Quantity(30),
                          Timeout(0.0), Timestamp(0.0), False)
        self.order_ask = Order(OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(63400), Quantity(30),
                               Timeout(0.0), Timestamp(0.0), True)
        self.order_bid = Order(OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(63400), Quantity(30),
                               Timeout(0.0), Timestamp(0.0), False)

    def test_properties(self):
        # Test for properties
        self.assertEqual(Price(63400), self.tick.price)
        self.assertEqual(Quantity(30), self.tick.quantity)
        self.assertEqual(self.inf, self.tick.timeout)
        self.assertEqual(Timestamp(float("inf")), self.tick.timestamp)
        self.assertEqual(OrderId(TraderId('trader_id'), OrderNumber("order_number")), self.tick.order_id)

    def test_reserve(self):
        # Test 'reserve' function
        self.assertFalse(self.tick.is_reserved())
        self.tick.reserve()
        self.assertTrue(self.tick.is_reserved())

    def test_release(self):
        # Test 'release' function
        self.tick.reserve()
        self.assertTrue(self.tick.is_reserved())
        self.tick.release()
        self.assertFalse(self.tick.is_reserved())

    def test_is_ask(self):
        # Test 'is ask' function
        self.assertTrue(self.tick.is_ask())
        self.assertFalse(self.tick2.is_ask())

    def test_is_valid(self):
        # Test for is valid
        self.assertTrue(self.tick.is_valid())
        self.assertFalse(self.tick2.is_valid())

    def test_to_network(self):
        # Test for to network
        self.assertEquals(((), ('trader_id', 'message_number', 'order_number', 63400, 30, float("inf"), float("inf"))),
                          self.tick.to_network())

    def test_quantity_setter(self):
        # Test for quantity setter
        self.tick.quantity = Quantity(60)
        self.assertEqual(Quantity(60), self.tick.quantity)

    def test_from_order_ask(self):
        # Test for from order
        ask = Tick.from_order(self.order_ask, MessageId(TraderId('trader_id'), MessageNumber('message_number')))
        self.assertIsInstance(ask, Ask)
        self.assertEqual(self.tick2.price, ask.price)
        self.assertEqual(self.tick2.quantity, ask.quantity)
        self.assertEqual(self.tick2.timestamp, ask.timestamp)
        self.assertEqual(self.tick2.order_id, ask.order_id)
        self.assertEqual(self.tick2.message_id, ask.message_id)

    def test_from_order_bid(self):
        # Test for from order
        bid = Tick.from_order(self.order_bid, MessageId(TraderId('trader_id'), MessageNumber('message_number')))
        self.assertIsInstance(bid, Bid)
        self.assertEqual(self.tick2.price, bid.price)
        self.assertEqual(self.tick2.quantity, bid.quantity)
        self.assertEqual(self.tick2.timestamp, bid.timestamp)
        self.assertEqual(self.tick2.order_id, bid.order_id)
        self.assertEqual(self.tick2.message_id, bid.message_id)


class AskTestSuite(unittest.TestCase):
    """Ask test cases."""

    def setUp(self):
        # Object creation
        self.ask = Ask(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                       OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(63400), Quantity(30),
                       Timeout(1462224447.117), Timestamp(1462224447.117))

    def test_properties(self):
        # Test for properties
        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), self.ask.message_id)
        self.assertEquals(Price(63400), self.ask.price)
        self.assertEquals(Quantity(30), self.ask.quantity)
        self.assertEquals(float(Timeout(1462224447.117)), float(self.ask.timeout))
        self.assertEquals(Timestamp(1462224447.117), self.ask.timestamp)

    def test_from_network(self):
        # Test for from network
        data = Ask.from_network(type('Data', (object,), {"trader_id": 'trader_id', "order_number": 'order_number',
                                                         "message_number": 'message_number', "price": 63400,
                                                         "quantity": 30, "timeout": 1462224447.117,
                                                         "timestamp": 1462224447.117}))

        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(30), data.quantity)
        self.assertEquals(float(Timeout(1462224447.117)), float(data.timeout))
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class BidTestSuite(unittest.TestCase):
    """Bid test cases."""

    def setUp(self):
        # Object creation
        self.bid = Bid(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                       OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(63400), Quantity(30),
                       Timeout(1462224447.117), Timestamp(1462224447.117))

    def test_properties(self):
        # Test for properties
        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), self.bid.message_id)
        self.assertEquals(Price(63400), self.bid.price)
        self.assertEquals(Quantity(30), self.bid.quantity)
        self.assertEquals(float(Timeout(1462224447.117)), float(self.bid.timeout))
        self.assertEquals(Timestamp(1462224447.117), self.bid.timestamp)

    def test_from_network(self):
        # Test for from network
        data = Bid.from_network(type('Data', (object,), {"trader_id": 'trader_id', "order_number": 'order_number',
                                                         "message_number": 'message_number', "price": 63400,
                                                         "quantity": 30, "timeout": 1462224447.117,
                                                         "timestamp": 1462224447.117}))

        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(30), data.quantity)
        self.assertEquals(float(Timeout(1462224447.117)), float(data.timeout))
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


if __name__ == '__main__':
    unittest.main()
