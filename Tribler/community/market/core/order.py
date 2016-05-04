from price_level import PriceLevel
from tick import Tick


class Order(object):
    """Class for representing an order in the order book"""

    def __init__(self, tick, price_level):
        """
        Initialise the order

        :param tick: A tick to represent in the order book
        :param price_level: A price level to place the order in
        :type tick: Tick
        :type price_level: PriceLevel
        """
        assert isinstance(tick, Tick), type(tick)
        assert isinstance(price_level, PriceLevel), type(price_level)

        self._tick = tick
        self._price_level = price_level
        self._prev_order = None
        self._next_order = None

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

    def price_level(self):
        """
        Return the price level

        :return: The price level the order was placed in
        :rtype: PriceLevel
        """
        return self._price_level

    def prev_order(self):
        """
        Return the order before this one

        This returns an order that was created earlier

        :return: The previous order
        :rtype: Order
        """
        return self._prev_order

    def next_order(self):
        """
        Return the order after this one

        This returns an order that was created later

        :return: The next order
        :rtype: Order
        """
        return self._next_order

    def __str__(self):
        """
        Return the string representation of the order

        format: <quantity>\t@\t<price>

        :return: The string representation of the order
        :rtype: str
        """
        return "%s\t@\t%s" % (str(self._tick.quantity), str(self._tick.price))
