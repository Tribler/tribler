from Tribler.community.market.core.order import OrderId
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.pricelevel_list import PriceLevelList
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.tickentry import TickEntry


class Side(object):
    """Class for representing a side of the order book"""

    def __init__(self):
        self._price_level_list_map = {}  # Dict of (price_type, asset_type) -> PriceLevelList
        self._price_map = {}  # Map: Price -> PriceLevel
        self._tick_map = {}  # Map: MessageId -> TickEntry
        self._depth = {}  # Dict of (price_type, asset_type) -> Int

    def __len__(self):
        """
        Return the length of the amount of ticks contained in all the price level of this side
        """
        return len(self._tick_map)

    def get_price_level(self, price):
        """
        Return the price level corresponding to the given price

        :param price: The price for which the price level needs to be returned
        :type price: Price
        :return: The price level
        :rtype: PriceLevel
        """
        return self._price_map[price]

    def get_tick(self, order_id):
        """
        :param order_id: The order id of the tick
        :type order_id: OrderId
        :return: The tick
        :rtype: TickEntry
        """
        return self._tick_map.get(order_id, None)

    def _create_price_level(self, price):
        """
        :param price: The price to create the level for
        :type price: Price
        """
        self._depth[(price.numerator, price.denominator)] += 1
        price_level = PriceLevel(price)
        self._price_level_list_map[(price.numerator, price.denominator)].insert(price_level)
        self._price_map[price] = price_level

    def _remove_price_level(self, price):
        """
        :param price: The price to remove the level for
        :type price: Price
        """
        self._depth[(price.numerator, price.denominator)] -= 1

        self._price_level_list_map[(price.numerator, price.denominator)].remove(price)
        del self._price_map[price]

    def _price_level_exists(self, price):
        """
        :param price: The price to check for
        :type price: Price
        :return: True if the price level exists, False otherwise
        :rtype: bool
        """
        return price in self._price_map

    def tick_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the tick exists, False otherwise
        :rtype: bool
        """
        return order_id in self._tick_map

    def insert_tick(self, tick):
        """
        :param tick: The tick to insert
        :type tick: Tick
        """
        if (tick.assets.second.asset_id, tick.assets.first.asset_id) not in self._price_level_list_map:
            self._price_level_list_map[(tick.assets.second.asset_id, tick.assets.first.asset_id)] = PriceLevelList()
            self._depth[(tick.assets.second.asset_id, tick.assets.first.asset_id)] = 0

        if not self._price_level_exists(tick.price):  # First tick for that price
            self._create_price_level(tick.price)
        tick_entry = TickEntry(tick, self._price_map[tick.price])
        self.get_price_level(tick.price).append_tick(tick_entry)
        self._tick_map[tick.order_id] = tick_entry

    def remove_tick(self, order_id):
        """
        :param order_id: The order id of the tick that needs to be removed
        :type order_id: OrderId
        """
        tick = self.get_tick(order_id)
        if tick:
            tick.shutdown_task_manager()
            tick.price_level().remove_tick(tick)
            if len(tick.price_level()) == 0:  # Last tick for that price
                self._remove_price_level(tick.price)
            del self._tick_map[order_id]

    def get_price_level_list(self, price_wallet_id, quantity_wallet_id):
        """
        :return: PriceLevelList
        """
        return self._price_level_list_map[(price_wallet_id, quantity_wallet_id)]

    def get_price_level_list_wallets(self):
        """
        Returns the combinations (price wallet id, quantity wallet id) available in the side.
        """
        return list(self._price_level_list_map)

    def get_max_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the maximum price that a tick is listed for on this side of the order book
        :rtype: float
        """
        key = price_wallet_id, quantity_wallet_id

        if self._depth.get(key, 0) > 0:
            return self.get_price_level_list(price_wallet_id, quantity_wallet_id).max_key()
        else:
            return None

    def get_min_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the minimum price that a tick is listed for on this side of the order book
        :rtype: Price
        """
        key = price_wallet_id, quantity_wallet_id

        if self._depth(key, 0) > 0:
            return self.get_price_level_list(price_wallet_id, quantity_wallet_id).min_key()
        else:
            return None

    def get_max_price_list(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price level for the maximum price
        :rtype: PriceLevel
        """
        key = price_wallet_id, quantity_wallet_id

        if self._depth(key, 0) > 0:
            return self.get_price_level(self.get_max_price(price_wallet_id, quantity_wallet_id))
        else:
            return None

    def get_min_price_list(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price level for the minimum price
        :rtype: PriceLevel
        """
        key = price_wallet_id, quantity_wallet_id

        if self._depth(key, 0) > 0:
            return self.get_price_level(self.get_min_price(price_wallet_id, quantity_wallet_id))
        else:
            return None

    def get_list_representation(self):
        """
        Return a list describing all ticks in this side.
        :rtype: list
        """
        rlist = []
        for asset1, asset2 in self._price_level_list_map.keys():
            rlist.append({'asset1': asset2, 'asset2': asset1,
                          'ticks': self._price_level_list_map[(asset1, asset2)].get_ticks_list()})

        return rlist
