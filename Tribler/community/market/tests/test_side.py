from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price, Quantity, Timeout, Timestamp, \
    Message, Tick
from Tribler.community.market.core.side import Side
import unittest


class SideTestSuite(unittest.TestCase):
    """Side test cases."""

    def test_side(self):
        # Object creation
        trader_id = TraderId('trader_id')
        trader_id2 = TraderId('trader_id2')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        message_id2 = MessageId(trader_id2, message_number)
        price = Price(400)
        price2 = Price(800)
        quantity = Quantity(30)
        timeout = Timeout(float("inf"))
        timestamp = Timestamp(float("inf"))

        tick = Tick(message_id, price, quantity, timeout, timestamp, True)
        tick2 = Tick(message_id2, price2, quantity, timeout, timestamp, True)
        side = Side()

        # Test max price (list) and min price (list)
        self.assertEquals(None, side.max_price)
        self.assertEquals(None, side.min_price)
        self.assertEquals(None, side.max_price_list)
        self.assertEquals(None, side.min_price_list)

        # Test insert tick
        self.assertEquals(0, len(side))
        self.assertFalse(side.tick_exists(message_id))
        side.insert_tick(tick)
        side.insert_tick(tick2)
        self.assertEquals(2, len(side))
        self.assertTrue(side.tick_exists(message_id))

        # Test max price (list) and min price (list)
        self.assertEquals(price2, side.max_price)
        self.assertEquals(price, side.min_price)
        self.assertEquals('0.0030\t@\t0.0800\n', str(side.max_price_list))
        self.assertEquals('0.0030\t@\t0.0400\n', str(side.min_price_list))

        # Test remove tick
        side.remove_tick(message_id)
        self.assertEquals(1, len(side))
        side.remove_tick(message_id2)
        self.assertEquals(0, len(side))

if __name__ == '__main__':
    unittest.main()
