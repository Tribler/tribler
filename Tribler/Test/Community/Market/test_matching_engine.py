from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.message_repository import MemoryMessageRepository
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class PriceTimeStrategyTestSuite(AbstractServer):
    """Price time strategy test cases."""

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(PriceTimeStrategyTestSuite, self).setUp(annotate=annotate)
        # Object creation
        self.ask = Ask(OrderId(TraderId('0'), OrderNumber(1)), Price(100, 'BTC'), Quantity(30, 'MC'),
                       Timeout(100), Timestamp.now())
        self.ask2 = Ask(OrderId(TraderId('1'), OrderNumber(2)), Price(100, 'BTC'), Quantity(30, 'MC'),
                        Timeout(100), Timestamp.now())
        self.ask3 = Ask(OrderId(TraderId('0'), OrderNumber(3)), Price(200, 'BTC'), Quantity(200, 'MC'),
                        Timeout(100), Timestamp.now())
        self.ask4 = Ask(OrderId(TraderId('1'), OrderNumber(4)), Price(50, 'BTC'), Quantity(200, 'MC'),
                        Timeout(100), Timestamp.now())
        self.ask5 = Ask(OrderId(TraderId('1'), OrderNumber(4)), Price(100, 'A'), Quantity(30, 'MC'),
                        Timeout(100), Timestamp.now())
        self.ask6 = Ask(OrderId(TraderId('1'), OrderNumber(4)), Price(100, 'BTC'), Quantity(30, 'A'),
                        Timeout(100), Timestamp.now())

        self.bid = Bid(OrderId(TraderId('0'), OrderNumber(5)), Price(100, 'BTC'), Quantity(30, 'MC'),
                       Timeout(100), Timestamp.now())
        self.bid2 = Bid(OrderId(TraderId('0'), OrderNumber(6)), Price(200, 'BTC'), Quantity(30, 'MC'),
                        Timeout(100), Timestamp.now())
        self.bid3 = Bid(OrderId(TraderId('0'), OrderNumber(7)), Price(50, 'BTC'), Quantity(200, 'MC'),
                        Timeout(100), Timestamp.now())
        self.bid4 = Bid(OrderId(TraderId('0'), OrderNumber(8)), Price(100, 'BTC'), Quantity(200, 'MC'),
                        Timeout(100), Timestamp.now())

        self.ask_order = Order(OrderId(TraderId('9'), OrderNumber(11)), Price(100, 'BTC'), Quantity(30, 'MC'),
                               Timeout(100), Timestamp.now(), True)
        self.ask_order2 = Order(OrderId(TraderId('9'), OrderNumber(12)), Price(10, 'BTC'), Quantity(60, 'MC'),
                                Timeout(100), Timestamp.now(), True)

        self.bid_order = Order(OrderId(TraderId('9'), OrderNumber(13)), Price(100, 'BTC'), Quantity(30, 'MC'),
                               Timeout(100), Timestamp.now(), False)
        self.bid_order2 = Order(OrderId(TraderId('9'), OrderNumber(14)), Price(100, 'BTC'), Quantity(60, 'MC'),
                                Timeout(100), Timestamp.now(), False)
        self.order_book = OrderBook()
        self.price_time_strategy = PriceTimeStrategy(self.order_book)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.order_book.cancel_all_pending_tasks()
        yield super(PriceTimeStrategyTestSuite, self).tearDown(annotate=annotate)

    def test_generate_match_id(self):
        """
        Test generation of a match id
        """
        def mocked_get_random_match_id():
            if not mocked_get_random_match_id.called:
                mocked_get_random_match_id.called = True
                return 'a' * 20
            else:
                return 'b' * 20
        mocked_get_random_match_id.called = False

        rand_id = self.price_time_strategy.get_unique_match_id()
        self.assertEqual(len(rand_id), 20)
        self.assertEqual(len(self.price_time_strategy.used_match_ids), 1)

        self.price_time_strategy.get_random_match_id = mocked_get_random_match_id
        self.price_time_strategy.used_match_ids.add('a' * 20)
        self.assertEqual(self.price_time_strategy.get_unique_match_id(), 'b' * 20)

    def test_empty_match_order(self):
        """
        Test for match order with an empty order book
        """
        self.assertEquals([], self.price_time_strategy.match(self.bid_order.order_id,
                                                             self.bid_order.price,
                                                             self.bid_order.available_quantity, False))
        self.assertEquals([], self.price_time_strategy.match(self.ask_order.order_id,
                                                             self.ask_order.price,
                                                             self.ask_order.available_quantity, True))

    def test_match_order_other_price(self):
        """
        Test whether two ticks with different price types are not matched
        """
        self.order_book.insert_ask(self.ask5)
        self.assertEqual([], self.price_time_strategy.match(self.bid_order.order_id,
                                                            self.bid_order.price,
                                                            self.bid_order.available_quantity, False))

    def test_match_order_other_quantity(self):
        """
        Test whether two ticks with different quantity types are not matched
        """
        self.order_book.insert_ask(self.ask6)
        self.assertEqual([], self.price_time_strategy.match(self.bid_order.order_id,
                                                            self.bid_order.price,
                                                            self.bid_order.available_quantity, False))

    def test_match_order_ask(self):
        """
        Test for match ask order
        """
        self.order_book.insert_bid(self.bid)
        matching_ticks = self.price_time_strategy.match(self.ask_order.order_id, self.ask_order.price,
                                                        self.ask_order.available_quantity, True)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(self.order_book.get_tick(self.bid.order_id), matching_ticks[0][1])
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[0][2])

    def test_match_order_bid(self):
        """
        Test for match bid order
        """
        self.order_book.insert_ask(self.ask)
        matching_ticks = self.price_time_strategy.match(self.bid_order.order_id, self.bid_order.price,
                                                        self.bid_order.available_quantity, False)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(self.order_book.get_tick(self.ask.order_id), matching_ticks[0][1])
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[0][2])

    def test_match_order_divided(self):
        """
        Test for match order divided over two ticks
        """
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        matching_ticks = self.price_time_strategy.match(self.bid_order2.order_id,
                                                        self.bid_order2.price,
                                                        self.bid_order2.available_quantity, False)
        self.assertEquals(2, len(matching_ticks))
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[0][2])
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[1][2])

    def test_match_order_partial_ask(self):
        """
        Test partial matching of a bid order with the matching engine
        """
        self.ask._quantity = Quantity(20, 'MC')
        self.order_book.insert_ask(self.ask)
        matching_ticks = self.price_time_strategy.match(self.bid_order2.order_id,
                                                        self.bid_order2.price,
                                                        self.bid_order2.available_quantity, False)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(Quantity(20, 'MC'), matching_ticks[0][2])

    def test_match_order_partial_bid(self):
        """
        Test partial matching of an ask order with the matching engine
        """
        self.bid._quantity = Quantity(20, 'MC')
        self.order_book.insert_bid(self.bid)
        matching_ticks = self.price_time_strategy.match(self.ask_order2.order_id,
                                                        self.ask_order2.price,
                                                        self.ask_order2.available_quantity, True)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(Quantity(20, 'MC'), matching_ticks[0][2])

    def test_match_order_different_price_level(self):
        """
        Test for match order given an ask order and bid in different price levels
        """
        self.order_book.insert_bid(self.bid2)
        matching_ticks = self.price_time_strategy.match(self.ask_order.order_id, self.ask_order.price,
                                                        self.ask_order.available_quantity, True)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(Price(200, 'BTC'), self.bid2.price)
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[0][2])

    def test_search_for_quantity_in_order_book_partial_ask_low(self):
        """
        Test for protected search for quantity in order book partial ask when price is too low
        """
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_bid(self.bid2)
        self.order_book.insert_bid(self.bid3)
        self.order_book.insert_bid(self.bid4)
        matching_ticks = self.price_time_strategy._search_for_quantity_in_order_book_partial_ask(
            self.ask_order2.order_id, Price(100, 'BTC'), Quantity(30, 'MC'), [], self.ask_order2.price, True)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[0][2])

    def test_search_for_quantity_in_order_book_partial_ask(self):
        """
        Test for protected search for quantity in order book partial ask
        """
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_bid(self.bid2)
        self.order_book.insert_bid(self.bid3)
        self.order_book.insert_bid(self.bid4)
        matching_ticks = self.price_time_strategy._search_for_quantity_in_order_book_partial_ask(
            self.ask_order.order_id, Price(100, 'BTC'), Quantity(30, 'MC'), [], self.ask_order.price, True)
        self.assertEquals(0, len(matching_ticks))

    def test_search_for_quantity_in_order_book_partial_bid_high(self):
        """
        Test for protected search for quantity in order book partial bid when price is too high
        """
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_ask(self.ask3)
        self.order_book.insert_ask(self.ask4)
        matching_ticks = self.price_time_strategy._search_for_quantity_in_order_book_partial_bid(
            self.bid_order.order_id, Price(100, 'BTC'), Quantity(30, 'MC'), [], self.bid_order.price, False)
        self.assertEquals(0, len(matching_ticks))

    def test_search_for_quantity_in_order_book_partial_bid(self):
        """
        Test for protected search for quantity in order book partial bid
        """
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_ask(self.ask3)
        self.order_book.insert_ask(self.ask4)
        matching_ticks = self.price_time_strategy._search_for_quantity_in_order_book_partial_bid(
            self.bid_order.order_id, Price(50, 'BTC'), Quantity(30, 'MC'), [], self.bid_order.price, False)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[0][2])

    def test_search_for_quantity_in_price_level(self):
        """
        Test searching within a price level
        """
        self.bid_order._order_id = self.ask.order_id
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        matching_ticks = self.price_time_strategy._search_for_quantity_in_price_level(
            self.bid_order.order_id, None, Quantity(10, 'MC'), self.bid_order.price, False)
        self.assertFalse(matching_ticks)

    def test_bid_blocked_for_matching(self):
        """
        Test whether a bid tick is not matched when blocked for matching
        """
        self.order_book.insert_bid(self.bid)
        self.order_book.get_tick(self.bid.order_id).block_for_matching(self.ask_order.order_id)
        matching_ticks = self.price_time_strategy.match(self.ask_order.order_id, self.ask_order.price,
                                                        self.ask_order.available_quantity, True)
        self.assertEquals(0, len(matching_ticks))

    def test_ask_blocked_for_matching(self):
        """
        Test whether an ask tick is not matched when blocked for matching
        """
        self.order_book.insert_ask(self.ask)
        self.order_book.get_tick(self.ask.order_id).block_for_matching(self.bid_order.order_id)
        matching_ticks = self.price_time_strategy.match(self.bid_order.order_id, self.bid_order.price,
                                                        self.bid_order.available_quantity, True)
        self.assertEquals(0, len(matching_ticks))


class MatchingEngineTestSuite(AbstractServer):
    """Matching engine test cases."""

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(MatchingEngineTestSuite, self).setUp(annotate=annotate)
        # Object creation
        self.ask = Ask(OrderId(TraderId('2'), OrderNumber(1)), Price(100, 'BTC'), Quantity(30, 'MC'),
                       Timeout(30), Timestamp.now())
        self.bid = Bid(OrderId(TraderId('4'), OrderNumber(2)), Price(100, 'BTC'), Quantity(30, 'MC'),
                       Timeout(30), Timestamp.now())
        self.ask_order = Order(OrderId(TraderId('5'), OrderNumber(3)), Price(100, 'BTC'), Quantity(30, 'MC'),
                               Timeout(30), Timestamp.now(), True)
        self.bid_order = Order(OrderId(TraderId('6'), OrderNumber(4)), Price(100, 'BTC'), Quantity(30, 'MC'),
                               Timeout(30), Timestamp.now(), False)
        self.order_book = OrderBook()
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.order_book.cancel_all_pending_tasks()
        yield super(MatchingEngineTestSuite, self).tearDown(annotate=annotate)

    def test_empty_match_order_empty(self):
        # Test for match order with an empty order book
        self.order_book.insert_ask(self.ask)
        self.assertEquals([], self.matching_engine.match(self.order_book.get_ask(self.ask.order_id)))
        self.order_book.remove_ask(self.ask.order_id)

        self.order_book.insert_bid(self.bid)
        self.assertEquals([], self.matching_engine.match(self.order_book.get_bid(self.bid.order_id)))
        self.order_book.remove_bid(self.bid.order_id)

    def test_match_order_bid(self):
        # Test for match bid order
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)
        matching_ticks = self.matching_engine.match(self.order_book.get_bid(self.bid.order_id))
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[0][2])

    def test_match_order_ask(self):
        # Test for match ask order
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_ask(self.ask)
        matching_ticks = self.matching_engine.match(self.order_book.get_ask(self.ask.order_id))
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(Quantity(30, 'MC'), matching_ticks[0][2])

    def test_no_match_reserved(self):
        """
        Test whether there is no match when we already reserved some quantity
        """
        self.order_book.insert_bid(self.bid)
        self.order_book.get_tick(self.bid.order_id).reserve_for_matching(Quantity(30, 'MC'))
        self.order_book.insert_ask(self.ask)
        matching_ticks = self.matching_engine.match(self.order_book.get_ask(self.ask.order_id))
        self.assertEquals([], matching_ticks)
