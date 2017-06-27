import unittest

from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.tickentry import TickEntry
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class PriceLevelTestSuite(unittest.TestCase):
    """PriceLevel test cases."""

    def setUp(self):
        # Object creation
        tick = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                    OrderId(TraderId('0'), OrderNumber(1)), Price(63400, 'BTC'), Quantity(30, 'MC'),
                    Timeout(float("inf")), Timestamp(float("inf")), True)
        tick2 = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                     OrderId(TraderId('0'), OrderNumber(2)), Price(30, 'MC'), Quantity(30, 'BTC'),
                     Timeout(float("inf")), Timestamp(float("inf")), True)

        self.price_level = PriceLevel('MC')
        self.tick_entry1 = TickEntry(tick, self.price_level)
        self.tick_entry2 = TickEntry(tick, self.price_level)
        self.tick_entry3 = TickEntry(tick, self.price_level)
        self.tick_entry4 = TickEntry(tick, self.price_level)
        self.tick_entry5 = TickEntry(tick2, self.price_level)

    def test_appending_length(self):
        # Test for tick appending and length
        self.assertEquals(0, self.price_level.length)
        self.assertEquals(0, len(self.price_level))

        self.price_level.append_tick(self.tick_entry1)
        self.price_level.append_tick(self.tick_entry2)
        self.price_level.append_tick(self.tick_entry3)
        self.price_level.append_tick(self.tick_entry4)

        self.assertEquals(4, self.price_level.length)
        self.assertEquals(4, len(self.price_level))
        self.assertRaises(AssertionError, self.price_level.append_tick, self.tick_entry5)

    def test_tick_removal(self):
        # Test for tick removal
        self.price_level.append_tick(self.tick_entry1)
        self.price_level.append_tick(self.tick_entry2)
        self.price_level.append_tick(self.tick_entry3)
        self.price_level.append_tick(self.tick_entry4)

        self.price_level.remove_tick(self.tick_entry2)
        self.price_level.remove_tick(self.tick_entry1)
        self.price_level.remove_tick(self.tick_entry4)
        self.price_level.remove_tick(self.tick_entry3)
        self.assertEquals(0, self.price_level.length)

    def test_str(self):
        # Test for price level string representation
        self.price_level.append_tick(self.tick_entry1)
        self.price_level.append_tick(self.tick_entry2)
        self.assertEquals('30.000000 MC\t@\t63400.000000 BTC\n'
                          '30.000000 MC\t@\t63400.000000 BTC\n', str(self.price_level))
