from quantity import Quantity
from tick import Tick


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

    def prev_tick(self):
        """
        :rtype: TickEntry
        """
        return self._prev_tick

    def next_tick(self):
        """
        :rtype: TickEntry
        """
        return self._next_tick

    def __str__(self):
        """
        format: <quantity>\t@\t<price>
        :rtype: str
        """
        return "%s\t@\t%s" % (str(self._tick.quantity), str(self._tick.price))
