class BitcoinAddress(object):
    """Used for having a validated instance of a bitcoin address that we can easily check if it still valid."""

    def __init__(self, bitcoin_address):
        """
        :param bitcoin_address: String representation of a bitcoin address
        :type bitcoin_address: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(BitcoinAddress, self).__init__()

        if not isinstance(bitcoin_address, str):
            raise ValueError("Bitcoin address must be a string")

        self._bitcoin_address = bitcoin_address

    def __str__(self):
        return "%s" % self._bitcoin_address
