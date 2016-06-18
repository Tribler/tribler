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
        :param order_number: String representing the number of an order
        :type order_number: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(OrderNumber, self).__init__()

        if not isinstance(order_number, str):
            raise ValueError("Order number must be a string")

        self._order_number = order_number

    def __str__(self):
        return "%s" % self._order_number

    def __eq__(self, other):
        if not isinstance(other, OrderNumber):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._order_number == \
                   other._order_number

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._order_number)


class OrderId(object):
    """Immutable class for representing the id of an order."""

    def __init__(self, trader_id, order_number):
        """
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
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def order_number(self):
        """
        :rtype: OrderNumber
        """
        return self._order_number

    def __str__(self):
        """
        format: <trader_id>.<order_number>
        """
        return "%s.%s" % (self._trader_id, self._order_number)

    def __eq__(self, other):
        if not isinstance(other, OrderId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self._trader_id, self._order_number) == \
                   (other._trader_id, other._order_number)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self._trader_id, self._order_number))


class Order(object):
    """Class for representing an ask or a bid created by the user"""

    def __init__(self, order_id, price, quantity, timeout, timestamp, is_ask):
        """
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
        self._accepted_trades = {}
        self._transactions = {}

    @property
    def reserved_ticks(self):
        """
        :rtype: Dictionary[OrderId: Quantity]
        """
        return self._reserved_ticks

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._order_id

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self._price

    @property
    def total_quantity(self):
        """
        Return the total quantity of the order
        :rtype: Quantity
        """
        return self._quantity

    @property
    def available_quantity(self):
        """
        Return the quantity that is not reserved
        :rtype: Quantity
        """
        return self._quantity - self._reserved_quantity

    @property
    def reserved_quantity(self):
        """
        Return the reserved quantity of the order
        :rtype: Quantity
        """
        return self._reserved_quantity

    @property
    def timeout(self):
        """
        Return when the order is going to expire
        :rtype: Timeout
        """
        return self._timeout

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp

    def is_ask(self):
        """
        :return: True if message is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    def reserve_quantity_for_tick(self, order_id, quantity):
        """
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

    def is_valid(self):
        """
        :return: True if valid, False otherwise
        :rtype: bool
        """
        return not self._timeout.is_timed_out(Timestamp.now())

    def cancel(self):
        self._timeout = Timestamp.now()

    def add_trade(self, accepted_trade):
        self._accepted_trades[accepted_trade.message_id] = accepted_trade

    def add_transaction(self, accepted_trade_message_id, transaction):
        self._transactions[accepted_trade_message_id] = transaction.transaction_id
