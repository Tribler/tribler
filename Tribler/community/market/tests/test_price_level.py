import unittest

from Tribler.community.market.core.price_level import PriceLevel
from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price, Quantity, Timeout, Timestamp, \
    Tick
from Tribler.community.market.core.tickentry import TickEntry


class PriceLevelTestSuite(unittest.TestCase):
    """PriceLevel test cases."""

    def test_price_level(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timeout = Timeout(float("inf"))
        timestamp = Timestamp(float("inf"))
        tick = Tick(message_id, price, quantity, timeout, timestamp, True)

        price_level = PriceLevel()
        tick_entry1 = TickEntry(tick, price_level)
        tick_entry2 = TickEntry(tick, price_level)
        tick_entry3 = TickEntry(tick, price_level)
        tick_entry4 = TickEntry(tick, price_level)

        # Test for tick appending
        price_level.append_tick(tick_entry1)
        price_level.append_tick(tick_entry2)
        price_level.append_tick(tick_entry3)
        price_level.append_tick(tick_entry4)
        self.assertEquals(4, price_level.length)

        # Test for properties and len()
        self.assertEquals(tick_entry1, price_level.first_tick)
        self.assertEquals(4, price_level.length)
        self.assertEquals(4, len(price_level))
        self.assertEquals(Quantity(120), price_level.depth)

        # Test for tick removal
        price_level.remove_tick(tick_entry2)
        price_level.remove_tick(tick_entry1)
        price_level.remove_tick(tick_entry4)
        price_level.remove_tick(tick_entry3)
        self.assertEquals(0, price_level.length)

        # Test for price level string representation
        price_level.append_tick(tick_entry1)
        price_level.append_tick(tick_entry2)
        self.assertEquals('0.0030\t@\t6.3400\n'
                          '0.0030\t@\t6.3400\n', str(price_level))


if __name__ == '__main__':
    unittest.main()
