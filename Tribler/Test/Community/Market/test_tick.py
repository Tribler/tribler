import unittest

from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.assetamount import Price
from Tribler.community.market.core.assetamount import Quantity
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class TickTestSuite(unittest.TestCase):
    """
    This class contains tests for the Tick object.
    """

    def setUp(self):
        # Object creation
        self.timestamp_now = Timestamp.now()
        self.tick = Tick(OrderId(TraderId('0'), OrderNumber(1)), Price(63400, 'BTC'), Quantity(30, 'MC'),
                         Timeout(30), self.timestamp_now, True)
        self.tick2 = Tick(OrderId(TraderId('0'), OrderNumber(2)), Price(63400, 'BTC'), Quantity(30, 'MC'),
                          Timeout(0.0), Timestamp(0.0), False)
        self.order_ask = Order(OrderId(TraderId('0'), OrderNumber(2)), Price(63400, 'BTC'),
                               Quantity(30, 'MC'), Timeout(0.0), Timestamp(0.0), True)
        self.order_bid = Order(OrderId(TraderId('0'), OrderNumber(2)), Price(63400, 'BTC'),
                               Quantity(30, 'MC'), Timeout(0.0), Timestamp(0.0), False)

    def test_is_ask(self):
        # Test 'is ask' function
        self.assertTrue(self.tick.is_ask())
        self.assertFalse(self.tick2.is_ask())

    def test_to_network(self):
        # Test for to network
        self.assertEquals((TraderId('0'), self.tick.timestamp, OrderNumber(1),
                           Price(63400, 'BTC'), Quantity(30, 'MC'), self.tick.timeout),
                          self.tick.to_network())

    def test_quantity_setter(self):
        # Test for quantity setter
        self.tick.quantity = Quantity(60, 'MC')
        self.assertEqual(Quantity(60, 'MC'), self.tick.quantity)

    def test_from_order_ask(self):
        # Test for from order
        ask = Tick.from_order(self.order_ask)
        self.assertIsInstance(ask, Ask)
        self.assertEqual(self.tick2.price, ask.price)
        self.assertEqual(self.tick2.quantity, ask.quantity)
        self.assertEqual(self.tick2.timestamp, ask.timestamp)
        self.assertEqual(self.tick2.order_id, ask.order_id)

    def test_from_order_bid(self):
        # Test for from order
        bid = Tick.from_order(self.order_bid)
        self.assertIsInstance(bid, Bid)
        self.assertEqual(self.tick2.price, bid.price)
        self.assertEqual(self.tick2.quantity, bid.quantity)
        self.assertEqual(self.tick2.timestamp, bid.timestamp)
        self.assertEqual(self.tick2.order_id, bid.order_id)

    def test_to_dictionary(self):
        """
        Test the to dictionary method of a tick
        """
        self.assertDictEqual(self.tick.to_dictionary(), {
            "trader_id": '0',
            "order_number": 1,
            "price": 63400.0,
            "price_type": "BTC",
            "quantity": 30.0,
            "quantity_type": "MC",
            "timeout": 30.0,
            "timestamp": float(self.timestamp_now),
            "block_hash": ('0' * 32).encode('hex')
        })
