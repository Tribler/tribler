from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class PriceTimeStrategyTestSuite(AbstractServer):
    """Price time strategy test cases."""

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(PriceTimeStrategyTestSuite, self).setUp(annotate=annotate)
        # Object creation
        self.ask = Ask(OrderId(TraderId('0'), OrderNumber(1)),
                       AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())
        self.ask2 = Ask(OrderId(TraderId('1'), OrderNumber(2)),
                        AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())
        self.ask3 = Ask(OrderId(TraderId('0'), OrderNumber(3)),
                        AssetPair(AssetAmount(40000, 'BTC'), AssetAmount(200, 'MB')), Timeout(100), Timestamp.now())
        self.ask4 = Ask(OrderId(TraderId('1'), OrderNumber(4)),
                        AssetPair(AssetAmount(3000, 'A'), AssetAmount(3000, 'MB')), Timeout(100), Timestamp.now())
        self.ask5 = Ask(OrderId(TraderId('1'), OrderNumber(4)),
                        AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'C')), Timeout(100), Timestamp.now())

        self.bid = Bid(OrderId(TraderId('0'), OrderNumber(5)),
                       AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())
        self.bid2 = Bid(OrderId(TraderId('0'), OrderNumber(6)),
                        AssetPair(AssetAmount(6000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())

        self.ask_order = Order(OrderId(TraderId('9'), OrderNumber(11)),
                               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')),
                               Timeout(100), Timestamp.now(), True)
        self.ask_order2 = Order(OrderId(TraderId('9'), OrderNumber(12)),
                                AssetPair(AssetAmount(600, 'BTC'), AssetAmount(60, 'MB')),
                                Timeout(100), Timestamp.now(), True)

        self.bid_order = Order(OrderId(TraderId('9'), OrderNumber(13)),
                               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')),
                               Timeout(100), Timestamp.now(), False)
        self.bid_order2 = Order(OrderId(TraderId('9'), OrderNumber(14)),
                                AssetPair(AssetAmount(6000, 'BTC'), AssetAmount(60, 'MB')),
                                Timeout(100), Timestamp.now(), False)
        self.order_book = OrderBook()
        self.price_time_strategy = PriceTimeStrategy(self.order_book)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.order_book.shutdown_task_manager()
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
        self.order_book.insert_ask(self.ask4)
        self.assertEqual([], self.price_time_strategy.match(self.bid_order.order_id,
                                                            self.bid_order.price,
                                                            self.bid_order.available_quantity, False))

    def test_match_order_other_quantity(self):
        """
        Test whether two ticks with different quantity types are not matched
        """
        self.order_book.insert_ask(self.ask5)
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
        self.assertEquals(3000, matching_ticks[0][2])

    def test_match_order_bid(self):
        """
        Test for match bid order
        """
        self.order_book.insert_ask(self.ask)
        matching_ticks = self.price_time_strategy.match(self.bid_order.order_id, self.bid_order.price,
                                                        self.bid_order.available_quantity, False)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(self.order_book.get_tick(self.ask.order_id), matching_ticks[0][1])
        self.assertEquals(3000, matching_ticks[0][2])

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
        self.assertEquals(3000, matching_ticks[0][2])
        self.assertEquals(3000, matching_ticks[1][2])

    def test_match_order_partial_ask(self):
        """
        Test partial matching of a bid order with the matching engine
        """
        self.ask.traded = 1000
        self.order_book.insert_ask(self.ask)
        matching_ticks = self.price_time_strategy.match(self.bid_order.order_id,
                                                        self.bid_order.price,
                                                        self.bid_order.available_quantity, False)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(2000, matching_ticks[0][2])

    def test_match_order_partial_bid(self):
        """
        Test partial matching of an ask order with the matching engine
        """
        self.bid.traded = 1000
        self.order_book.insert_bid(self.bid)
        matching_ticks = self.price_time_strategy.match(self.ask_order.order_id,
                                                        self.ask_order.price,
                                                        self.ask_order.available_quantity, True)
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(2000, matching_ticks[0][2])

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
                                                        self.bid_order.available_quantity, False)
        self.assertEquals(0, len(matching_ticks))


class MatchingEngineTestSuite(AbstractServer):
    """Matching engine test cases."""

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(MatchingEngineTestSuite, self).setUp(annotate=annotate)
        # Object creation
        self.ask = Ask(OrderId(TraderId('2'), OrderNumber(1)),
                       AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp.now())
        self.bid = Bid(OrderId(TraderId('4'), OrderNumber(2)),
                       AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp.now())
        self.ask_order = Order(OrderId(TraderId('5'), OrderNumber(3)),
                               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')),
                               Timeout(30), Timestamp.now(), True)
        self.bid_order = Order(OrderId(TraderId('6'), OrderNumber(4)),
                               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')),
                               Timeout(30), Timestamp.now(), False)
        self.order_book = OrderBook()
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))

        self.ask_count = 2
        self.bid_count = 2

    def create_ask(self, amount1, amount2):
        """
        Create an ask with a specific price and quantity
        """
        new_ask = Ask(OrderId(TraderId('2'), OrderNumber(self.ask_count)),
                      AssetPair(AssetAmount(amount1, 'BTC'), AssetAmount(amount2, 'MB')), Timeout(30), Timestamp.now())
        self.ask_count += 1
        return new_ask

    def create_bid(self, amount1, amount2):
        """
        Create a bid with a specific price and quantity
        """
        new_bid = Bid(OrderId(TraderId('2'), OrderNumber(self.bid_count)),
                      AssetPair(AssetAmount(amount1, 'BTC'), AssetAmount(amount2, 'MB')), Timeout(30), Timestamp.now())
        self.bid_count += 1
        return new_bid

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.order_book.shutdown_task_manager()
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
        self.assertEquals(3000, matching_ticks[0][2])

    def test_match_order_ask(self):
        # Test for match ask order
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_ask(self.ask)
        matching_ticks = self.matching_engine.match(self.order_book.get_ask(self.ask.order_id))
        self.assertEquals(1, len(matching_ticks))
        self.assertEquals(3000, matching_ticks[0][2])

    def test_no_match_reserved(self):
        """
        Test whether there is no match when we already reserved some quantity
        """
        self.order_book.insert_bid(self.bid)
        self.order_book.get_tick(self.bid.order_id).reserve_for_matching(3000)
        self.order_book.insert_ask(self.ask)
        matching_ticks = self.matching_engine.match(self.order_book.get_ask(self.ask.order_id))
        self.assertEquals([], matching_ticks)

    def test_multiple_price_levels_asks(self):
        """
        Test matching when there are asks in multiple price levels
        """
        self.order_book.insert_ask(self.create_ask(50, 350))
        self.order_book.insert_ask(self.create_ask(18, 72))
        self.order_book.insert_ask(self.create_ask(100, 700))
        my_bid = self.create_bid(200, 2000)
        self.order_book.insert_bid(my_bid)
        matching_ticks = self.matching_engine.match(self.order_book.get_bid(my_bid.order_id))

        self.assertEqual(len(matching_ticks), 3)
        total_matched = sum([quantity for _, _, quantity in matching_ticks])
        self.assertEqual(total_matched, 168)

    def test_multiple_price_levels_bids(self):
        """
        Test matching when there are bids in multiple price levels
        """
        self.order_book.insert_bid(self.create_bid(50, 200))
        self.order_book.insert_bid(self.create_bid(18, 72))
        self.order_book.insert_bid(self.create_bid(100, 400))
        my_ask = self.create_ask(200, 200)
        self.order_book.insert_ask(my_ask)
        matching_ticks = self.matching_engine.match(self.order_book.get_ask(my_ask.order_id))

        self.assertEqual(len(matching_ticks), 3)
        total_matched = sum([quantity for _, _, quantity in matching_ticks])
        self.assertEqual(total_matched, 168)

    def test_price_time_priority_asks(self):
        """
        Test whether the price-time priority works correctly
        """
        self.order_book.insert_ask(self.create_ask(20, 100))
        self.order_book.insert_ask(self.create_ask(25, 125))
        self.order_book.insert_ask(self.create_ask(10, 50))

        my_bid = self.create_bid(50, 250)
        self.order_book.insert_bid(my_bid)
        matching_ticks = self.matching_engine.match(self.order_book.get_bid(my_bid.order_id))

        self.assertEqual(len(matching_ticks), 3)
        self.assertEqual(matching_ticks[-1][1].assets.first.amount, 10)
        self.assertEqual(matching_ticks[-1][2], 5)

    def test_price_time_priority_bids(self):
        """
        Test whether the price-time priority works correctly
        """
        self.order_book.insert_bid(self.create_bid(20, 100))
        self.order_book.insert_bid(self.create_bid(25, 125))
        self.order_book.insert_bid(self.create_bid(10, 50))

        my_ask = self.create_ask(50, 250)
        self.order_book.insert_ask(my_ask)
        matching_ticks = self.matching_engine.match(self.order_book.get_ask(my_ask.order_id))

        self.assertEqual(len(matching_ticks), 3)
        self.assertEqual(matching_ticks[-1][1].assets.first.amount, 10)
        self.assertEqual(matching_ticks[-1][2], 5)

    def test_matching_multiple_levels(self):
        """
        Test a matching with multiple price levels
        """
        self.order_book.insert_bid(self.create_bid(10, 60))
        self.order_book.insert_bid(self.create_bid(10, 50))
        my_ask = self.create_ask(30, 180)
        self.order_book.insert_ask(my_ask)
        matching_ticks = self.matching_engine.match(self.order_book.get_ask(my_ask.order_id))
        self.assertEqual(len(matching_ticks), 1)
