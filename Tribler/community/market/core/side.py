from Tribler.community.market.core.order import OrderId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.pricelevel_list import PriceLevelList
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.tickentry import TickEntry


class Side(object):
    """Class for representing a side of the order book"""

    def __init__(self):
        self._price_level_list_map = {}  # Dict of (price_type, quantity_type) -> PriceLevelList
        self._price_map = {}  # Map: Price -> PriceLevel
        self._tick_map = {}  # Map: MessageId -> TickEntry
        self._depth = {}  # Dict of (price_type, quantity_type) -> Int

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
        assert isinstance(price, Price), type(price)
        return self._price_map[price]

    def get_tick(self, order_id):
        """
        :param order_id: The order id of the tick
        :type order_id: OrderId
        :return: The tick
        :rtype: TickEntry
        """
        assert isinstance(order_id, OrderId), type(order_id)
        return self._tick_map[order_id] if order_id in self._tick_map else None

    def _create_price_level(self, price, quantity_wallet_id):
        """
        :param price: The price to create the level for
        :param quantity_wallet_id: the id of the quantities stored in this price level
        :type price: Price
        :type quantity_wallet_id: str
        """
        assert isinstance(price, Price), type(price)

        self._depth[(price.wallet_id, quantity_wallet_id)] += 1

        price_level = PriceLevel(quantity_wallet_id)
        self._price_level_list_map[(price.wallet_id, quantity_wallet_id)].insert(price, price_level)
        self._price_map[price] = price_level

    def _remove_price_level(self, price, quantity_wallet_id):
        """
        :param price: The price to remove the level for
        :param quantity_wallet_id: the id of the quantities stored in this price level
        :type price: Price
        :type quantity_wallet_id: str
        """
        assert isinstance(price, Price), type(price)

        self._depth[(price.wallet_id, quantity_wallet_id)] -= 1

        self._price_level_list_map[(price.wallet_id, quantity_wallet_id)].remove(price)
        del self._price_map[price]

    def _price_level_exists(self, price):
        """
        :param price: The price to check for
        :type price: Price
        :return: True if the price level exists, False otherwise
        :rtype: bool
        """
        assert isinstance(price, Price), type(price)
        return price in self._price_map

    def tick_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the tick exists, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)
        return order_id in self._tick_map

    def insert_tick(self, tick):
        """
        :param tick: The tick to insert
        :type tick: Tick
        """
        assert isinstance(tick, Tick), type(tick)

        if (tick.price.wallet_id, tick.quantity.wallet_id) not in self._price_level_list_map:
            self._price_level_list_map[(tick.price.wallet_id, tick.quantity.wallet_id)] = PriceLevelList()
            self._depth[(tick.price.wallet_id, tick.quantity.wallet_id)] = 0

        if not self._price_level_exists(tick.price):  # First tick for that price
            self._create_price_level(tick.price, tick.quantity.wallet_id)
        tick_entry = TickEntry(tick, self._price_map[tick.price])
        self.get_price_level(tick.price).append_tick(tick_entry)
        self._tick_map[tick.order_id] = tick_entry

    def remove_tick(self, order_id):
        """
        :param order_id: The order id of the tick that needs to be removed
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

        tick = self.get_tick(order_id)
        if tick:
            tick.cancel_all_pending_tasks()
            tick.price_level().remove_tick(tick)
            if len(tick.price_level()) == 0:  # Last tick for that price
                self._remove_price_level(tick.price, tick.quantity.wallet_id)
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
        return self._price_level_list_map.keys()

    def get_max_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the maximum price that a tick is listed for on this side of the order book
        :rtype: Price
        """
        key = price_wallet_id, quantity_wallet_id

        if key in self._depth and self._depth[key] > 0:
            return self.get_price_level_list(price_wallet_id, quantity_wallet_id).max_key()
        else:
            return None

    def get_min_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the minimum price that a tick is listed for on this side of the order book
        :rtype: Price
        """
        key = price_wallet_id, quantity_wallet_id

        if key in self._depth and self._depth[key] > 0:
            return self.get_price_level_list(price_wallet_id, quantity_wallet_id).min_key()
        else:
            return None

    def get_max_price_list(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price level for the maximum price
        :rtype: PriceLevel
        """
        key = price_wallet_id, quantity_wallet_id

        if key in self._depth and self._depth[key] > 0:
            return self.get_price_level(self.get_max_price(price_wallet_id, quantity_wallet_id))
        else:
            return None

    def get_min_price_list(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price level for the minimum price
        :rtype: PriceLevel
        """
        key = price_wallet_id, quantity_wallet_id

        if key in self._depth and self._depth[key] > 0:
            return self.get_price_level(self.get_min_price(price_wallet_id, quantity_wallet_id))
        else:
            return None

    def get_list_representation(self):
        """
        Return a list describing all ticks in this side.
        :rtype: list
        """
        rlist = []
        for price_type, quantity_type in self._price_level_list_map.keys():
            rlist.append({'price_type': price_type, 'quantity_type': quantity_type,
                          'ticks': self._price_level_list_map[(price_type, quantity_type)].get_ticks_list()})

        return rlist
