from Tribler.community.market.core.timestamp import Timestamp


class TraderId(object):
    """Immutable class for representing the id of a trader."""

    def __init__(self, trader_id):
        """
        :param trader_id: String representing the trader id
        :type trader_id: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(TraderId, self).__init__()

        if not isinstance(trader_id, str):
            raise ValueError("Trader id must be a string")

        try:
            int(trader_id, 16)
        except ValueError:  # Not a hexadecimal
            raise ValueError("Trader id must be hexadecimal")

        self._trader_id = trader_id

    def __str__(self):
        return "%s" % self._trader_id

    def __eq__(self, other):
        if not isinstance(other, TraderId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._trader_id == \
                   other._trader_id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._trader_id)


class MessageNumber(object):
    """Immutable class for representing the number of a message."""

    def __init__(self, message_number):
        """
        :param message_number: String representing the number of a message
        :type message_number: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(MessageNumber, self).__init__()

        if not isinstance(message_number, int):
            raise ValueError("Message number must be an int")

        self._message_number = message_number

    def __int__(self):
        return self._message_number

    def __str__(self):
        return str(self._message_number)

    def __eq__(self, other):
        if not isinstance(other, MessageNumber):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._message_number == \
                   other._message_number

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._message_number)


class MessageId(object):
    """Immutable class for representing the id of a message."""

    def __init__(self, trader_id, message_number):
        """
        :param trader_id: The trader id who created the message
        :param message_number: The number of the message created
        :type trader_id: TraderId
        :type message_number: MessageNumber
        """
        super(MessageId, self).__init__()

        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(message_number, MessageNumber), type(message_number)

        self._trader_id = trader_id
        self._message_number = message_number

    @property
    def trader_id(self):
        """
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def message_number(self):
        """
        :rtype: MessageNumber
        """
        return self._message_number

    def __str__(self):
        """
        format: <trader_id>.<message_number>
        :rtype: str
        """
        return "%s.%s" % (self._trader_id, self._message_number)

    def __eq__(self, other):
        if not isinstance(other, MessageId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self._trader_id, self._message_number) == \
                   (other.trader_id, other.message_number)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self._trader_id, self._message_number))


class Message(object):
    """Abstract class for representing a message."""

    def __init__(self, message_id, timestamp):
        """
        Don't use this class directly, use on of its implementations

        :param message_id: A message id to identify the message
        :param timestamp: A timestamp when the message was created
        :type message_id: MessageId
        :type timestamp: Timestamp
        """
        super(Message, self).__init__()

        assert isinstance(message_id, MessageId), type(message_id)
        assert isinstance(timestamp, Timestamp), type(timestamp)

        self._message_id = message_id
        self._timestamp = timestamp

    @property
    def message_id(self):
        """
        :rtype: MessageId
        """
        return self._message_id

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp
