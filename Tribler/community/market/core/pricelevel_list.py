from price import Price
from pricelevel import PriceLevel


class PriceLevelList(object):
    def __init__(self):
        super(PriceLevelList, self).__init__()
        self._price_list = []
        self._price_level_dictionary = {}

    def insert(self, price, pricelevel):
        assert isinstance(price, Price), type(price)
        assert isinstance(pricelevel, PriceLevel), type(pricelevel)

        self._price_list.append(price)
        self._price_list.sort()
        self._price_level_dictionary[price] = pricelevel

    def remove(self, price):
        assert isinstance(price, Price), type(price)

        self._price_list.remove(price)
        del self._price_level_dictionary[price]

    def succ_item(self, price):
        assert isinstance(price, Price), type(price)

        index = self._price_list.index(price) + 1
        if index > len(self._price_list):
            raise IndexError
        succ_price = self._price_list[index]
        return succ_price, self._price_level_dictionary[succ_price]

    def prev_item(self, price):
        assert isinstance(price, Price), type(price)

        index = self._price_list.index(price) - 1
        if index < 0:
            raise IndexError
        prev_price = self._price_list[index]
        return prev_price, self._price_level_dictionary[prev_price]

    def min_key(self):
        return self._price_list[0]

    def max_key(self):
        return self._price_list[-1]

    def items(self, reverse=False):
        items = []
        for price in self._price_list:
            if reverse:
                items.insert(0, (price, self._price_level_dictionary[price]))
            else:
                items.append((price, self._price_level_dictionary[price]))
        return items
