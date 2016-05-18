from Tribler.community.market.core.order import OrderId, OrderNumber
from message import TraderId, MessageNumber, Message, MessageId
from price import Price
from quantity import Quantity
from timestamp import Timestamp


class Trade(Message):
    """Abstract class representing a trade."""

    def __init__(self, message_id, order_id, recipient_order_id, timestamp, quick):
        """
        Initialise the trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(Trade, self).__init__(message_id, timestamp)

        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(recipient_order_id, OrderId), type(recipient_order_id)
        assert isinstance(quick, bool), type(quick)

        self._order_id = order_id
        self._recipient_order_id = recipient_order_id
        self._quick = quick

    @classmethod
    def propose(cls, message_id, order_id, recipient_order_id, price, quantity, timestamp):
        """
        Propose a trade

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type timestamp: Timestamp
        :return: A proposed trade
        :rtype: ProposedTrade
        """
        return ProposedTrade(
            message_id,
            order_id,
            recipient_order_id,
            price,
            quantity,
            timestamp,
            False
        )

    @classmethod
    def quick_propose(cls, message_id, order_id, recipient_order_id, price, quantity, timestamp):
        """
        Propose a quick-trade

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :return: A proposed trade
        :rtype: ProposedTrade
        """
        return ProposedTrade(
            message_id,
            order_id,
            recipient_order_id,
            price,
            quantity,
            timestamp,
            True
        )

    @classmethod
    def accept(cls, message_id, timestamp, proposed_trade):
        """
        Accept a trade

        :param message_id: A message id to identify the trade
        :param timestamp: A timestamp when the trade was accepted
        :param proposed_trade: A proposed trade that needs to be accepted
        :type message_id: MessageId
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :return: An accepted trade
        :rtype: AcceptedTrade
        """
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)

        return AcceptedTrade(
            message_id,
            proposed_trade.order_id,
            proposed_trade.recipient_order_id,
            proposed_trade.price,
            proposed_trade.quantity,
            timestamp,
            proposed_trade.is_quick()
        )

    @classmethod
    def decline(cls, message_id, timestamp, proposed_trade):
        """
        Decline a trade

        :param message_id: A message id to identify the trade
        :param timestamp: A timestamp when the trade was declined
        :param proposed_trade: A proposed trade that needs to be declined
        :type message_id: MessageId
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :return: A declined trade
        :rtype: DeclinedTrade
        """
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)

        return DeclinedTrade(
            message_id,
            proposed_trade.order_id,
            proposed_trade.recipient_order_id,
            timestamp,
            proposed_trade.is_quick()
        )

    @classmethod
    def counter(cls, message_id, quantity, timestamp, proposed_trade):
        """
        Counter a trade

        :param message_id: A message id to identify the trade
        :param quantity: The quantity to use for the counter offer
        :param timestamp: A timestamp when the trade was countered
        :param proposed_trade: A proposed trade that needs to be countered
        :type message_id: MessageId
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :return: A counter trade
        :rtype: CounterTrade
        """
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)

        return CounterTrade(
            message_id,
            proposed_trade.recipient_order_id,
            proposed_trade.order_id,
            proposed_trade.price,
            quantity,
            timestamp,
            proposed_trade.is_quick()
        )

    @property
    def order_id(self):
        """
        Return the order id

        :return: The order id
        :rtype: OrderId
        """
        return self._order_id

    @property
    def recipient_order_id(self):
        """
        Return the order id of the party to trade with

        :return: The order id
        :rtype: OrderId
        """
        return self._recipient_order_id

    def is_quick(self):
        """
        Return if this trade was a quick-trade

        :return: True if this trade was a quick-trade, False otherwise
        :rtype: bool
        """
        return self._quick

    def to_network(self):
        return NotImplemented


class ProposedTrade(Trade):
    """Class representing a proposed trade."""

    def __init__(self, message_id, order_id, recipient_order_id, price, quantity, timestamp, quick):
        """
        Initialise a proposed trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(ProposedTrade, self).__init__(message_id, order_id, recipient_order_id, timestamp, quick)

        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)

        self._price = price
        self._quantity = quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a proposed trade from the network

        :param data: object with (trader_id, message_number, order_number, recipient_trader_id, recipient_order_number, price, quantity, timestamp, quick) properties
        :return: Restored proposed trade
        :rtype: ProposedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'order_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_order_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            OrderId(TraderId(data.trader_id), OrderNumber(data.order_number)),
            OrderId(TraderId(data.recipient_trader_id), OrderNumber(data.recipient_order_number)),
            Price.from_mil(data.price),
            Quantity.from_mil(data.quantity),
            Timestamp(data.timestamp),
            data.quick
        )

    @property
    def price(self):
        """
        Return the price

        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        Return the quantity

        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    def to_network(self):
        """
        Return network representation of a proposed trade

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <order_number>, <recipient_trader_id>, <recipient_order_number>, <price>, <quantity>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(
            [str(self._recipient_order_id.trader_id)]
        ), (
                   str(self._order_id.trader_id),
                   str(self._message_id.message_number),
                   str(self._order_id.order_number),
                   str(self._recipient_order_id.trader_id),
                   str(self._recipient_order_id.order_number),
                   int(self._price),
                   int(self._quantity),
                   float(self._timestamp),
                   bool(self._quick)
               )


class AcceptedTrade(Trade):
    """Class representing an accepted trade."""

    def __init__(self, message_id, order_id, recipient_order_id, price, quantity, timestamp, quick):
        """
        Initialise an accepted trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(AcceptedTrade, self).__init__(message_id, order_id, recipient_order_id, timestamp, quick)

        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)

        self._price = price
        self._quantity = quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore an accepted trade from the network

        :param data: object with (trader_id, message_number, order_number, recipient_trader_id, recipient_order_number, price, quantity, timestamp, quick) properties
        :return: Restored accepted trade
        :rtype: AcceptedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'order_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_order_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            OrderId(TraderId(data.trader_id), OrderNumber(data.order_number)),
            OrderId(TraderId(data.recipient_trader_id), OrderNumber(data.recipient_order_number)),
            Price.from_mil(data.price),
            Quantity.from_mil(data.quantity),
            Timestamp(data.timestamp),
            data.quick
        )

    @property
    def price(self):
        """
        Return the price

        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        Return the quantity

        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    def to_network(self):
        """
        Return network representation of an accepted trade

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <order_number>, <recipient_trader_id>, <recipient_order_number>, <price>, <quantity>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            str(self._order_id.trader_id),
            str(self._message_id.message_number),
            str(self._order_id.order_number),
            str(self._recipient_order_id.trader_id),
            str(self._recipient_order_id.order_number),
            int(self._price),
            int(self._quantity),
            float(self._timestamp),
            bool(self._quick)
        )


class DeclinedTrade(Trade):
    """Class representing a declined trade."""

    def __init__(self, message_id, order_id, recipient_order_id, timestamp, quick):
        """
        Initialise a declined trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the order
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(DeclinedTrade, self).__init__(message_id, order_id, recipient_order_id, timestamp, quick)

    @classmethod
    def from_network(cls, data):
        """
        Restore a declined trade from the network

        :param data: object with (trader_id, message_number, order_number, recipient_trader_id, recipient_order_number, timestamp, quick) properties
        :return: Restored declined trade
        :rtype: DeclinedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'order_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_order_number')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            OrderId(TraderId(data.trader_id), OrderNumber(data.order_number)),
            OrderId(TraderId(data.recipient_trader_id), OrderNumber(data.recipient_order_number)),
            Timestamp(data.timestamp),
            data.quick
        )

    def to_network(self):
        """
        Return network representation of a declined trade

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <order_number>, <recipient_trader_id>, <recipient_order_number>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(
            [str(self._recipient_order_id.trader_id)]
        ), (
                   str(self._order_id.trader_id),
                   str(self._message_id.message_number),
                   str(self._order_id.order_number),
                   str(self._recipient_order_id.trader_id),
                   str(self._recipient_order_id.order_number),
                   float(self._timestamp),
                   bool(self._quick)
               )


class CounterTrade(Trade):
    """Class representing a counter trade."""

    def __init__(self, message_id, order_id, recipient_order_id, price, quantity, timestamp, quick):
        """
        Initialise a counter trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(CounterTrade, self).__init__(message_id, order_id, recipient_order_id, timestamp, quick)

        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)

        self._price = price
        self._quantity = quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a counter trade from the network

        :param data: object with (trader_id, message_number, order_number, recipient_trader_id, recipient_order_number, price, quantity, timestamp, quick) properties
        :return: Restored counter trade
        :rtype: CounterTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'order_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_order_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            OrderId(TraderId(data.trader_id), OrderNumber(data.order_number)),
            OrderId(TraderId(data.recipient_trader_id), OrderNumber(data.recipient_order_number)),
            Price.from_mil(data.price),
            Quantity.from_mil(data.quantity),
            Timestamp(data.timestamp),
            data.quick
        )

    @property
    def price(self):
        """
        Return the price

        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        Return the quantity

        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    def to_network(self):
        """
        Return network representation of a counter trade

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <order_number>, <recipient_trader_id>, <recipient_order_number>, <price>, <quantity>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(
            [str(self._recipient_order_id.trader_id)]
        ), (
                   str(self._order_id.trader_id),
                   str(self._message_id.message_number),
                   str(self._order_id.order_number),
                   str(self._recipient_order_id.trader_id),
                   str(self._recipient_order_id.order_number),
                   int(self._price),
                   int(self._quantity),
                   float(self._timestamp),
                   bool(self._quick)
               )
