import unittest

from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy, MatchingStrategy
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tickentry import TickEntry
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.message_repository import MessageRepository, MemoryMessageRepository


class MatchingStrategyTestSuite(unittest.TestCase):
    """Matching strategy test cases."""

    def setUp(self):
        # Object creation
        self.order = Order(OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(30),
                           Timeout(0.0), Timestamp(10.0), False)
        self.matching_strategy = MatchingStrategy(OrderBook(MemoryMessageRepository('trader_id')))

    def test_match_order(self):
        # Test for match order
        self.assertEquals(NotImplemented, self.matching_strategy.match_order(self.order))


class PriceTimeStrategyTestSuite(unittest.TestCase):
    """Price time strategy test cases."""

    def setUp(self):
        # Object creation
        self.ask = Ask(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                       OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(30),
                       Timeout(float('inf')), Timestamp(float('inf')))
        self.bid = Bid(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                       OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(30),
                       Timeout(float('inf')), Timestamp(float('inf')))
        self.ask_order = Order(OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(30),
                               Timeout(float('inf')), Timestamp(float('inf')), True)
        self.bid_order = Order(OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(30),
                               Timeout(float('inf')), Timestamp(float('inf')), False)
        self.price_level_ask = PriceLevel()
        self.tick_entry_ask = TickEntry(self.ask, self.price_level_ask)
        self.price_level_bid = PriceLevel()
        self.tick_entry_bid = TickEntry(self.bid, self.price_level_bid)

        self.order_book = OrderBook(MemoryMessageRepository('trader_id'))
        self.price_time_strategy = PriceTimeStrategy(self.order_book)


class MatchingEngineTestSuite(unittest.TestCase):
    """Matching engine test cases."""

    def setUp(self):
        # Object creation
        self.ask = Ask(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                       OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(30),
                       Timeout(float('inf')), Timestamp(float('inf')))
        self.bid_order = Order(OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(30),
                               Timeout(float('inf')), Timestamp(float('inf')), False)
        self.order_book = OrderBook(MemoryMessageRepository('trader_id'))
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))


if __name__ == '__main__':
    unittest.main()
