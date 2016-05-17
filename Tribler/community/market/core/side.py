from bintrees import FastRBTree

from Tribler.community.market.core.order import OrderId
from price import Price
from pricelevel import PriceLevel
from quantity import Quantity
from tick import Tick
from tickentry import TickEntry


class Side(object):
    """Class for representing a side of the order book"""

    def __init__(self):
        """
        Initialise the side
        """
        self._price_tree = FastRBTree()  # Red Black tree containing price levels: Price -> PriceLevel
        self._price_map = {}  # Map: Price -> PriceLevel
        self._tick_map = {}  # Map: MessageId -> TickEntry
        self._volume = Quantity(0)  # Total number of quantity contained in all the price levels
        self._depth = 0  # Total amount of price levels

    def __len__(self):
        """
        Return the length of the amount of ticks contained in all the price level of this side

        :return: The length
        :rtype: integer
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
        Retrieve a tick by order id

        :param order_id: The order id of the tick
        :type order_id: OrderId
        :return: The tick
        :rtype: TickEntry
        """
        assert isinstance(order_id, OrderId), type(order_id)
        return self._tick_map[order_id]

    def _create_price_level(self, price):
        """
        Create a price level

        :param price: The price to create the level for
        :type price: Price
        """
        assert isinstance(price, Price), type(price)

        self._depth += 1

        price_level = PriceLevel()
        self._price_tree.insert(price, price_level)
        self._price_map[price] = price_level

    def _remove_price_level(self, price):
        """
        Remove a price level by price

        :param price: The price to remove the level for
        :type price: Price
        """
        assert isinstance(price, Price), type(price)

        self._depth -= 1

        self._price_tree.remove(price)
        del self._price_map[price]

    def _price_level_exists(self, price):
        """
        Check if the price level exists

        :param price: The price to check for
        :type price: Price
        :return: True if the price level exists, False otherwise
        :rtype: bool
        """
        assert isinstance(price, Price), type(price)
        return price in self._price_map

    def tick_exists(self, order_id):
        """
        Check if a tick exists with the given order id

        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the tick exists, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)
        return order_id in self._tick_map

    def insert_tick(self, tick):
        """
        Insert a tick into this side of the order book

        :param tick: The tick to insert
        :type tick: Tick
        """
        assert isinstance(tick, Tick), type(tick)

        if not self._price_level_exists(tick.price):  # First tick for that price
            self._create_price_level(tick.price)
        tick_entry = TickEntry(tick, self._price_map[tick.price])
        self.get_price_level(tick.price).append_tick(tick_entry)
        self._tick_map[tick.order_id] = tick_entry
        self._volume += tick.quantity

    def remove_tick(self, order_id):
        """
        Remove a tick with the given order id from this side of the order book

        :param order_id: The order id of the tick that needs to be removed
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

        tick = self.get_tick(order_id)
        self._volume -= tick.quantity
        tick.price_level().remove_tick(tick)
        if len(tick.price_level()) == 0:  # Last tick for that price
            self._remove_price_level(tick.price)
        del self._tick_map[order_id]

    @property
    def max_price(self):
        """
        Return the maximum price that a tick is listed for on this side of the order book

        :return: The maximum price
        :rtype: Price
        """
        if self._depth > 0:
            return self._price_tree.max_key()
        else:
            return None

    @property
    def min_price(self):
        """
        Return the minimum price that a tick is listed for on this side of the order book

        :return: The minimum price
        :rtype: Price
        """
        if self._depth > 0:
            return self._price_tree.min_key()
        else:
            return None

    @property
    def max_price_list(self):
        """
        Return the price level for the maximum price

        :return: The maximum price level
        :rtype: PriceLevel
        """
        if self._depth > 0:
            return self.get_price_level(self.max_price)
        else:
            return None

    @property
    def min_price_list(self):
        """
        Return the price level for the minimum price

        :return: The minimum price level
        :rtype: PriceLevel
        """
        if self._depth > 0:
            return self.get_price_level(self.min_price)
        else:
            return None
