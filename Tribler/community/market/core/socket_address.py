from Tribler.dispersy.util import is_valid_address


class SocketAddress(object):
    """Used for having a validated instance of a socket address for the candidate destination."""

    def __init__(self, ip, port):
        """
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
        :return: The ip
        :rtype: str
        """
        return self._ip

    @property
    def port(self):
        """
        :return: The port
        :rtype: int
        """
        return self._port
