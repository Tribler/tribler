import datetime

from timestamp import Timestamp


class Timeout(object):
    """Immutable class for representing a timeout."""

    def __init__(self, timeout):
        """
        Initialise the timeout

        :param timeout: Float representation of a timeout
        :type timeout: float
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Timeout, self).__init__()

        if not isinstance(timeout, float):
            raise ValueError("Timeout must be a float")

        if timeout < 0:
            raise ValueError("Timeout must be positive or zero")

        self._timeout = timeout

    def is_timed_out(self, timestamp):
        """
        Return if a timeout has occurred

        :param timestamp: A timestamp
        :type timestamp: Timestamp
        :return: True if timeout has occurred, False otherwise
        :rtype: bool
        """
        assert isinstance(timestamp, Timestamp), type(timestamp)

        if self._timeout < timestamp:
            return True
        else:
            return False

    def __float__(self):
        """
        Return the float representation of the timeout

        :return: The float representation of the timeout
        :rtype: float
        """
        return self._timeout

    def __str__(self):
        """
        Return the string representation of the timeout

        :return: The string representation of the timeout
        :rtype: str
        """
        return "%s" % datetime.datetime.fromtimestamp(self._timeout)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._timeout)
