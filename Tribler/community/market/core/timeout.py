import datetime

from timestamp import Timestamp


class Timeout(object):
    """Used for having a validated instance of a timeout that we can easily check if it still valid."""

    def __init__(self, timeout):
        """
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
        return self._timeout

    def __str__(self):
        return "%s" % datetime.datetime.fromtimestamp(self._timeout)

    def __hash__(self):
        return hash(self._timeout)
