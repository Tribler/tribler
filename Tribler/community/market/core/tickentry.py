from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Tick


class TickEntry(object):
    """Class for representing a tick in the order book"""

    def __init__(self, tick, price_level):
        """
        :param tick: A tick to represent in the order book
        :param price_level: A price level to place the tick in
        :type tick: Tick
        :type price_level: PriceLevel
        """
        assert isinstance(tick, Tick), type(tick)

        self._tick = tick
        self._price_level = price_level
        self._prev_tick = None
        self._next_tick = None

    @property
    def tick(self):
        """
        :rtype: Tick
        """
        return self._tick

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._tick.order_id

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self._tick.price

    @property
    def quantity(self):
        """
        :rtype: Quantity
        """
        return self._tick.quantity

    @quantity.setter
    def quantity(self, new_quantity):
        """
        :param new_quantity: The new quantity
        :type new_quantity: Quantity
        """
        assert isinstance(new_quantity, Quantity), type(new_quantity)

        self._price_level.depth -= (self._tick.quantity - new_quantity)
        self._tick.quantity = new_quantity

    def is_valid(self):
        """
        Return if the tick is still valid

        :return: True if valid, False otherwise
        :rtype: bool
        """
        return self._tick.is_valid()

    def price_level(self):
        """
        :return: The price level the tick was placed in
        :rtype: PriceLevel
        """
        return self._price_level

    @property
    def prev_tick(self):
        """
        :rtype: TickEntry
        """
        return self._prev_tick

    @prev_tick.setter
    def prev_tick(self, new_prev_tick):
        """
        :param new_prev_tick: The new previous tick
        :type new_prev_tick: TickEntry
        """
        self._prev_tick = new_prev_tick

    @property
    def next_tick(self):
        """
        :rtype: TickEntry
        """
        return self._next_tick

    @next_tick.setter
    def next_tick(self, new_next_tick):
        """
        :param new_next_tick: The new previous tick
        :type new_next_tick: TickEntry
        """
        self._next_tick = new_next_tick

    def __str__(self):
        """
        format: <quantity>\t@\t<price>
        :rtype: str
        """
        return "%s\t@\t%s" % (str(self._tick.quantity), str(self._tick.price))
