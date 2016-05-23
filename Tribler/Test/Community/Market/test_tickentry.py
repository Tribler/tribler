import unittest

from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.tickentry import TickEntry


class OrderTestSuite(unittest.TestCase):
    """TickEntry test cases."""

    def setUp(self):
        # Object creation
        tick = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                    OrderId(TraderId('0'), OrderNumber("order_number")), Price(63400), Quantity(30),
                    Timeout(0.0), Timestamp(0.0), True)
        tick2 = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                     OrderId(TraderId('0'), OrderNumber("order_number")), Price(63400), Quantity(30),
                     Timeout(float("inf")), Timestamp(float("inf")), True)

        self.price_level = PriceLevel()
        self.tick_entry = TickEntry(tick, self.price_level)
        self.tick_entry2 = TickEntry(tick2, self.price_level)

    def test_properties(self):
        # Test properties
        self.assertEquals(OrderId(TraderId('0'), OrderNumber("order_number")), self.tick_entry.order_id)
        self.assertEquals(Price(63400), self.tick_entry.price)
        self.assertEquals(Quantity(30), self.tick_entry.quantity)

    def test_price_level(self):
        self.assertEquals(self.price_level, self.tick_entry.price_level())

    def test_next_tick(self):
        # Test for next tick
        self.assertEquals(None, self.tick_entry.next_tick())
        self.price_level.append_tick(self.tick_entry)
        self.price_level.append_tick(self.tick_entry2)
        self.assertEquals(self.tick_entry2, self.tick_entry.next_tick())

    def test_prev_tick(self):
        # Test for previous tick
        self.assertEquals(None, self.tick_entry.prev_tick())
        self.price_level.append_tick(self.tick_entry)
        self.price_level.append_tick(self.tick_entry2)
        self.assertEquals(self.tick_entry, self.tick_entry2.prev_tick())

    def test_str(self):
        # Test for tick string representation
        self.assertEquals('0.0030\t@\t6.3400', str(self.tick_entry))

    def test_is_valid(self):
        # Test for is valid
        self.assertFalse(self.tick_entry.is_valid())
        self.assertTrue(self.tick_entry2.is_valid())

    def test_quantity_setter(self):
        # Test for quantity setter
        self.price_level.append_tick(self.tick_entry)
        self.price_level.append_tick(self.tick_entry2)
        self.tick_entry.quantity = Quantity(15)
        self.assertEquals(Quantity(15), self.tick_entry.quantity)


if __name__ == '__main__':
    unittest.main()
