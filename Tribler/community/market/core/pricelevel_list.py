from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel


class PriceLevelList(object):
    """
    Sorted doubly linked dictionary implementation.
    """

    def __init__(self):
        super(PriceLevelList, self).__init__()
        self._price_list = []
        self._price_level_dictionary = {}

    def insert(self, price, price_level):
        """
        :type price: Price
        :type price_level: PriceLevel
        """
        assert isinstance(price, Price), type(price)
        assert isinstance(price_level, PriceLevel), type(price_level)

        self._price_list.append(price)
        self._price_list.sort()
        self._price_level_dictionary[price] = price_level

    def remove(self, price):
        """
        :type price: Price
        """
        assert isinstance(price, Price), type(price)

        self._price_list.remove(price)
        del self._price_level_dictionary[price]

    def succ_item(self, price):
        """
        Returns (price, price_level) pair where price is successor to given price

        :type price: Price
        :rtype: (Price, PriceLevel)
        """
        assert isinstance(price, Price), type(price)

        index = self._price_list.index(price) + 1
        if index >= len(self._price_list):
            raise IndexError
        succ_price = self._price_list[index]
        return succ_price, self._price_level_dictionary[succ_price]

    def prev_item(self, price):
        """
        Returns (price, price_level) pair where price is predecessor to given price

        :type price: Price
        :rtype: (Price, PriceLevel)
        """
        assert isinstance(price, Price), type(price)

        index = self._price_list.index(price) - 1
        if index < 0:
            raise IndexError
        prev_price = self._price_list[index]
        return prev_price, self._price_level_dictionary[prev_price]

    def min_key(self):
        """
        Return the lowest price in the price level list

        :rtype: Price
        """
        return self._price_list[0]

    def max_key(self):
        """
        Return the highest price in the price level list

        :rtype: Price
        """
        return self._price_list[-1]

    def items(self, reverse=False):
        """
        Returns a sorted list of price, price_level tuples

        :param reverse: When true returns the reversed sorted list of price, price_level tuples
        :type reverse: bool
        :rtype: List[(Price, PriceLevel)]
        """
        items = []
        for price in self._price_list:
            if reverse:
                items.insert(0, (price, self._price_level_dictionary[price]))
            else:
                items.append((price, self._price_level_dictionary[price]))
        return items

    def get_ticks_list(self):
        """
        Returns a list describing all ticks.
        :return: list
        """
        ticks_list = []
        for _, price_level in self.items():
            for tick in price_level:
                ticks_list.append(tick.tick.to_dictionary())

        return ticks_list
