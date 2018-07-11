import unittest

from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.pricelevel_list import PriceLevelList


class PriceLevelListTestSuite(unittest.TestCase):
    """PriceLevelList test cases."""

    def setUp(self):
        # Object creation
        self.price_level_list = PriceLevelList()
        self.price_level_list2 = PriceLevelList()
        self.price = Price(1, 'BTC', 'MB')
        self.price2 = Price(2, 'BTC', 'MB')
        self.price3 = Price(3, 'BTC', 'MB')
        self.price4 = Price(4, 'BTC', 'MB')
        self.price_level = PriceLevel(self.price)
        self.price_level2 = PriceLevel(self.price2)
        self.price_level3 = PriceLevel(self.price3)
        self.price_level4 = PriceLevel(self.price4)

        # Fill price level list
        self.price_level_list.insert(self.price_level)
        self.price_level_list.insert(self.price_level2)
        self.price_level_list.insert(self.price_level3)
        self.price_level_list.insert(self.price_level4)

    def test_min_key(self):
        # Test for min key
        self.assertEquals(self.price, self.price_level_list.min_key())

    def test_min_key_empty(self):
        # Test for min key when empty
        with self.assertRaises(IndexError):
            self.price_level_list2.min_key()

    def test_max_key(self):
        # Test for max key
        self.assertEquals(self.price4, self.price_level_list.max_key())

    def test_max_key_empty(self):
        # Test for max key when empty
        with self.assertRaises(IndexError):
            self.price_level_list2.max_key()

    def test_succ_item(self):
        # Test for succ item
        self.assertEquals(self.price_level2, self.price_level_list.succ_item(self.price))
        self.assertEquals(self.price_level4, self.price_level_list.succ_item(self.price3))

    def test_succ_item_tail(self):
        # Test for succ item when at tail
        with self.assertRaises(IndexError):
            self.price_level_list.succ_item(self.price4)

    def test_prev_item(self):
        # Test for prev item
        self.assertEquals(self.price_level3, self.price_level_list.prev_item(self.price4))
        self.assertEquals(self.price_level2, self.price_level_list.prev_item(self.price3))

    def test_prev_item_head(self):
        # Test for prev item when at head
        with self.assertRaises(IndexError):
            self.price_level_list.prev_item(self.price)

    def test_remove(self):
        # Test for remove
        self.price_level_list.remove(self.price4)
        self.assertEquals(self.price3, self.price_level_list.max_key())

    def test_remove_empty(self):
        # Test for remove when element not exists
        self.price_level_list.remove(self.price4)
        with self.assertRaises(ValueError):
            self.price_level_list.remove(self.price4)

    def test_items(self):
        # Test for items
        self.assertEquals(
            [self.price_level, self.price_level2, self.price_level3, self.price_level4], self.price_level_list.items())
        self.price_level_list.remove(self.price2)
        self.assertEquals(
            [self.price_level, self.price_level3, self.price_level4], self.price_level_list.items())

    def test_items_empty(self):
        # Test for items when empty
        self.assertEquals([], self.price_level_list2.items())

    def test_items_reverse(self):
        # Test for items with reverse attribute
        self.assertEquals(
            [self.price_level4, self.price_level3, self.price_level2, self.price_level],
            self.price_level_list.items(reverse=True))
        self.price_level_list.remove(self.price2)
        self.assertEquals(
            [self.price_level4, self.price_level3, self.price_level], self.price_level_list.items(reverse=True))

    def test_items_reverse_empty(self):
        # Test for items when empty with reverse attribute
        self.assertEquals([], self.price_level_list2.items(reverse=True))
