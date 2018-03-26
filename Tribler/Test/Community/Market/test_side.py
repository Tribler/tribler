import unittest

from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.side import Side
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class SideTestSuite(unittest.TestCase):
    """Side test cases."""

    def setUp(self):
        # Object creation

        self.tick = Tick(OrderId(TraderId('0'), OrderNumber(1)), Price(400, 'BTC'), Quantity(30, 'MC'),
                         Timeout(float("inf")), Timestamp(float("inf")), True)
        self.tick2 = Tick(OrderId(TraderId('1'), OrderNumber(2)), Price(800, 'BTC'), Quantity(30, 'MC'),
                          Timeout(float("inf")), Timestamp(float("inf")), True)
        self.side = Side()

    def test_max_price(self):
        # Test max price (list)
        self.assertEquals(None, self.side.get_max_price('BTC', 'MC'))
        self.assertEquals(None, self.side.get_max_price_list('BTC', 'MC'))

        self.side.insert_tick(self.tick)
        self.side.insert_tick(self.tick2)

        self.assertEquals(Price(800, 'BTC'), self.side.get_max_price('BTC', 'MC'))

    def test_min_price(self):
        # Test min price (list)
        self.assertEquals(None, self.side.get_min_price_list('BTC', 'MC'))
        self.assertEquals(None, self.side.get_min_price('BTC', 'MC'))

        self.side.insert_tick(self.tick)
        self.side.insert_tick(self.tick2)

        self.assertEquals(Price(400, 'BTC'), self.side.get_min_price('BTC', 'MC'))

    def test_insert_tick(self):
        # Test insert tick
        self.assertEquals(0, len(self.side))
        self.assertFalse(self.side.tick_exists(OrderId(TraderId('0'), OrderNumber(1))))

        self.side.insert_tick(self.tick)
        self.side.insert_tick(self.tick2)

        self.assertEquals(2, len(self.side))
        self.assertTrue(self.side.tick_exists(OrderId(TraderId('0'), OrderNumber(1))))

    def test_remove_tick(self):
        # Test remove tick
        self.side.insert_tick(self.tick)
        self.side.insert_tick(self.tick2)

        self.side.remove_tick(OrderId(TraderId('0'), OrderNumber(1)))
        self.assertEquals(1, len(self.side))
        self.side.remove_tick(OrderId(TraderId('1'), OrderNumber(2)))
        self.assertEquals(0, len(self.side))

    def test_get_price_level_list_wallets(self):
        """
        Test the price level lists of wallets of a side
        """
        self.assertFalse(self.side.get_price_level_list_wallets())
        self.side.insert_tick(self.tick)
        self.assertTrue(self.side.get_price_level_list_wallets())

    def test_get_list_representation(self):
        """
        Testing the list representation of a side
        """
        self.assertFalse(self.side.get_list_representation())
        self.side.insert_tick(self.tick)

        list_rep = self.side.get_list_representation()
        self.assertTrue(list_rep)
