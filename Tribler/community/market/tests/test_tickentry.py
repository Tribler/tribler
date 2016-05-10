import unittest

from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price, Quantity, Timeout, Timestamp, \
    Tick
from Tribler.community.market.core.tickentry import TickEntry


class OrderTestSuite(unittest.TestCase):
    """TickEntry test cases."""

    def test_tick_entry(self):
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
        tick_entry = TickEntry(tick, price_level)
        tick_entry2 = TickEntry(tick, price_level)

        # Test properties and price level
        self.assertEquals(message_id, tick_entry.message_id)
        self.assertEquals(price, tick_entry.price)
        self.assertEquals(quantity, tick_entry.quantity)
        self.assertEquals(price_level, tick_entry.price_level())

        # Test for next tick and previous tick
        self.assertEquals(None, tick_entry.next_tick())
        self.assertEquals(None, tick_entry.prev_tick())
        price_level.append_tick(tick_entry)
        price_level.append_tick(tick_entry2)
        self.assertEquals(tick_entry2, tick_entry.next_tick())
        self.assertEquals(tick_entry, tick_entry2.prev_tick())

        # Test for tick string representation
        self.assertEquals('0.0030\t@\t6.3400', str(tick_entry))


if __name__ == '__main__':
    unittest.main()
