from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price, Quantity, Timeout, Timestamp, \
    Message, Tick
from Tribler.community.market.core.order import Order
from Tribler.community.market.core.price_level import PriceLevel
import unittest


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
        order1 = Order(tick, price_level)
        order2 = Order(tick, price_level)
        order3 = Order(tick, price_level)
        order4 = Order(tick, price_level)

        # Test for order appending
        price_level.append_order(order1)
        price_level.append_order(order2)
        price_level.append_order(order3)
        price_level.append_order(order4)
        self.assertEquals(4, price_level.length)

        # Test for properties and len()
        self.assertEquals(order1, price_level.first_order)
        self.assertEquals(4, price_level.length)
        self.assertEquals(4, len(price_level))
        self.assertEquals(Quantity(120), price_level.depth)

        # Test for order removal
        price_level.remove_order(order2)
        price_level.remove_order(order1)
        price_level.remove_order(order4)
        price_level.remove_order(order3)
        self.assertEquals(0, price_level.length)

        # Test for price level string representation
        price_level.append_order(order1)
        price_level.append_order(order2)
        self.assertEquals('0.0030\t@\t6.3400\n'
                          '0.0030\t@\t6.3400\n', str(price_level))

if __name__ == '__main__':
    unittest.main()
