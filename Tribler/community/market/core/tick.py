from order import OrderId, OrderNumber, Order
from message import TraderId, MessageNumber, MessageId, Message
from price import Price
from quantity import Quantity
from timeout import Timeout
from timestamp import Timestamp


class Tick(Message):
    """
    Abstract message class for representing a order on another node. This tick is replicating the order sitting on
    the node it belongs to.
    """

    def __init__(self, message_id, order_id, price, quantity, timeout, timestamp, is_ask):
        """
        Don't use this class directly, use one of the class methods

        :param message_id: A message id to identify the tick
        :param order_id: A order id to identify the order this tick represents
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param timeout: A timeout when this tick is going to expire
        :param timestamp: A timestamp when the tick was created
        :param is_ask: A bool to indicate if this tick is an ask
        :type message_id: MessageId
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type is_ask: bool
        """
        super(Tick, self).__init__(message_id, timestamp)

        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)
        assert isinstance(is_ask, bool), type(is_ask)

        self._order_id = order_id
        self._price = price
        self._quantity = quantity
        self._timeout = timeout
        self._is_ask = is_ask

    @classmethod
    def from_order(cls, order, message_id):
        """
        Create a tick from an order

        :param order: The order that this tick represents
        :param message_id: The message id for the tick
        :return: The created tick
        :rtype: Tick
        """
        assert isinstance(order, Order), type(order)
        assert isinstance(message_id, MessageId), type(message_id)

        if order.is_ask():
            return Ask(message_id, order.order_id, order.price, order.total_quantity, order.timeout, order.timestamp)
        else:
            return Bid(message_id, order.order_id, order.price, order.total_quantity, order.timeout, order.timestamp)

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
    def quantity(self):
        """
        :rtype: Quantity
        """
        return self._quantity

    @quantity.setter
    def quantity(self, quantity):
        """
        :param quantity: The new quantity
        :type quantity: Quantity
        """
        assert isinstance(quantity, Quantity), type(quantity)
        self._quantity = quantity

    @property
    def timeout(self):
        """
        Return when the tick is going to expire
        :rtype: Timeout
        """
        return self._timeout

    def is_ask(self):
        """
        :return: True if this tick is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    def is_valid(self):
        """
        :return: True if valid, False otherwise
        :rtype: bool
        """
        return not self._timeout.is_timed_out(Timestamp.now())

    def to_network(self):
        """
        Return network representation of the tick

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <price>, <quantity>, <timeout>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            self._order_id.trader_id,
            self._message_id.message_number,
            self._order_id.order_number,
            self._price,
            self._quantity,
            self._timeout,
            self._timestamp,
        )


class Ask(Tick):
    """Represents an ask from a order located on another node."""

    def __init__(self, message_id, order_id, price, quantity, timeout, timestamp):
        """
        :param message_id: A message id to identify the ask
        :param order_id: A order id to identify the order this tick represents
        :param price: A price that needs to be paid for the ask
        :param quantity: The quantity that needs to be sold
        :param timeout: A timeout for the ask
        :param timestamp: A timestamp for when the ask was created
        :type message_id: MessageId
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        """
        super(Ask, self).__init__(message_id, order_id, price, quantity, timeout, timestamp, True)

    @classmethod
    def from_network(cls, data):
        """
        Restore an ask from the network

        :param data: object with (trader_id, message_number, order_number, price, quantity, timeout, timestamp) properties
        :return: Restored ask
        :rtype: Ask
        """
        assert hasattr(data, 'trader_id'), isinstance(data.trader_id, TraderId)
        assert hasattr(data, 'message_number'), isinstance(data.message_number, MessageNumber)
        assert hasattr(data, 'order_number'), isinstance(data.order_number, OrderNumber)
        assert hasattr(data, 'price'), isinstance(data.price, Price)
        assert hasattr(data, 'quantity'), isinstance(data.quantity, Quantity)
        assert hasattr(data, 'timeout'), isinstance(data.timeout, Timeout)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            MessageId(data.trader_id, data.message_number),
            OrderId(data.trader_id, data.order_number),
            data.price,
            data.quantity,
            data.timeout,
            data.timestamp,
        )


class Bid(Tick):
    """Represents a bid from a order located on another node."""

    def __init__(self, message_id, order_id, price, quantity, timeout, timestamp):
        """
        :param message_id: A message id to identify the bid
        :param order_id: A order id to identify the order this tick represents
        :param price: A price that you are willing to pay for the bid
        :param quantity: The quantity that you want to buy
        :param timeout: A timeout for the bid
        :param timestamp: A timestamp for when the bid was created
        :type message_id: MessageId
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        """
        super(Bid, self).__init__(message_id, order_id, price, quantity, timeout, timestamp, False)

    @classmethod
    def from_network(cls, data):
        """
        Restore a bid from the network

        :param data: object with (trader_id, message_number, order_number, price, quantity, timeout, timestamp) properties
        :return: Restored bid
        :rtype: Bid
        """
        assert hasattr(data, 'trader_id'), isinstance(data.trader_id, TraderId)
        assert hasattr(data, 'message_number'), isinstance(data.message_number, MessageNumber)
        assert hasattr(data, 'order_number'), isinstance(data.order_number, OrderNumber)
        assert hasattr(data, 'price'), isinstance(data.price, Price)
        assert hasattr(data, 'quantity'), isinstance(data.quantity, Quantity)
        assert hasattr(data, 'timeout'), isinstance(data.timeout, Timeout)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            MessageId(data.trader_id, data.message_number),
            OrderId(data.trader_id, data.order_number),
            data.price,
            data.quantity,
            data.timeout,
            data.timestamp,
        )
