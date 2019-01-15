from __future__ import absolute_import

from six import string_types


class WalletAddress(object):
    """Used for having a validated instance of a wallet address that we can easily check if it still valid."""

    def __init__(self, wallet_address):
        """
        :param wallet_address: String representation of a wallet address
        :type wallet_address: str or unicode
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(WalletAddress, self).__init__()

        if not isinstance(wallet_address, string_types):
            raise ValueError("Wallet address must be a string, found %s instead" % type(wallet_address))

        self._wallet_address = wallet_address

    def __eq__(self, other):
        return str(other) == self._wallet_address

    def __str__(self):
        return "%s" % self._wallet_address
