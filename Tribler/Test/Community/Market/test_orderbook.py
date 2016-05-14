import unittest

from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.trade import Trade, ProposedTrade, DeclinedTrade, AcceptedTrade
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.message_repository import MessageRepository, MemoryMessageRepository


class OrderBookTestSuite(unittest.TestCase):
    """OrderBook test cases."""

    def setUp(self):
        # Object creation
        self.ask = Ask(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                       OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(30),
                       Timeout(1462224447.117), Timestamp(1462224447.117))
        self.ask2 = Ask(MessageId(TraderId('trader_id2'), MessageNumber('message_number')),
                        OrderId(TraderId('trader_id2'), OrderNumber("order_number")), Price(400), Quantity(30),
                        Timeout(1462224447.117), Timestamp(1462224447.117))
        self.bid = Bid(MessageId(TraderId('trader_id3'), MessageNumber('message_number')),
                       OrderId(TraderId('trader_id3'), OrderNumber("order_number")), Price(200), Quantity(30),
                       Timeout(1462224447.117), Timestamp(1462224447.117))
        self.bid2 = Bid(MessageId(TraderId('trader_id4'), MessageNumber('message_number')),
                        OrderId(TraderId('trader_id4'), OrderNumber("order_number")), Price(300), Quantity(30),
                        Timeout(1462224447.117), Timestamp(1462224447.117))
        self.trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                   MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                   MessageId(TraderId('trader_id'), MessageNumber('message_number')), Price(100),
                                   Quantity(30), Timestamp(1462224447.117))
        self.order_book = OrderBook(MemoryMessageRepository('trader_id'))

    def test_ask_insertion(self):
        # Test for ask insertion
        self.order_book.insert_ask(self.ask2)
        self.assertTrue(self.order_book.tick_exists(MessageId(TraderId('trader_id2'), MessageNumber('message_number'))))

    def test_bid_insertion(self):
        # Test for bid insertion
        self.order_book.insert_bid(self.bid2)
        self.assertTrue(self.order_book.tick_exists(MessageId(TraderId('trader_id4'), MessageNumber('message_number'))))

    def test_trade_insertion(self):
        # Test for trade insertion
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)

    def test_properties(self):
        # Test for properties
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Price(350), self.order_book.mid_price)
        self.assertEquals(Price(100), self.order_book.bid_ask_spread)

    def test_tick_price(self):
        # Test for tick price
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Price(300), self.order_book.relative_tick_price(self.ask))
        self.assertEquals(Price(100), self.order_book.relative_tick_price(self.bid))

    def test_bid_ask_price_level(self):
        self.order_book.insert_ask(self.ask)
        self.assertEquals('0.0030\t@\t0.0100\n', str(self.order_book.ask_price_level))

    def test_bid_price_level(self):
        # Test for tick price
        self.order_book.insert_bid(self.bid2)
        self.assertEquals('0.0030\t@\t0.0300\n', str(self.order_book.bid_price_level))

    def test_ask_side_depth(self):
        # Test for ask side depth
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        self.assertEquals(Quantity(30), self.order_book.ask_side_depth(Price(100)))
        self.assertEquals([(Price(100), Quantity(30)), (Price(400), Quantity(30))],
                          self.order_book.ask_side_depth_profile)

    def test_bid_side_depth(self):
        # Test for bid side depth
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Quantity(30), self.order_book.bid_side_depth(Price(300)))
        self.assertEquals([(Price(200), Quantity(30)), (Price(300), Quantity(30))],
                          self.order_book.bid_side_depth_profile)

    def test_remove_tick(self):
        # Test for tick removal
        self.order_book.remove_tick(MessageId(TraderId('trader_id2'), MessageNumber('message_number')))
        self.order_book.remove_tick(MessageId(TraderId('trader_id4'), MessageNumber('message_number')))

    def test_str(self):
        # Test for order book string representation
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)

        self.assertEquals('------ Bids -------\n'
                          '0.0030\t@\t0.0200\n\n'
                          '------ Asks -------\n'
                          '0.0030\t@\t0.0100\n\n'
                          '------ Trades ------\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n\n', str(self.order_book))


if __name__ == '__main__':
    unittest.main()
