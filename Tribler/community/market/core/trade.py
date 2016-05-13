from message import TraderId, MessageNumber, MessageId, Message
from price import Price
from quantity import Quantity
from timestamp import Timestamp


class Trade(Message):
    """Abstract class representing a trade."""

    def __init__(self, message_id, recipient_message_id, timestamp, quick, proposed, accepted):
        """
        Initialise the trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param recipient_message_id: A message id to identify the traded party
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :param proposed: A bool to indicate if this trade is proposed
        :param accepted: A bool to indicate if this trade is accepted
        :type message_id: MessageId
        :type recipient_message_id: MessageId
        :type timestamp: Timestamp
        :type quick: bool
        :type proposed: bool
        :type accepted: bool
        """
        super(Trade, self).__init__(message_id, timestamp)

        assert isinstance(recipient_message_id, MessageId), type(recipient_message_id)
        assert isinstance(proposed, bool), type(proposed)
        assert isinstance(accepted, bool), type(accepted)
        assert isinstance(quick, bool), type(quick)

        self._recipient_message_id = recipient_message_id
        self._proposed = proposed
        self._accepted = accepted
        self._quick = quick

    @classmethod
    def propose(cls, message_id, sender_message_id, recipient_message_id, price, quantity, timestamp):
        """
        Propose a trade

        :param message_id: A message id to identify the trade
        :param sender_message_id: A message id to identify the sending party
        :param recipient_message_id: A message id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type recipient_message_id: MessageId
        :type timestamp: Timestamp
        :return: A proposed trade
        :rtype: ProposedTrade
        """
        return ProposedTrade(
            message_id,
            sender_message_id,
            recipient_message_id,
            price,
            quantity,
            timestamp,
            False
        )

    @classmethod
    def quick_propose(cls, message_id, sender_message_id, recipient_message_id, price, quantity, timestamp):
        """
        Propose a quick-trade

        :param message_id: A message id to identify the trade
        :param sender_message_id: A message id to identify the sending party
        :param recipient_message_id: A message id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type sender_message_id: MessageId
        :type recipient_message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :return: A proposed trade
        :rtype: ProposedTrade
        """
        return ProposedTrade(
            message_id,
            sender_message_id,
            recipient_message_id,
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
            proposed_trade.sender_message_id,
            proposed_trade.recipient_message_id,
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
            proposed_trade.recipient_message_id,
            timestamp,
            proposed_trade.is_quick()
        )

    @property
    def recipient_message_id(self):
        """
        Return the message id of the party to trade with

        :return: The message id
        :rtype: MessageId
        """
        return self._recipient_message_id

    def is_proposed(self):
        """
        Return if this trade was proposed

        :return: True if this trade was proposed, False otherwise
        :rtype: bool
        """
        return self._proposed

    def is_accepted(self):
        """
        Return if this trade was accepted

        :return: True if this trade was accepted, False otherwise
        :rtype: bool
        """
        return self._accepted

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

    def __init__(self, message_id, sender_message_id, recipient_message_id, price, quantity, timestamp, quick):
        """
        Initialise a proposed trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param sender_message_id: A message id to identify the sending party
        :param recipient_message_id: A message id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type sender_message_id: MessageId
        :type recipient_message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(ProposedTrade, self).__init__(message_id, recipient_message_id, timestamp, quick, True, False)

        assert isinstance(sender_message_id, MessageId), type(sender_message_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)

        self._sender_message_id = sender_message_id
        self._price = price
        self._quantity = quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a proposed trade from the network

        :param data: object with (trader_id, message_number, sender_trader_id, sender_message_number, recipient_trader_id, recipient_message_number, price, quantity, timestamp, quick) properties
        :return: Restored proposed trade
        :rtype: ProposedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'sender_trader_id')
        assert hasattr(data, 'sender_message_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_message_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            MessageId(TraderId(data.sender_trader_id), MessageNumber(data.sender_message_number)),
            MessageId(TraderId(data.recipient_trader_id), MessageNumber(data.recipient_message_number)),
            Price.from_mil(data.price),
            Quantity(data.quantity),
            Timestamp(data.timestamp),
            data.quick
        )

    @property
    def sender_message_id(self):
        """
        Return the message id of the sender party

        :return: The message id
        :rtype: MessageId
        """
        return self._sender_message_id

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

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <sender_trader_id>, <sender_message_number>, <recipient_trader_id>, <recipient_message_number>, <price>, <quantity>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(
            [str(self._recipient_message_id.trader_id)]
        ), (
                   str(self._message_id.trader_id),
                   str(self._message_id.message_number),
                   str(self._sender_message_id.trader_id),
                   str(self._sender_message_id.message_number),
                   str(self._recipient_message_id.trader_id),
                   str(self._recipient_message_id.message_number),
                   int(self._price),
                   int(self._quantity),
                   float(self._timestamp),
                   bool(self._quick)
               )


class AcceptedTrade(Trade):
    """Class representing an accepted trade."""

    def __init__(self, message_id, sender_message_id, recipient_message_id, price, quantity, timestamp, quick):
        """
        Initialise an accepted trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param sender_message_id: A message id to identify the sending party
        :param recipient_message_id: A message id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type sender_message_id: MessageId
        :type recipient_message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(AcceptedTrade, self).__init__(message_id, recipient_message_id, timestamp, quick, False, True)

        assert isinstance(sender_message_id, MessageId), type(sender_message_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)

        self._sender_message_id = sender_message_id
        self._price = price
        self._quantity = quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore an accepted trade from the network

        :param data: object with (trader_id, message_number, sender_trader_id, sender_message_number, recipient_trader_id, recipient_message_number, price, quantity, timestamp, quick) properties
        :return: Restored accepted trade
        :rtype: AcceptedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'sender_trader_id')
        assert hasattr(data, 'sender_message_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_message_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            MessageId(TraderId(data.sender_trader_id), MessageNumber(data.sender_message_number)),
            MessageId(TraderId(data.recipient_trader_id), MessageNumber(data.recipient_message_number)),
            Price.from_mil(data.price),
            Quantity(data.quantity),
            Timestamp(data.timestamp),
            data.quick
        )

    @property
    def sender_message_id(self):
        """
        Return the message id of the sender party

        :return: The message id
        :rtype: MessageId
        """
        return self._sender_message_id

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

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <sender_trader_id>, <sender_message_number>, <recipient_trader_id>, <recipient_message_number>, <price>, <quantity>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            str(self._message_id.trader_id),
            str(self._message_id.message_number),
            str(self._sender_message_id.trader_id),
            str(self._sender_message_id.message_number),
            str(self._recipient_message_id.trader_id),
            str(self._recipient_message_id.message_number),
            int(self._price),
            int(self._quantity),
            float(self._timestamp),
            bool(self._quick)
        )


class DeclinedTrade(Trade):
    """Class representing a declined trade."""

    def __init__(self, message_id, declined_message_id, timestamp, quick):
        """
        Initialise a declined trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(DeclinedTrade, self).__init__(message_id, declined_message_id, timestamp, quick, False, False)

    @classmethod
    def from_network(cls, data):
        """
        Restore a declined trade from the network

        :param data: object with (trader_id, message_number, recipient_trader_id, recipient_message_number, timestamp, quick) properties
        :return: Restored declined trade
        :rtype: DeclinedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_message_number')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            MessageId(TraderId(data.recipient_trader_id), MessageNumber(data.recipient_message_number)),
            Timestamp(data.timestamp),
            data.quick
        )

    def to_network(self):
        """
        Return network representation of a declined trade

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <recipient_trader_id>, <recipient_message_number>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(
            [str(self._recipient_message_id.trader_id)]
        ), (
                   str(self._message_id.trader_id),
                   str(self._message_id.message_number),
                   str(self._recipient_message_id.trader_id),
                   str(self._recipient_message_id.message_number),
                   float(self._timestamp),
                   bool(self._quick)
               )
