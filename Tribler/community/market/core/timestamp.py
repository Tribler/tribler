from __future__ import absolute_import

import datetime
import time

from six import integer_types


class Timestamp(object):
    """Used for having a validated instance of a timestamp that we can easily compare."""

    def __init__(self, timestamp):
        """
        :param timestamp: Float representation of a timestamp
        :type timestamp: float
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Timestamp, self).__init__()

        if not isinstance(timestamp, (float, integer_types)):
            raise ValueError("Timestamp must be a float or a integer")

        if timestamp < 0:
            raise ValueError("Timestamp can not be negative")

        self._timestamp = float(timestamp)

    @classmethod
    def now(cls):
        """
        Create a timestamp with the time set to the current time

        :return: A timestamp
        :rtype: Timestamp
        """
        return cls(time.time())

    def __float__(self):
        return self._timestamp

    def __str__(self):
        return "%s" % datetime.datetime.fromtimestamp(self._timestamp)

    def __lt__(self, other):
        if isinstance(other, Timestamp):
            return self._timestamp < other._timestamp
        if isinstance(other, float):
            return self._timestamp < other
        else:
            return NotImplemented

    def __le__(self, other):
        if isinstance(other, Timestamp):
            return self._timestamp <= other._timestamp
        if isinstance(other, float):
            return self._timestamp <= other
        else:
            return NotImplemented

    def __eq__(self, other):
        if not isinstance(other, Timestamp):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._timestamp == \
                   other._timestamp

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        if isinstance(other, Timestamp):
            return self._timestamp > other._timestamp
        if isinstance(other, float):
            return self._timestamp > other
        else:
            return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Timestamp):
            return self._timestamp >= other._timestamp
        if isinstance(other, float):
            return self._timestamp >= other
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self._timestamp)
