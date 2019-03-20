from __future__ import absolute_import

from typing import Any, Dict, List  # pylint: disable=unused-import

from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel


class PriceLevelList(object):
    """
    Sorted doubly linked dictionary implementation.
    """

    def __init__(self):
        super(PriceLevelList, self).__init__()
        self._price_list = []  # type: List[float]
        self._price_level_dictionary = {}  # type: Dict[float, PriceLevel]

    def insert(self, price_level):  # type: (PriceLevel) -> None
        """
        :type price_level: PriceLevel
        """
        self._price_list.append(price_level.price)
        self._price_list.sort()
        self._price_level_dictionary[price_level.price] = price_level

    def remove(self, price):  # type: (Price) -> None
        """
        :type price: Price
        """
        self._price_list.remove(price)
        del self._price_level_dictionary[price]

    def succ_item(self, price):  # type: (Price) -> PriceLevel
        """
        Returns the price level where price_level.price is successor to given price

        :type price: Price
        :rtype: PriceLevel
        """
        index = self._price_list.index(price) + 1
        if index >= len(self._price_list):
            raise IndexError
        succ_price = self._price_list[index]
        return self._price_level_dictionary[succ_price]

    def prev_item(self, price):  # type: (Price) -> PriceLevel
        """
        Returns the price level where price_level.price is predecessor to given price

        :type price: Price
        :rtype: PriceLevel
        """
        index = self._price_list.index(price) - 1
        if index < 0:
            raise IndexError
        prev_price = self._price_list[index]
        return self._price_level_dictionary[prev_price]

    def min_key(self):  # type: () -> Price
        """
        Return the lowest price in the price level list

        :rtype: Price
        """
        return self._price_list[0]

    def max_key(self):  # type: () -> Price
        """
        Return the highest price in the price level list

        :rtype: Price
        """
        return self._price_list[-1]

    def items(self, reverse=False):  # type: (bool) -> List[(Price, PriceLevel)]
        """
        Returns a sorted list (on price) of price_levels

        :param reverse: When true returns the reversed sorted list of price, price_level tuples
        :type reverse: bool
        :rtype: List[(Price, PriceLevel)]
        """
        items = []
        for price in self._price_list:
            if reverse:
                items.insert(0, self._price_level_dictionary[price])
            else:
                items.append(self._price_level_dictionary[price])
        return items

    def get_ticks_list(self):  # type: () -> List[Any]
        """
        Returns a list describing all ticks.
        :return: list
        """
        ticks_list = []
        for price_level in self.items():
            for tick in price_level:
                ticks_list.append(tick.tick.to_dictionary())

        return ticks_list
