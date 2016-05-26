class BitcoinAddress(object):
    """Immutable class for representing a bitcoin address."""

    def __init__(self, bitcoin_address):
        """
        Initialise the bitcoin address

        :param bitcoin_address: String representation of a bitcoin address
        :type bitcoin_address: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(BitcoinAddress, self).__init__()

        if not isinstance(bitcoin_address, str):
            raise ValueError("Bitcoin address must be a string")

        self._bitcoin_address = bitcoin_address

    @property
    def bitcoin_address(self):
        """
        Return the bitcoin address

        :return: The bitcoin addres
        :rtype: str
        """
        return self._bitcoin_address

    def __str__(self):
        """
        Return the string representation of the bitcoin address

        :return: The string representation of the bitcoin address
        :rtype: str
        """
        return "%s" % self._bitcoin_address

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, BitcoinAddress):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._bitcoin_address == other._bitcoin_address

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
        return hash(self._bitcoin_address)

