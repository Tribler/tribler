from __future__ import absolute_import

import os

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.tools import trial_timeout
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade


class AbstractTestOrderBook(AbstractServer):
    """
    Base class for the order book tests.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(AbstractTestOrderBook, self).setUp()
        # Object creation
        self.ask = Ask(OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                       AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())
        self.invalid_ask = Ask(OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                               AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')), Timeout(0), Timestamp(0.0))
        self.ask2 = Ask(OrderId(TraderId(b'1' * 20), OrderNumber(1)),
                        AssetPair(AssetAmount(400, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())
        self.bid = Bid(OrderId(TraderId(b'2' * 20), OrderNumber(1)),
                       AssetPair(AssetAmount(200, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())
        self.invalid_bid = Bid(OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                               AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')), Timeout(0), Timestamp(0.0))
        self.bid2 = Bid(OrderId(TraderId(b'3' * 20), OrderNumber(1)),
                        AssetPair(AssetAmount(300, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())
        self.trade = Trade.propose(TraderId(b'0' * 20),
                                   OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                   OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                   AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')),
                                   Timestamp(1462224447.117))
        self.order_book = OrderBook()

    def tearDown(self):
        self.order_book.shutdown_task_manager()
        super(AbstractTestOrderBook, self).tearDown()


class TestOrderBook(AbstractTestOrderBook):
    """OrderBook test cases."""

    def test_timeouts(self):
        """
        Test the timeout functions of asks/bids
        """
        self.order_book.insert_ask(self.ask)
        self.assertEqual(self.order_book.timeout_ask(self.ask.order_id), self.ask)

        self.order_book.insert_bid(self.bid)
        self.assertEqual(self.order_book.timeout_bid(self.bid.order_id), self.bid)

        self.order_book.on_invalid_tick_insert(None)

    def test_ask_insertion(self):
        # Test for ask insertion
        self.order_book.insert_ask(self.ask2)
        self.assertTrue(self.order_book.tick_exists(self.ask2.order_id))
        self.assertTrue(self.order_book.ask_exists(self.ask2.order_id))
        self.assertFalse(self.order_book.bid_exists(self.ask2.order_id))
        self.assertEquals(self.ask2, self.order_book.get_ask(self.ask2.order_id).tick)

    def test_get_tick(self):
        """
        Test the retrieval of a tick from the order book
        """
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)
        self.assertTrue(self.order_book.get_tick(self.ask.order_id))
        self.assertTrue(self.order_book.get_tick(self.bid.order_id))

    @trial_timeout(10)
    def test_ask_insertion_invalid(self):
        """
        Test whether we get an error when we add an invalid ask to the order book
        """
        return self.order_book.insert_ask(self.invalid_ask)

    @trial_timeout(10)
    def test_bid_insertion_invalid(self):
        """
        Test whether we get an error when we add an invalid bid to the order book
        """
        return self.order_book.insert_bid(self.invalid_bid)

    def test_ask_removal(self):
        # Test for ask removal
        self.order_book.insert_ask(self.ask2)
        self.assertTrue(self.order_book.tick_exists(self.ask2.order_id))
        self.order_book.remove_ask(self.ask2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.ask2.order_id))

    def test_bid_insertion(self):
        # Test for bid insertion
        self.order_book.insert_bid(self.bid2)
        self.assertTrue(self.order_book.tick_exists(self.bid2.order_id))
        self.assertTrue(self.order_book.bid_exists(self.bid2.order_id))
        self.assertFalse(self.order_book.ask_exists(self.bid2.order_id))
        self.assertEquals(self.bid2, self.order_book.get_bid(self.bid2.order_id).tick)

    def test_bid_removal(self):
        # Test for bid removal
        self.order_book.insert_bid(self.bid2)
        self.assertTrue(self.order_book.tick_exists(self.bid2.order_id))
        self.order_book.remove_bid(self.bid2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.bid2.order_id))

    def test_properties(self):
        # Test for properties
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Price(0.0875, 'MB', 'BTC'), self.order_book.get_mid_price('MB', 'BTC'))
        self.assertEquals(Price(-0.025, 'MB', 'BTC'), self.order_book.get_bid_ask_spread('MB', 'BTC'))

    def test_ask_price_level(self):
        self.order_book.insert_ask(self.ask)
        price_level = self.order_book.get_ask_price_level('MB', 'BTC')
        self.assertEqual(price_level.depth, 100)

    def test_bid_price_level(self):
        # Test for tick price
        self.order_book.insert_bid(self.bid2)
        price_level = self.order_book.get_bid_price_level('MB', 'BTC')
        self.assertEqual(price_level.depth, 300)

    def test_ask_side_depth(self):
        # Test for ask side depth
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        self.assertEquals(100, self.order_book.ask_side_depth(Price(0.3, 'MB', 'BTC')))
        self.assertEquals([(Price(0.075, 'MB', 'BTC'), 400), (Price(0.3, 'MB', 'BTC'), 100)],
                          self.order_book.get_ask_side_depth_profile('MB', 'BTC'))

    def test_bid_side_depth(self):
        # Test for bid side depth
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(300, self.order_book.bid_side_depth(Price(0.1, 'MB', 'BTC')))
        self.assertEquals([(Price(0.1, 'MB', 'BTC'), 300), (Price(0.15, 'MB', 'BTC'), 200)],
                          self.order_book.get_bid_side_depth_profile('MB', 'BTC'))

    def test_remove_tick(self):
        # Test for tick removal
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.order_book.remove_tick(self.ask2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.ask2.order_id))
        self.order_book.remove_tick(self.bid2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.bid2.order_id))

    def test_get_order_ids(self):
        """
        Test the get order IDs function in order book
        """
        self.assertFalse(self.order_book.get_order_ids())
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)
        self.assertEqual(len(self.order_book.get_order_ids()), 2)

    def test_update_ticks(self):
        """
        Test updating ticks in an order book
        """
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)

        ask_dict = {
            "trader_id": self.ask.order_id.trader_id.as_hex(),
            "order_number": int(self.ask.order_id.order_number),
            "assets": self.ask.assets.to_dictionary(),
            "traded": 100,
            "timeout": 3600,
            "timestamp": float(Timestamp.now())
        }
        bid_dict = {
            "trader_id": self.bid.order_id.trader_id.as_hex(),
            "order_number": int(self.bid.order_id.order_number),
            "assets": self.bid.assets.to_dictionary(),
            "traded": 100,
            "timeout": 3600,
            "timestamp": float(Timestamp.now())
        }

        self.order_book.get_tick(self.ask.order_id).reserve_for_matching(100)
        self.order_book.get_tick(self.bid.order_id).reserve_for_matching(100)
        self.order_book.update_ticks(ask_dict, bid_dict, 100, unreserve=True)

        self.assertEqual(len(self.order_book.asks), 0)
        self.assertEqual(len(self.order_book.bids), 1)
        self.order_book.remove_bid(self.bid.order_id)

        ask_dict["traded"] = 50
        bid_dict["traded"] = 50
        self.order_book.completed_orders = []
        self.order_book.update_ticks(ask_dict, bid_dict, 100)
        self.assertEqual(len(self.order_book.asks), 1)
        self.assertEqual(len(self.order_book.bids), 1)

    def test_str(self):
        # Test for order book string representation
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)

        self.assertEquals('------ Bids -------\n'
                          '200 BTC\t@\t0.15 MB (R: 0)\n\n'
                          '------ Asks -------\n'
                          '100 BTC\t@\t0.3 MB (R: 0)\n\n', str(self.order_book))
