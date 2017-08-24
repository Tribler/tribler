import os

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.twisted_thread import deferred
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.message_repository import MemoryMessageRepository
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.orderbook import OrderBook, DatabaseOrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.database import MarketDB
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTestOrderBook(AbstractServer):
    """
    Base class for the order book tests.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(AbstractTestOrderBook, self).setUp(annotate=annotate)
        # Object creation
        self.ask = Ask(MessageId(TraderId('0'), MessageNumber('message_number')),
                       OrderId(TraderId('0'), OrderNumber(1)), Price(100, 'BTC'), Quantity(30, 'MC'),
                       Timeout(1462224447.117), Timestamp(1462224447.117))
        self.invalid_ask = Ask(MessageId(TraderId('0'), MessageNumber('message_number')),
                               OrderId(TraderId('0'), OrderNumber(1)), Price(100, 'BTC'), Quantity(30, 'MC'),
                               Timeout(0), Timestamp(0.0))
        self.ask2 = Ask(MessageId(TraderId('1'), MessageNumber('message_number')),
                        OrderId(TraderId('1'), OrderNumber(1)), Price(400, 'BTC'), Quantity(30, 'MC'),
                        Timeout(1462224447.117), Timestamp(1462224447.117))
        self.bid = Bid(MessageId(TraderId('2'), MessageNumber('message_number')),
                       OrderId(TraderId('2'), OrderNumber(1)), Price(200, 'BTC'), Quantity(30, 'MC'),
                       Timeout(1462224447.117), Timestamp(1462224447.117))
        self.invalid_bid = Bid(MessageId(TraderId('0'), MessageNumber('message_number')),
                               OrderId(TraderId('0'), OrderNumber(1)), Price(100, 'BTC'), Quantity(30, 'MC'),
                               Timeout(0), Timestamp(0.0))
        self.bid2 = Bid(MessageId(TraderId('3'), MessageNumber('message_number')),
                        OrderId(TraderId('3'), OrderNumber(1)), Price(300, 'BTC'), Quantity(30, 'MC'),
                        Timeout(1462224447.117), Timestamp(1462224447.117))
        self.trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                   OrderId(TraderId('0'), OrderNumber(1)),
                                   OrderId(TraderId('0'), OrderNumber(1)), Price(100, 'BTC'),
                                   Quantity(30, 'MC'), Timestamp(1462224447.117))
        self.order_book = OrderBook()

    def tearDown(self, annotate=True):
        self.order_book.cancel_all_pending_tasks()
        super(AbstractTestOrderBook, self).tearDown(annotate=annotate)


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

    @deferred(timeout=10)
    def test_ask_insertion_invalid(self):
        """
        Test whether we get an error when we add an invalid ask to the order book
        """
        return self.order_book.insert_ask(self.invalid_ask)

    @deferred(timeout=10)
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
        self.assertEquals(Price(350, 'BTC'), self.order_book.get_mid_price('BTC', 'MC'))
        self.assertEquals(Price(100, 'BTC'), self.order_book.get_bid_ask_spread('BTC', 'MC'))

    def test_tick_price(self):
        # Test for tick price
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Price(300, 'BTC'), self.order_book.relative_tick_price(self.ask))
        self.assertEquals(Price(100, 'BTC'), self.order_book.relative_tick_price(self.bid))

    def test_bid_ask_price_level(self):
        self.order_book.insert_ask(self.ask)
        self.assertEquals('30.000000 MC\t@\t100.000000 BTC\n', str(self.order_book.get_ask_price_level('BTC', 'MC')))

    def test_bid_price_level(self):
        # Test for tick price
        self.order_book.insert_bid(self.bid2)
        self.assertEquals('30.000000 MC\t@\t300.000000 BTC\n', str(self.order_book.get_bid_price_level('BTC', 'MC')))

    def test_ask_side_depth(self):
        # Test for ask side depth
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        self.assertEquals(Quantity(30, 'MC'), self.order_book.ask_side_depth(Price(100, 'BTC')))
        self.assertEquals([(Price(100, 'BTC'), Quantity(30, 'MC')), (Price(400, 'BTC'), Quantity(30, 'MC'))],
                          self.order_book.get_ask_side_depth_profile('BTC', 'MC'))

    def test_bid_side_depth(self):
        # Test for bid side depth
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Quantity(30, 'MC'), self.order_book.bid_side_depth(Price(300, 'BTC')))
        self.assertEquals([(Price(200, 'BTC'), Quantity(30, 'MC')), (Price(300, 'BTC'), Quantity(30, 'MC'))],
                          self.order_book.get_bid_side_depth_profile('BTC', 'MC'))

    def test_remove_tick(self):
        # Test for tick removal
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.order_book.remove_tick(self.ask2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.ask2.order_id))
        self.order_book.remove_tick(self.bid2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.bid2.order_id))

    def test_trade_tick(self):
        """
        Test the trade tick method in an order book
        """
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)

        # Reserve quantities for matching
        self.order_book.get_tick(self.ask.order_id).reserve_for_matching(Quantity(20, 'MC'))
        self.order_book.get_tick(self.bid.order_id).reserve_for_matching(Quantity(20, 'MC'))
        self.order_book.get_tick(self.ask2.order_id).reserve_for_matching(Quantity(30, 'MC'))
        self.order_book.get_tick(self.bid2.order_id).reserve_for_matching(Quantity(30, 'MC'))

        # Trade self.ask <-> self.bid
        self.order_book.trade_tick(self.ask.order_id, self.bid.order_id, Quantity(20, 'MC'), unreserve=True)
        self.assertTrue(self.order_book.tick_exists(self.ask.order_id))
        self.assertTrue(self.order_book.tick_exists(self.bid.order_id))
        self.assertEqual(self.order_book.get_tick(self.ask.order_id).tick.quantity, Quantity(10, 'MC'))
        self.assertEqual(self.order_book.get_tick(self.bid.order_id).tick.quantity, Quantity(10, 'MC'))

        # Trade self.bid2 <-> self.ask2
        self.order_book.trade_tick(self.bid2.order_id, self.ask2.order_id, Quantity(30, 'MC'), unreserve=True)
        self.assertFalse(self.order_book.tick_exists(self.ask2.order_id))
        self.assertFalse(self.order_book.tick_exists(self.bid2.order_id))

    def test_get_order_ids(self):
        """
        Test the get order IDs function in order book
        """
        self.assertFalse(self.order_book.get_order_ids())
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)
        self.assertEqual(len(self.order_book.get_order_ids()), 2)

    def test_str(self):
        # Test for order book string representation
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)

        self.assertEquals('------ Bids -------\n'
                          '30.000000 MC\t@\t200.000000 BTC\n\n'
                          '------ Asks -------\n'
                          '30.000000 MC\t@\t100.000000 BTC\n\n', str(self.order_book))


class TestDatabaseOrderBook(AbstractTestOrderBook):
    """
    This class contains tests for the database order book.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestDatabaseOrderBook, self).setUp(annotate=annotate)

        path = os.path.join(self.getStateDir(), 'sqlite')
        if not os.path.exists(path):
            os.makedirs(path)

        self.database = MarketDB(self.getStateDir(), 'market')
        self.order_book = DatabaseOrderBook(self.database)

    @blocking_call_on_reactor_thread
    def test_save_to_db(self):
        """
        Test whether ticks from the order book are correctly saved to the database
        """
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)
        self.order_book.save_to_database()

        self.assertEqual(len(self.database.get_ticks()), 2)

    @blocking_call_on_reactor_thread
    def test_restore_from_db(self):
        """
        Test whether ticks from the database are correctly restored to the order book
        """
        self.database.add_tick(self.ask)
        self.database.add_tick(self.bid)
        self.order_book.restore_from_database()

        self.assertEqual(len(self.order_book.asks), 1)
        self.assertEqual(len(self.order_book.bids), 1)
