from timestamp import Timestamp


class TraderId(object):
    """Immutable class for representing the id of a trader."""

    def __init__(self, trader_id):
        """
        Initialise the trader id

        :param trader_id: String representing the trader id
        :type trader_id: str
        """
        super(TraderId, self).__init__()

        assert isinstance(trader_id, str), type(trader_id)

        self._trader_id = trader_id

    def __str__(self):
        """
        Return the string representation of the trader id

        :return: The string representation of the trader id
        :rtype: str
        """
        return "%s" % self._trader_id

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, TraderId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._trader_id == \
                   other._trader_id

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
        return hash(self._trader_id)


class MessageNumber(object):
    """Immutable class for representing the number of a message."""

    def __init__(self, message_number):
        """
        Initialise the message number

        :param message_number: String representing the number of a message
        :type message_number: str
        """
        super(MessageNumber, self).__init__()

        assert isinstance(message_number, str), type(message_number)

        self._message_number = message_number

    def __str__(self):
        """
        Return the string representation of the message number

        :return: The string representation of the message number
        :rtype: str
        """
        return "%s" % self._message_number

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, MessageNumber):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._message_number == \
                   other._message_number

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
        return hash(self._message_number)


class MessageId(object):
    """Immutable class for representing the id of a message."""

    def __init__(self, trader_id, message_number):
        """
        Initialise the message id

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
        Return the trader id

        :return: The trader id of the message id
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def message_number(self):
        """
        Return the message number

        :return: The message number of the message id
        :rtype: MessageNumber
        """
        return self._message_number

    def __str__(self):
        """
        Return the string representation of the message id

        format: <trader_id>.<message_number>

        :return: The string representation of the message id
        :rtype: str
        """
        return "%s.%s" % (self._trader_id, self._message_number)

    def __eq__(self, other):
        """
        Check if two objects are the same

        :param other: An object to compare with
        :return: True if the object is the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, MessageId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self._trader_id, self._message_number) == \
                   (other._trader_id, other._message_number)

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
        return hash((self._trader_id, self._message_number))


class Message(object):
    """Abstract class for representing a message."""

    def __init__(self, message_id, timestamp):
        """
        Initialise the message

        Don't use this class directly

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
        Return the message id of the message

        :return: The message id
        :rtype: MessageId
        """
        return self._message_id

    @property
    def timestamp(self):
        """
        Return the timestamp of the message

        :return: The timestamp
        :rtype: Timestamp
        """
        return self._timestamp
