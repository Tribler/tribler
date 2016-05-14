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

    def test_tick_entry(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timeout = Timeout(float("inf"))
        timestamp = Timestamp(float("inf"))
        order_id = OrderId(trader_id, OrderNumber("order_number"))
        tick = Tick(message_id, order_id, price, quantity, timeout, timestamp, True)

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

        # Test for quantity setter
        price_level.append_tick(tick_entry)
        price_level.append_tick(tick_entry2)
        tick_entry.quantity = Quantity(15)
        self.assertEquals(Quantity(15), tick_entry.quantity)


if __name__ == '__main__':
    unittest.main()
