from price import Price
from quantity import Quantity


class IncrementalQuantityManager(object):
    """Incremental Quantity Manager which determines an incremental quantity list for payments"""

    def __init__(self):
        super(IncrementalQuantityManager, self).__init__()

    def determine_incremental_quantity_list(self, total_quantity, total_price, incremental_prices):
        """
        Determines an incremental quantity list parallel to the incremental price list

        :param incremental_prices: Incremental price list from IncrementalPriceManager
        :type total_quantity: Quantity
        :type total_price: Price
        :type incremental_prices: List[Price]
        :return: Incremental quantity list
        :rtype: List[Quantity]
        """
        incremental_quantities = []
        remaining_quantity = int(total_quantity)

        for incremental_price in incremental_prices:
            incremental_quantity = (int(total_quantity) * int(incremental_price)) / int(total_price)
            incremental_quantities.append(Quantity(incremental_quantity))
            remaining_quantity -= incremental_quantity

        if len(incremental_quantities) > 1 and remaining_quantity > 0:
            incremental_quantities[-1] = Quantity(remaining_quantity + int(incremental_quantities[-1]))

        return incremental_quantities


class IncrementalPriceManager(object):
    """Incremental Price Manager which determines an incremental price list for payments"""

    INITIAL_PRICE = 1
    INCREMENTAL_PRICE = 10

    def __init__(self):
        super(IncrementalPriceManager, self).__init__()

    def determine_incremental_price_list(self, total_price):
        """
        Determines an incremental price list

        :type total_price: Price
        :return: Incremental price list
        :rtype: List[Price]
        """
        incremental_prices = []
        remaining_price = int(total_price)
        if remaining_price > 0:
            initial_price = min(self.INITIAL_PRICE, remaining_price)
            incremental_prices.append(Price(initial_price))
            remaining_price -= initial_price

            while remaining_price > 0:
                incremental_price = min(self.INCREMENTAL_PRICE, remaining_price)
                incremental_prices.append(Price(incremental_price))
                remaining_price -= incremental_price
        return incremental_prices
