from Tribler.dispersy.util import is_valid_address


class SocketAddress(object):
    """Immutable class for representing a socket address."""

    def __init__(self, ip, port):
        """
        Initialise the socket address

        :param ip: String representation of an ipv4 address
        :type ip: str
        :param port: Integer representation of a port
        :type port: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(SocketAddress, self).__init__()

        assert isinstance(ip, str), type(ip)
        assert isinstance(port, int), type(port)

        if not is_valid_address((ip, port)):
            raise ValueError("Address is not valid")

        self._ip = ip
        self._port = port

    @property
    def ip(self):
        """
        Return the ip of the address

        :return: The ip
        :rtype: str
        """
        return self._ip

    @property
    def port(self):
        """
        Return the port of the address

        :return: The port
        :rtype: int
        """
        return self._port

    def __str__(self):
        """
        Return the string representation of the address

        :return: The string representation of the address
        :rtype: str
        """
        return "%s:%i" % self._ip, self._port

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, SocketAddress):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self._ip, self._port) == \
                   (other._ip, self._port)

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
        return hash((self._ip, self._port))

