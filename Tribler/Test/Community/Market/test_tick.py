from __future__ import absolute_import

import unittest
from binascii import hexlify

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.tick import Ask, Bid, Tick
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class TickTestSuite(unittest.TestCase):
    """
    This class contains tests for the Tick object.
    """

    def setUp(self):
        # Object creation
        self.timestamp_now = Timestamp.now()
        self.tick = Tick(OrderId(TraderId(b'0'), OrderNumber(1)),
                         AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp(0.0), True)
        self.tick2 = Tick(OrderId(TraderId(b'0'), OrderNumber(2)),
                          AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timeout(0), Timestamp(0.0), False)
        self.order_ask = Order(OrderId(TraderId(b'0'), OrderNumber(2)),
                               AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')),
                               Timeout(0), Timestamp(0.0), True)
        self.order_bid = Order(OrderId(TraderId(b'0'), OrderNumber(2)),
                               AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')),
                               Timeout(0), Timestamp(0.0), False)

    def test_is_ask(self):
        # Test 'is ask' function
        self.assertTrue(self.tick.is_ask())
        self.assertFalse(self.tick2.is_ask())

    def test_to_network(self):
        # Test for to network
        self.assertEquals((TraderId(b'0'), self.tick.timestamp, OrderNumber(1),
                           AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), self.tick.timeout, 0),
                          self.tick.to_network())

    def test_traded_setter(self):
        # Test for traded setter
        self.tick.traded = 10
        self.assertEqual(10, self.tick.traded)

    def test_from_order_ask(self):
        # Test for from order
        ask = Tick.from_order(self.order_ask)
        self.assertIsInstance(ask, Ask)
        self.assertEqual(self.tick2.price, ask.price)
        self.assertEqual(self.tick2.assets, ask.assets)
        self.assertEqual(self.tick2.timestamp, ask.timestamp)
        self.assertEqual(self.tick2.order_id, ask.order_id)
        self.assertEqual(self.tick2.traded, 0)

    def test_from_order_bid(self):
        # Test for from order
        bid = Tick.from_order(self.order_bid)
        self.assertIsInstance(bid, Bid)
        self.assertEqual(self.tick2.price, bid.price)
        self.assertEqual(self.tick2.assets, bid.assets)
        self.assertEqual(self.tick2.timestamp, bid.timestamp)
        self.assertEqual(self.tick2.order_id, bid.order_id)
        self.assertEqual(self.tick2.traded, 0)

    def test_to_dictionary(self):
        """
        Test the to dictionary method of a tick
        """
        self.assertDictEqual(self.tick.to_dictionary(), {
            "trader_id": '0',
            "order_number": 1,
            "assets": self.tick.assets.to_dictionary(),
            "timeout": 30,
            "timestamp": 0.0,
            "traded": 0,
            "block_hash": hexlify(b'0' * 32)
        })
