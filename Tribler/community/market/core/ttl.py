class Ttl(object):
    """
    The time to live is used for keeping track of how many nodes have relayed this messages.
    The number of relayed nodes should be kept low to prevent a flooding of the overlay network.
    Two was chosen because it provides the best balance between flooding the network and still
    reaching enough nodes to find good trades
    """

    DEFAULT = 2

    def __init__(self, ttl):
        """
        :param ttl: Integer representation of a time to live
        :type ttl: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Ttl, self).__init__()

        if not isinstance(ttl, int):
            raise ValueError("Time to live must be an int")

        if ttl < 0:
            raise ValueError("Time to live must be greater than zero")

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
        Check if the ttl is still hig enough to be send on

        :return: True if it is alive, False otherwise
        :rtype: bool
        """
        return self._ttl > 0

    def make_hop(self):
        """
        Makes a hop by reducing the ttl by 1, to simulate the message being relayed through a node
        """
        self._ttl -= 1

    def __int__(self):
        return self._ttl
