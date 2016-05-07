from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price, Quantity, Timeout, Timestamp, \
    Message, Tick
from Tribler.community.market.core.order import Order
from Tribler.community.market.core.price_level import PriceLevel
import unittest


class OrderTestSuite(unittest.TestCase):
    """Order test cases."""

    def test_order(self):
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
        order = Order(tick, price_level)
        order2 = Order(tick, price_level)

        # Test properties and price level
        self.assertEquals(message_id, order.message_id)
        self.assertEquals(price, order.price)
        self.assertEquals(quantity, order.quantity)
        self.assertEquals(price_level, order.price_level())

        # Test for next order and previous order
        self.assertEquals(None, order.next_order())
        self.assertEquals(None, order.prev_order())
        price_level.append_order(order)
        price_level.append_order(order2)
        self.assertEquals(order2, order.next_order())
        self.assertEquals(order, order2.prev_order())

        # Test for order string representation
        self.assertEquals('0.0030\t@\t6.3400', str(order))


if __name__ == '__main__':
    unittest.main()
