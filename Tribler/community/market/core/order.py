import logging

from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class TickWasNotReserved(Exception):
    """Used for throwing exception when a tick was not reserved"""
    pass


class OrderNumber(object):
    """Immutable class for representing the number of an order."""

    def __init__(self, order_number):
        """
        :param order_number: Integer representing the number of an order
        :type order_number: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(OrderNumber, self).__init__()

        if not isinstance(order_number, (int, long)):
            raise ValueError("Order number must be an integer or long")

        self._order_number = order_number

    def __int__(self):
        return self._order_number

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
                   (other.trader_id, other.order_number)

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
        self._logger = logging.getLogger(self.__class__.__name__)

        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        assert isinstance(is_ask, bool), type(is_ask)

        self._order_id = order_id
        self._price = price
        self._quantity = quantity
        self._reserved_quantity = Quantity(0, quantity.wallet_id)
        self._traded_quantity = Quantity(0, quantity.wallet_id)
        self._timeout = timeout
        self._timestamp = timestamp
        self._completed_timestamp = None
        self._is_ask = is_ask
        self._reserved_ticks = {}
        self._cancelled = False

    @classmethod
    def from_database(cls, data, reserved_ticks):
        """
        Create an Order object based on information in the database.
        """
        trader_id, order_number, price, price_type, quantity, quantity_type, traded_quantity, timeout, \
        order_timestamp, completed_timestamp, is_ask, cancelled = data

        order_id = OrderId(TraderId(str(trader_id)), OrderNumber(order_number))
        order = cls(order_id, Price(price, str(price_type)), Quantity(quantity, str(quantity_type)), Timeout(timeout),
                    Timestamp(order_timestamp), bool(is_ask))
        order._traded_quantity = Quantity(traded_quantity, str(quantity_type))
        order._cancelled = bool(cancelled)
        if completed_timestamp:
            order._completed_timestamp = Timestamp(completed_timestamp)

        for reserved_order_id, quantity in reserved_ticks:
            order.reserved_ticks[reserved_order_id] = quantity
            order._reserved_quantity += quantity

        return order

    def to_database(self):
        """
        Returns a database representation of an Order object.
        :rtype: tuple
        """
        completed_timestamp = float(self.completed_timestamp) if self.completed_timestamp else None
        return (unicode(self.order_id.trader_id), unicode(self.order_id.order_number), float(self.price),
                unicode(self.price.wallet_id), float(self.total_quantity), unicode(self.total_quantity.wallet_id),
                float(self.traded_quantity), float(self.timeout), float(self.timestamp), completed_timestamp,
                self.is_ask(), self._cancelled)

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
        self._logger.debug("quantity: %s, reserved: %s, traded: %s", self._quantity, self._reserved_quantity,
                           self._traded_quantity)
        return self._quantity - self._reserved_quantity - self._traded_quantity

    @property
    def reserved_quantity(self):
        """
        Return the reserved quantity of the order
        :rtype: Quantity
        """
        return self._reserved_quantity

    @property
    def traded_quantity(self):
        """
        Return the traded quantity of the order
        :rtype: Quantity
        """
        return self._traded_quantity

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

    @property
    def completed_timestamp(self):
        """
        :return: the timestamp of completion of this order, None if this order is not completed (yet).
        :rtype: Timestamp
        """
        return self._completed_timestamp

    def is_ask(self):
        """
        :return: True if message is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    @property
    def cancelled(self):
        """
        :return: whether the order has been cancelled or not.
        :rtype: bool
        """
        return self._cancelled

    def is_complete(self):
        """
        :return: True if the order is completed.
        :rtype: bool
        """
        return self._traded_quantity >= self._quantity

    @property
    def status(self):
        """
        Return the status of this order. Can be one of these: "open", "completed", "expired" or "cancelled"
        :return: The status of this order
        :rtype: str
        """
        if self._cancelled:
            return "cancelled"
        elif self.is_complete():
            return "completed"
        elif self._timeout.is_timed_out(self._timestamp):
            return "expired"
        return "open"

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
            self._reserved_quantity += quantity
            if order_id not in self._reserved_ticks:
                self._reserved_ticks[order_id] = quantity
            else:
                self._reserved_ticks[order_id] += quantity
        else:
            raise ValueError("Order %s does not have enough available quantity for reservation", self.order_id)

        self._logger.debug("reserved quantity for order id %s (own order id: %s),"
                           "total quantity: %s, traded quantity: %s, reserved quantity: %s",
                           str(order_id), str(self.order_id), self.total_quantity, self.traded_quantity,
                           self.reserved_quantity)

    def release_quantity_for_tick(self, order_id, quantity):
        """
        Release all quantity for a specific tick.
        :param order_id: The order id from another peer that the quantity needs to be released for
        :type order_id: OrderId
        :raises TickWasNotReserved: Thrown when the tick was not reserved first
        """
        if order_id not in self._reserved_ticks:
            raise TickWasNotReserved()

        if self._reserved_quantity >= quantity:
            self._reserved_quantity -= quantity
            self._reserved_ticks[order_id] -= quantity
            assert self.available_quantity >= Quantity(0, self._quantity.wallet_id), str(self.available_quantity)

            if self._reserved_ticks[order_id] == Quantity(0, quantity.wallet_id):  # Remove the quantity if it's zero
                del self._reserved_ticks[order_id]
        else:
            raise ValueError("Not enough reserved quantity for order id %s" % order_id)

        self._logger.debug("Released quantity for order id %s (own order id: %s),"
                           "total quantity: %s, traded quantity: %s, reserved quantity: %s",
                           str(order_id), str(self.order_id), self.total_quantity, self.traded_quantity,
                           self.reserved_quantity)

    def is_valid(self):
        """
        :return: True if valid, False otherwise
        :rtype: bool
        """
        return not self._timeout.is_timed_out(self._timestamp) and not self._cancelled

    def cancel(self):
        self._cancelled = True

    def add_trade(self, other_order_id, quantity):
        assert isinstance(other_order_id, OrderId), type(other_order_id)

        self._logger.debug("Adding trade for order %s with quantity %s (other id: %s)",
                           str(self.order_id), quantity, str(other_order_id))
        self._traded_quantity += quantity
        self.release_quantity_for_tick(other_order_id, quantity)
        assert self.available_quantity >= Quantity(0, quantity.wallet_id), str(self.available_quantity)

        if self.is_complete():
            self._completed_timestamp = Timestamp.now()

    def to_dictionary(self):
        """
        Return a dictionary representation of this dictionary.
        """
        completed_timestamp = float(self.completed_timestamp) if self.completed_timestamp else None
        return {
            "trader_id": str(self.order_id.trader_id),
            "order_number": int(self.order_id.order_number),
            "price": float(self.price),
            "price_type": self.price.wallet_id,
            "quantity": float(self.total_quantity),
            "quantity_type": self.total_quantity.wallet_id,
            "reserved_quantity": float(self.reserved_quantity),
            "traded_quantity": float(self.traded_quantity),
            "timeout": float(self.timeout),
            "timestamp": float(self.timestamp),
            "completed_timestamp": completed_timestamp,
            "is_ask": self.is_ask(),
            "cancelled": self.cancelled,
            "status": self.status
        }
