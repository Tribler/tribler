class Ttl(object):
    """Class for representing a time to live."""

    DEFAULT = 2

    def __init__(self, ttl):
        """
        Initialise the time to live

        :param ttl: Integer representation of a time to live
        :type ttl: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Ttl, self).__init__()

        if not isinstance(ttl, int):
            raise ValueError("Time to live must be an int")

        if ttl > 2 or ttl < 0:
            raise ValueError("Time to live must be between 0 and 2")

        self._ttl = ttl

    @classmethod
    def default(cls):
        """
        Create a time to live with the default value

        :return: The ttl
        :rtype: Ttl
        """
        return cls(cls.DEFAULT)

    def is_alive(self):
        """
        Check if the ttl is still alive and needs to be send on

        :return: True if it is alive, False otherwise
        :rtype: bool
        """
        return self._ttl > 0

    def make_hop(self):
        """
        Makes a hop by reducing the ttl by 1
        """
        self._ttl -= 1

    def __int__(self):
        """
        Return the integer representation of the ttl

        :return: The integer representation of the ttl
        :rtype: integer
        """
        return self._ttl

    def __str__(self):
        """
        Return the string representation of the ttl

        :return: The string representation of the ttl
        :rtype: str
        """
        return "%s" % str(self._ttl)

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, Ttl):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._ttl == \
                   other._ttl

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
        return hash(self._ttl)
