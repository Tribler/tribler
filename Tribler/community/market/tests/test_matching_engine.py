import unittest

from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy, MatchingStrategy
from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price, Quantity, Timeout, Timestamp, \
    Ask, Bid, Trade


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

        ask = Ask.create(message_id, price, quantity, timeout, timestamp)
        order_book = OrderBook()
        matching_strategy = MatchingStrategy(order_book)

        # Test for match tick
        self.assertEquals(NotImplemented, matching_strategy.match_tick(ask))

    def test_matching_engine(self):
        # Object creation
        message_number = MessageNumber('message_number')
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)

        ask = Ask.create(MessageId(TraderId('1'), message_number), Price(100), Quantity(30), timeout, timestamp)
        ask2 = Ask.create(MessageId(TraderId('2'), message_number), Price(400), Quantity(30), timeout, timestamp)
        ask3 = Ask.create(MessageId(TraderId('2'), message_number), Price(50), Quantity(60), timeout, timestamp)
        bid = Bid.create(MessageId(TraderId('3'), message_number), Price(200), Quantity(30), timeout, timestamp)
        bid2 = Bid.create(MessageId(TraderId('4'), message_number), Price(300), Quantity(30), timeout, timestamp)
        bid3 = Bid.create(MessageId(TraderId('5'), message_number), Price(300), Quantity(60), timeout, timestamp)

        order_book = OrderBook()

        price_time_strategy = PriceTimeStrategy(order_book)
        matching_engine = MatchingEngine(order_book, price_time_strategy)

        # Test for match tick
        self.assertEquals([], matching_engine.match_tick(ask)[0])

        order_book.insert_ask(ask)
        order_book.insert_ask(ask2)
        order_book.insert_bid(bid)
        order_book.insert_bid(bid2)

        self.assertEquals(Price(300), matching_engine.match_tick(ask)[0][0].price)
        self.assertEquals(Price(100), matching_engine.match_tick(bid)[0][0].price)

        # Test for dividable match tick
        self.assertEquals(Quantity(30), matching_engine.match_tick(bid3)[0][0].quantity)
        self.assertEquals(Quantity(30), matching_engine.match_tick(bid3)[0][1].quantity)

if __name__ == '__main__':
    unittest.main()