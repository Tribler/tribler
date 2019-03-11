from __future__ import absolute_import

from six import binary_type

from Tribler.community.market.core.timestamp import Timestamp


class TraderId(object):
    """Immutable class for representing the id of a trader."""

    def __init__(self, trader_id):
        """
        :param trader_id: String representing the trader id
        :type trader_id: binary_type
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(TraderId, self).__init__()

        trader_id = trader_id if isinstance(trader_id, bytes) else binary_type(trader_id)

        if not isinstance(trader_id, binary_type):
            raise ValueError("Trader id must be a binary type")

        try:
            int(trader_id, 16)
        except ValueError:  # Not a hexadecimal
            raise ValueError("Trader id must be hexadecimal")

        self._trader_id = trader_id

    def __str__(self):
        return "%s" % self._trader_id

    def to_string(self):
        return self._trader_id

    def __eq__(self, other):
        if not isinstance(other, TraderId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._trader_id == other.to_string()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._trader_id)


class Message(object):
    """Abstract class for representing a message."""

    def __init__(self, trader_id, timestamp):
        """
        Don't use this class directly, use on of its implementations

        :param trader_id: The trader id of the message sender
        :param timestamp: A timestamp when the message was created
        :type trader_id: TraderId
        :type timestamp: Timestamp
        """
        super(Message, self).__init__()

        self._trader_id = trader_id
        self._timestamp = timestamp

    @property
    def trader_id(self):
        """
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp
