import unittest

from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy, MatchingStrategy
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.message_repository import MemoryMessageRepository
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class MatchingStrategyTestSuite(unittest.TestCase):
    """Matching strategy test cases."""

    def setUp(self):
        # Object creation
        self.order = Order(OrderId(TraderId('0'), OrderNumber("order_number")), Price(100), Quantity(30),
                           Timeout(0.0), Timestamp(10.0), False)
        self.matching_strategy = MatchingStrategy(OrderBook(MemoryMessageRepository('0')))

    def test_match_order(self):
        # Test for match order
        self.assertEquals(NotImplemented, self.matching_strategy.match_order(self.order))


class PriceTimeStrategyTestSuite(unittest.TestCase):
    """Price time strategy test cases."""

    def setUp(self):
        # Object creation
        self.ask = Ask(MessageId(TraderId('0'), MessageNumber('1')), OrderId(TraderId('0'), OrderNumber("1")),
                       Price(100), Quantity(30), Timeout(float('inf')), Timestamp(float('inf')))
        self.ask2 = Ask(MessageId(TraderId('1'), MessageNumber('1')), OrderId(TraderId('1'), OrderNumber("2")),
                        Price(100), Quantity(30), Timeout(float('inf')), Timestamp(float('inf')))
        self.ask3 = Ask(MessageId(TraderId('3'), MessageNumber('1')), OrderId(TraderId('0'), OrderNumber("3")),
                        Price(200), Quantity(200), Timeout(float('inf')), Timestamp(float('inf')))
        self.ask4 = Ask(MessageId(TraderId('4'), MessageNumber('1')), OrderId(TraderId('1'), OrderNumber("4")),
                        Price(50), Quantity(200), Timeout(float('inf')), Timestamp(float('inf')))
        self.bid = Bid(MessageId(TraderId('5'), MessageNumber('2')), OrderId(TraderId('0'), OrderNumber("5")),
                       Price(100), Quantity(30), Timeout(float('inf')), Timestamp(float('inf')))
        self.bid2 = Bid(MessageId(TraderId('6'), MessageNumber('2')), OrderId(TraderId('0'), OrderNumber("6")),
                        Price(200), Quantity(30), Timeout(float('inf')), Timestamp(float('inf')))
        self.bid3 = Bid(MessageId(TraderId('7'), MessageNumber('2')), OrderId(TraderId('0'), OrderNumber("7")),
                        Price(50), Quantity(200), Timeout(float('inf')), Timestamp(float('inf')))
        self.bid4 = Bid(MessageId(TraderId('8'), MessageNumber('2')), OrderId(TraderId('0'), OrderNumber("8")),
                        Price(100), Quantity(200), Timeout(float('inf')), Timestamp(float('inf')))

        self.ask_order = Order(OrderId(TraderId('9'), OrderNumber("11")), Price(100), Quantity(30),
                               Timeout(float('inf')), Timestamp(float('inf')), True)
        self.ask_order2 = Order(OrderId(TraderId('9'), OrderNumber("12")), Price(10), Quantity(60),
                                Timeout(float('inf')), Timestamp(float('inf')), True)
        self.bid_order = Order(OrderId(TraderId('9'), OrderNumber("13")), Price(100), Quantity(30),
                               Timeout(float('inf')), Timestamp(float('inf')), False)
        self.bid_order2 = Order(OrderId(TraderId('9'), OrderNumber("14")), Price(100), Quantity(60),
                                Timeout(float('inf')), Timestamp(float('inf')), False)
        self.order_book = OrderBook(MemoryMessageRepository('0'))
        self.price_time_strategy = PriceTimeStrategy(self.order_book)

    def test_empty_match_order(self):
        # Test for match order with an empty order book
        self.assertEquals([], self.price_time_strategy.match_order(self.bid_order))
        self.assertEquals([], self.price_time_strategy.match_order(self.ask_order))

    def test_match_order_ask(self):
        # Test for match order
        self.order_book.insert_bid(self.bid)
        proposed_trades = self.price_time_strategy.match_order(self.ask_order)
        self.assertEquals(1, len(proposed_trades))
        self.assertEquals(Price(100), proposed_trades[0].price)
        self.assertEquals(Quantity(30), proposed_trades[0].quantity)

    def test_match_order_bid(self):
        # Test for match order
        self.order_book.insert_ask(self.ask)
        proposed_trades = self.price_time_strategy.match_order(self.bid_order)
        self.assertEquals(1, len(proposed_trades))
        self.assertEquals(Price(100), proposed_trades[0].price)
        self.assertEquals(Quantity(30), proposed_trades[0].quantity)

    def test_match_order_divided(self):
        # Test for match order divided over two ticks
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        proposed_trades = self.price_time_strategy.match_order(self.bid_order2)
        self.assertEquals(2, len(proposed_trades))
        self.assertEquals(Price(100), proposed_trades[0].price)
        self.assertEquals(Quantity(30), proposed_trades[0].quantity)
        self.assertEquals(Price(100), proposed_trades[1].price)
        self.assertEquals(Quantity(30), proposed_trades[1].quantity)

    def test_match_bid_order_insufficient(self):
        # Test for match order with insufficient tick quantity
        self.order_book.insert_ask(self.ask)
        proposed_trades = self.price_time_strategy.match_order(self.bid_order2)
        self.assertEquals(0, len(proposed_trades))

    def test_match_ask_order_insufficient(self):
        # Test for match order with insufficient tick quantity
        self.order_book.insert_bid(self.bid)
        proposed_trades = self.price_time_strategy.match_order(self.ask_order2)
        self.assertEquals(0, len(proposed_trades))

    def test_match_order_different_price_level(self):
        # Test for match order given an ask order and bid in different price levels
        self.order_book.insert_bid(self.bid2)
        proposed_trades = self.price_time_strategy.match_order(self.ask_order)
        self.assertEquals(1, len(proposed_trades))
        self.assertEquals(Price(200), proposed_trades[0].price)
        self.assertEquals(Quantity(30), proposed_trades[0].quantity)

    def test_search_for_quantity_in_order_book_partial_ask_low(self):
        # Test for protected search for quantity in order book partial ask when price is too low
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_bid(self.bid2)
        self.order_book.insert_bid(self.bid3)
        self.order_book.insert_bid(self.bid4)
        quantity_to_trade, proposed_trades = self.price_time_strategy._search_for_quantity_in_order_book_partial_ask(
            Price(100), Quantity(30), [],
            self.ask_order2)
        self.assertEquals(1, len(proposed_trades))
        self.assertEquals(Quantity(0), quantity_to_trade)

    def test_search_for_quantity_in_order_book_partial_ask(self):
        # Test for protected search for quantity in order book partial ask
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_bid(self.bid2)
        self.order_book.insert_bid(self.bid3)
        self.order_book.insert_bid(self.bid4)
        quantity_to_trade, proposed_trades = self.price_time_strategy._search_for_quantity_in_order_book_partial_ask(
            Price(100), Quantity(30), [],
            self.ask_order)
        self.assertEquals(0, len(proposed_trades))
        self.assertEquals(Quantity(30), quantity_to_trade)

    def test_search_for_quantity_in_order_book_partial_bid_high(self):
        # Test for protected search for quantity in order book partial bid when price is too high
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_ask(self.ask3)
        self.order_book.insert_ask(self.ask4)
        quantity_to_trade, proposed_trades = self.price_time_strategy._search_for_quantity_in_order_book_partial_bid(
            Price(100), Quantity(30), [],
            self.bid_order)
        self.assertEquals(0, len(proposed_trades))
        self.assertEquals(Quantity(30), quantity_to_trade)

    def test_search_for_quantity_in_order_book_partial_bid(self):
        # Test for protected search for quantity in order book partial bid
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_ask(self.ask3)
        self.order_book.insert_ask(self.ask4)
        quantity_to_trade, proposed_trades = self.price_time_strategy._search_for_quantity_in_order_book_partial_bid(
            Price(50), Quantity(30), [],
            self.bid_order)
        self.assertEquals(1, len(proposed_trades))
        self.assertEquals(Quantity(0), quantity_to_trade)


class MatchingEngineTestSuite(unittest.TestCase):
    """Matching engine test cases."""

    def setUp(self):
        # Object creation
        self.ask = Ask(MessageId(TraderId('1'), MessageNumber('message_number1')),
                       OrderId(TraderId('2'), OrderNumber("order_number")), Price(100), Quantity(30),
                       Timeout(float('inf')), Timestamp(float('inf')))
        self.bid = Bid(MessageId(TraderId('3'), MessageNumber('message_number2')),
                       OrderId(TraderId('4'), OrderNumber("order_number")), Price(100), Quantity(30),
                       Timeout(float('inf')), Timestamp(float('inf')))
        self.ask_order = Order(OrderId(TraderId('5'), OrderNumber("order_number")), Price(100), Quantity(30),
                               Timeout(float('inf')), Timestamp(float('inf')), True)
        self.bid_order = Order(OrderId(TraderId('6'), OrderNumber("order_number")), Price(100), Quantity(30),
                               Timeout(float('inf')), Timestamp(float('inf')), False)
        self.order_book = OrderBook(MemoryMessageRepository('0'))
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))

    def test_empty_match_order_empty(self):
        # Test for match order with an empty order book
        self.assertEquals([], self.matching_engine.match_order(self.bid_order))
        self.assertEquals([], self.matching_engine.match_order(self.ask_order))

    def test_match_order(self):
        # Test for match order
        self.order_book.insert_ask(self.ask)
        proposed_trades = self.matching_engine.match_order(self.bid_order)
        self.assertEquals(1, len(proposed_trades))
        self.assertEquals(Price(100), proposed_trades[0].price)
        self.assertEquals(Quantity(30), proposed_trades[0].quantity)


if __name__ == '__main__':
    unittest.main()
