import unittest

from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.incremental_manager import IncrementalPriceManager, IncrementalQuantityManager


class IncrementalPriceManagerTestSuite(unittest.TestCase):
    """Incremental price manager test cases."""

    def setUp(self):
        # Object creation
        self.incremental_price_manager = IncrementalPriceManager()
        self.price = Price(30)
        self.price2 = Price(21)
        self.price3 = Price(1)
        self.price4 = Price(0)

    def test_determine_incremental_price_list_empty(self):
        # Test for determine incremental price list when price is empty
        self.assertEquals([], self.incremental_price_manager.determine_incremental_price_list(self.price4))

    def test_determine_incremental_price_list_initial(self):
        # Test for determine incremental price list is equal to initial price
        self.assertEquals([Price(1)], self.incremental_price_manager.determine_incremental_price_list(self.price3))

    def test_determine_incremental_price_list_exact(self):
        # Test for determine incremental price list when price is equal to initial price + multiple incremental prices
        self.assertEquals([Price(1), Price(10), Price(10)],
                          self.incremental_price_manager.determine_incremental_price_list(self.price2))

    def test_determine_incremental_price_list(self):
        # Test for determine incremental price list
        self.assertEquals([Price(1), Price(10), Price(10), Price(9)],
                          self.incremental_price_manager.determine_incremental_price_list(self.price))


class IncrementalQuantityManagerTestSuite(unittest.TestCase):
    """Incremental quantity manager test cases."""

    def setUp(self):
        # Object creation
        self.incremental_quantity_manager = IncrementalQuantityManager()
        self.incremental_price_manager = IncrementalPriceManager()
        self.price = Price(21)
        self.quantity = Quantity(21)
        self.price2 = Price(30)
        self.quantity2 = Quantity(30)
        self.price3 = Price(1)
        self.quantity3 = Quantity(20)
        self.price4 = Price(0)
        self.quantity4 = Quantity(0)

    def test_determine_incremental_quantity_list_empty(self):
        # Test for determine incremental quantity list when price is empty
        incremental_price_list = self.incremental_price_manager.determine_incremental_price_list(self.price4)
        self.assertEquals([], self.incremental_quantity_manager.determine_incremental_quantity_list(self.quantity4,
                                                                                                    self.price4,
                                                                                                    incremental_price_list))

    def test_determine_incremental_quantity_list_initial(self):
        # Test for determine incremental quantity list when price is equal to initial price
        incremental_price_list = self.incremental_price_manager.determine_incremental_price_list(self.price3)
        self.assertEquals([Quantity(20)],
                          self.incremental_quantity_manager.determine_incremental_quantity_list(self.quantity3,
                                                                                                self.price3,
                                                                                                incremental_price_list))

    def test_determine_incremental_quantity_list_exact(self):
        # Test for determine incremental quantity list when price is equal to initial price + multiple incremental prices
        incremental_price_list = self.incremental_price_manager.determine_incremental_price_list(self.price)
        self.assertEquals([Quantity(1), Quantity(10), Quantity(10)],
                          self.incremental_quantity_manager.determine_incremental_quantity_list(self.quantity,
                                                                                                self.price,
                                                                                                incremental_price_list))

    def test_determine_incremental_quantity_list_rounding_error(self):
        # Test for determine incremental quantity list when a rounding error occurs
        incremental_price_list = self.incremental_price_manager.determine_incremental_price_list(self.price2)
        self.assertEquals([Quantity(0), Quantity(7), Quantity(7), Quantity(7)],
                          self.incremental_quantity_manager.determine_incremental_quantity_list(self.quantity,
                                                                                                self.price2,
                                                                                                incremental_price_list))

    def test_determine_incremental_quantity_list(self):
        # Test for determine incremental quantity list
        incremental_price_list = self.incremental_price_manager.determine_incremental_price_list(self.price2)
        self.assertEquals([Quantity(1), Quantity(10), Quantity(10), Quantity(9)],
                          self.incremental_quantity_manager.determine_incremental_quantity_list(self.quantity2,
                                                                                                self.price2,
                                                                                                incremental_price_list))


if __name__ == '__main__':
    unittest.main()
