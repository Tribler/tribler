import datetime
import time


class Timestamp(object):
    """Immutable class for representing a timestamp."""

    def __init__(self, timestamp):
        """
        Initialise the timestamp

        :param timestamp: Float representation of a timestamp
        :type timestamp: float
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Timestamp, self).__init__()

        if not isinstance(timestamp, float):
            raise ValueError("Timestamp must be a float")

        if timestamp < 0:
            raise ValueError("Timestamp can not be negative")

        self._timestamp = timestamp

    @classmethod
    def now(cls):
        """
        Create a timestamp with the time set to the current time

        :return: A timestamp
        :rtype: Timestamp
        """
        return cls(time.time())

    def __float__(self):
        """
        Return the float representation of the timestamp

        :return: The float representation of the timestamp
        :rtype: float
        """
        return self._timestamp

    def __str__(self):
        """
        Return the string representation of the timestamp

        :return: The string representation of the timestamp
        :rtype: str
        """
        return "%s" % datetime.datetime.fromtimestamp(self._timestamp)

    def __lt__(self, other):
        """
        Check if the supplied object is less than this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower, False otherwise
        :rtype: bool
        """
        if isinstance(other, Timestamp):
            return self._timestamp < other._timestamp
        if isinstance(other, float):
            return self._timestamp < other
        else:
            return NotImplemented

    def __le__(self, other):
        """
        Check if the supplied object is less than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Timestamp):
            return self._timestamp <= other._timestamp
        if isinstance(other, float):
            return self._timestamp <= other
        else:
            return NotImplemented

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, Timestamp):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._timestamp == \
                   other._timestamp

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __gt__(self, other):
        """
        Check if the supplied object is greater than this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger, False otherwise
        :rtype: bool
        """
        if isinstance(other, Timestamp):
            return self._timestamp > other._timestamp
        if isinstance(other, float):
            return self._timestamp > other
        else:
            return NotImplemented

    def __ge__(self, other):
        """
        Check if the supplied object is greater than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Timestamp):
            return self._timestamp >= other._timestamp
        if isinstance(other, float):
            return self._timestamp >= other
        else:
            return NotImplemented

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._timestamp)
