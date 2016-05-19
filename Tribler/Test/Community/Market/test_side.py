import unittest

from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.side import Side


class SideTestSuite(unittest.TestCase):
    """Side test cases."""

    def setUp(self):
        # Object creation

        self.tick = Tick(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                         OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(400), Quantity(30),
                         Timeout(float("inf")), Timestamp(float("inf")), True)
        self.tick2 = Tick(MessageId(TraderId('trader_id2'), MessageNumber('message_number')),
                          OrderId(TraderId('trader_id2'), OrderNumber("order_number")), Price(800), Quantity(30),
                          Timeout(float("inf")), Timestamp(float("inf")), True)
        self.side = Side()

    def test_max_price(self):
        # Test max price (list)
        self.assertEquals(None, self.side.max_price)
        self.assertEquals(None, self.side.max_price_list)

        self.side.insert_tick(self.tick)
        self.side.insert_tick(self.tick2)

        self.assertEquals('0.0030\t@\t0.0800\n', str(self.side.max_price_list))
        self.assertEquals(Price(800), self.side.max_price)

    def test_min_price(self):
        # Test min price (list)
        self.assertEquals(None, self.side.min_price_list)
        self.assertEquals(None, self.side.min_price)

        self.side.insert_tick(self.tick)
        self.side.insert_tick(self.tick2)

        self.assertEquals('0.0030\t@\t0.0400\n', str(self.side.min_price_list))
        self.assertEquals(Price(400), self.side.min_price)

    def test_insert_tick(self):
        # Test insert tick
        self.assertEquals(0, len(self.side))
        self.assertFalse(self.side.tick_exists(OrderId(TraderId('trader_id'), OrderNumber("order_number"))))

        self.side.insert_tick(self.tick)
        self.side.insert_tick(self.tick2)

        self.assertEquals(2, len(self.side))
        self.assertTrue(self.side.tick_exists(OrderId(TraderId('trader_id'), OrderNumber("order_number"))))

    def test_remove_tick(self):
        # Test remove tick
        self.side.insert_tick(self.tick)
        self.side.insert_tick(self.tick2)

        self.side.remove_tick(OrderId(TraderId('trader_id'), OrderNumber("order_number")))
        self.assertEquals(1, len(self.side))
        self.side.remove_tick(OrderId(TraderId('trader_id2'), OrderNumber("order_number")))
        self.assertEquals(0, len(self.side))


if __name__ == '__main__':
    unittest.main()
