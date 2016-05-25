from message import TraderId
from price import Price
from quantity import Quantity
from timeout import Timeout
from timestamp import Timestamp


class TickWasNotReserved(Exception):
    """Used for throwing exception when a tick was not reserved"""
    pass


class OrderNumber(object):
    """Immutable class for representing the number of an order."""

    def __init__(self, order_number):
        """
        Initialise the order number

        :param order_number: String representing the number of an order
        :type order_number: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(OrderNumber, self).__init__()

        if not isinstance(order_number, str):
            raise ValueError("Order number must be a string")

        self._order_number = order_number

    def __str__(self):
        """
        Return the string representation of the order number

        :return: The string representation of the order number
        :rtype: str
        """
        return "%s" % self._order_number

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, OrderNumber):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._order_number == \
                   other._order_number

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._order_number)


class OrderId(object):
    """Immutable class for representing the id of an order."""

    def __init__(self, trader_id, order_number):
        """
        Initialise the order id

        :param trader_id: The trader id who created the order
        :param order_number: The number of the order created
        :type trader_id: TraderId
        :type order_number: OrderNumber
        """
        super(OrderId, self).__init__()

        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(order_number, OrderNumber), type(order_number)

        self._trader_id = trader_id
        self._order_number = order_number

    @property
    def trader_id(self):
        """
        Return the trader id

        :return: The trader id of the message id
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def order_number(self):
        """
        Return the order number

        :return: The order number of the order id
        :rtype: OrderNumber
        """
        return self._order_number

    def __str__(self):
        """
        Return the string representation of the order id

        format: <trader_id>.<order_number>

        :return: The string representation of the order id
        :rtype: str
        """
        return "%s.%s" % (self._trader_id, self._order_number)

    def __eq__(self, other):
        """
        Check if two objects are the same

        :param other: An object to compare with
        :return: True if the object is the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, OrderId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self._trader_id, self._order_number) == \
                   (other._trader_id, other._order_number)

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the object is not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash((self._trader_id, self._order_number))


class Order(object):
    """Class for representing an ask or a bid created by the user"""

    def __init__(self, order_id, price, quantity, timeout, timestamp, is_ask):
        """
        Initialise the order

        :param order_id: An order id to identify the order
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param timeout: A timeout when this tick is going to expire
        :param timestamp: A timestamp when the order was created
        :param is_ask: A bool to indicate if this order is an ask
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type is_ask: bool
        """
        super(Order, self).__init__()

        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        assert isinstance(is_ask, bool), type(is_ask)

        self._order_id = order_id
        self._price = price
        self._quantity = quantity
        self._reserved_quantity = Quantity(0)
        self._timeout = timeout
        self._timestamp = timestamp
        self._is_ask = is_ask
        self._reserved_ticks = {}

    @property
    def order_id(self):
        """
        Return the order id of the order

        :return: The order id
        :rtype: OrderId
        """
        return self._order_id

    @property
    def price(self):
        """
        Return the price of the order

        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def total_quantity(self):
        """
        Return the total quantity of the order

        :return: The total quantity
        :rtype: Quantity
        """
        return self._quantity

    @property
    def available_quantity(self):
        """
        Return the available quantity of the order

        The quantity that is not reserved

        :return: The available quantity
        :rtype: Quantity
        """
        return self._quantity - self._reserved_quantity

    @property
    def reserved_quantity(self):
        """
        Return the reserved quantity of the order

        :return: The reserved quantity
        :rtype: Quantity
        """
        return self._reserved_quantity

    @property
    def timeout(self):
        """
        Return when the order is going to expire

        :return: The timeout
        :rtype: Timeout
        """
        return self._timeout

    @property
    def timestamp(self):
        """
        Return the timestamp of the message

        :return: The timestamp
        :rtype: Timestamp
        """
        return self._timestamp

    def is_ask(self):
        """
        Return if the message is an ask

        :return: True if message is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    def reserve_quantity_for_tick(self, order_id, quantity):
        """
        Reserve quantity in the order for the tick provided

        :param order_id: The order id from another peer that the quantity needs to be reserved for
        :param quantity: The quantity to reserve
        :type order_id: OrderId
        :type quantity: Quantity
        :return: True if the quantity was reserved, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(quantity, Quantity), type(quantity)

        if self.available_quantity >= quantity:
            if order_id not in self._reserved_ticks:
                self._reserved_quantity += quantity
                self._reserved_ticks[order_id] = quantity
            return True
        else:
            return False

    def release_quantity_for_tick(self, order_id):
        """
        Release quantity in the order for the tick provided

        :param order_id: The order id from another peer that the quantity needs to be released for
        :type order_id: OrderId
        :raises TickWasNotReserved: Thrown when the tick was not reserved first
        """
        if order_id in self._reserved_ticks:
            if self._reserved_quantity >= self._reserved_ticks[order_id]:
                self._reserved_quantity -= self._reserved_ticks[order_id]
                del self._reserved_ticks[order_id]
        else:
            raise TickWasNotReserved()
