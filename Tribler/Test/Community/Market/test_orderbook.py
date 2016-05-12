import unittest

from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price, Quantity, Timeout, Timestamp, \
    Ask, Bid, Trade


class OrderBookTestSuite(unittest.TestCase):
    """OrderBook test cases."""

    def test_order_book(self):
        # Object creation
        trader_id = TraderId('trader_id')
        trader_id2 = TraderId('trader_id2')
        trader_id3 = TraderId('trader_id3')
        trader_id4 = TraderId('trader_id4')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        message_id2 = MessageId(trader_id2, message_number)
        message_id3 = MessageId(trader_id3, message_number)
        message_id4 = MessageId(trader_id4, message_number)
        price = Price(100)
        price2 = Price(200)
        price3 = Price(300)
        price4 = Price(400)
        quantity = Quantity(30)
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)

        ask = Ask.create(message_id, price, quantity, timeout, timestamp)
        ask2 = Ask.create(message_id2, price4, quantity, timeout, timestamp)
        bid = Bid.create(message_id3, price2, quantity, timeout, timestamp)
        bid2 = Bid.create(message_id4, price3, quantity, timeout, timestamp)
        trade = Trade.propose(message_id, message_id, message_id, price, quantity, timestamp)

        order_book = OrderBook()

        # Test for ask, bid, and trade insertion
        order_book.insert_ask(ask2)
        order_book.insert_bid(bid2)
        order_book.insert_trade(trade)
        order_book.insert_trade(trade)
        order_book.insert_trade(trade)
        order_book.insert_trade(trade)
        order_book.insert_trade(trade)
        order_book.insert_trade(trade)

        self.assertTrue(order_book.tick_exists(message_id2))
        self.assertTrue(order_book.tick_exists(message_id4))

        # Test for properties
        self.assertEquals(Price(350), order_book.mid_price)
        self.assertEquals(Price(100), order_book.bid_ask_spread)
        self.assertEquals(Price(300), order_book.relative_tick_price(ask))
        self.assertEquals(Price(100), order_book.relative_tick_price(bid))

        order_book.insert_ask(ask)
        order_book.insert_bid(bid)

        self.assertEquals('0.0030\t@\t0.0100\n', str(order_book.ask_price_level))
        self.assertEquals('0.0030\t@\t0.0300\n', str(order_book.bid_price_level))

        # Test for ask / bid side depth
        self.assertEquals(Quantity(30), order_book.ask_side_depth(Price(200)))
        self.assertEquals(Quantity(30), order_book.bid_side_depth(Price(300)))

        # Test for ask / bid side depth profile
        self.assertEquals([(Price(100), Quantity(30)), (Price(400), Quantity(30))], order_book.ask_side_depth_profile)
        self.assertEquals([(Price(200), Quantity(30)), (Price(300), Quantity(30))], order_book.bid_side_depth_profile)

        # Test for tick removal
        order_book.remove_tick(message_id2)
        order_book.remove_tick(message_id4)

        # Test for order book string representation
        self.assertEquals('------ Bids -------\n'
                          '0.0030\t@\t0.0200\n\n'
                          '------ Asks -------\n'
                          '0.0030\t@\t0.0100\n\n'
                          '------ Trades ------\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n'
                          '0.0030 @ 0.0100 (2016-05-02 23:27:27.117000)\n\n', str(order_book))


if __name__ == '__main__':
    unittest.main()
