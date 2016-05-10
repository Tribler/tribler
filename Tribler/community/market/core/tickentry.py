from tick import Tick, Quantity


class TickEntry(object):
    """Class for representing a tick in the order book"""

    def __init__(self, tick, price_level):
        """
        Initialise the tick entry

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
    def message_id(self):
        """
        Return the message id of the tick

        :return: The message id
        :rtype: MessageId
        """
        return self._tick.message_id

    @property
    def price(self):
        """
        Return the price of the tick

        :return: The price
        :rtype: Price
        """
        return self._tick.price

    @property
    def quantity(self):
        """
        Return the quantity of the tick

        :return: The quantity
        :rtype: Quantity
        """
        return self._tick.quantity

    @quantity.setter
    def quantity(self, new_quantity):
        """
        Set the quantity of the tick

        :param new_quantity: The new quantity
        :type new_quantity: Quantity
        """
        assert isinstance(new_quantity, Quantity), type(new_quantity)

        self._price_level.depth -= (self._tick.quantity - new_quantity)
        self._tick.quantity = new_quantity

    def price_level(self):
        """
        Return the price level

        :return: The price level the tick was placed in
        :rtype: PriceLevel
        """
        return self._price_level

    def prev_tick(self):
        """
        Return the tick before this one

        This returns a tick that was inserted earlier

        :return: The previous tick
        :rtype: TickEntry
        """
        return self._prev_tick

    def next_tick(self):
        """
        Return the tick after this one

        This returns a tick that was inserted later

        :return: The next tick
        :rtype: TickEntry
        """
        return self._next_tick

    def __str__(self):
        """
        Return the string representation of the tick entry

        format: <quantity>\t@\t<price>

        :return: The string representation of the tick entry
        :rtype: str
        """
        return "%s\t@\t%s" % (str(self._tick.quantity), str(self._tick.price))
