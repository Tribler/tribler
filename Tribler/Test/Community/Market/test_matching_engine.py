import unittest

from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy, MatchingStrategy
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.message_repository import MessageRepository, MemoryMessageRepository


class MatchingEngineTestSuite(unittest.TestCase):
    """Matching engine test cases."""

    def test_matching_strategy(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(100)
        quantity = Quantity(30)
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)
        order_id = OrderId(trader_id, OrderNumber("order_number"))
        memory_message_repository = MemoryMessageRepository('trader_id')

        ask = Ask(message_id, order_id, price, quantity, timeout, timestamp)
        order_book = OrderBook(memory_message_repository)
        matching_strategy = MatchingStrategy(order_book)

    def test_matching_engine(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)
        order_id = OrderId(trader_id, OrderNumber("order_number"))
        memory_message_repository = MemoryMessageRepository('trader_id')

        ask = Ask(MessageId(TraderId('1'), message_number), order_id, Price(100), Quantity(30), timeout,
                  timestamp)
        ask2 = Ask(MessageId(TraderId('2'), message_number), order_id, Price(400), Quantity(30), timeout,
                   timestamp)
        ask3 = Ask(MessageId(TraderId('2'), message_number), order_id, Price(50), Quantity(60), timeout,
                   timestamp)
        bid = Bid(MessageId(TraderId('3'), message_number), order_id, Price(200), Quantity(30), timeout,
                  timestamp)
        bid2 = Bid(MessageId(TraderId('4'), message_number), order_id, Price(300), Quantity(30), timeout,
                   timestamp)
        bid3 = Bid(MessageId(TraderId('5'), message_number), order_id, Price(300), Quantity(60), timeout,
                   timestamp)

        order_book = OrderBook(memory_message_repository)

        price_time_strategy = PriceTimeStrategy(order_book)
        matching_engine = MatchingEngine(price_time_strategy)

        # Insert ticks in order book
        order_book.insert_ask(ask)
        order_book.insert_ask(ask2)
        order_book.insert_bid(bid)
        order_book.insert_bid(bid2)


if __name__ == '__main__':
    unittest.main()
