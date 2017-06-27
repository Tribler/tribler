from Tribler.community.market.wallet import ASSET_MAP


class Price(object):
    """Price is used for having a consistent comparable and usable class that deals with floats."""

    def __init__(self, price, wallet_id):
        """
        :param price: Integer representation of a price that is positive or zero
        :param wallet_id: Identifier of the wallet type of this price
        :type price: float
        :type wallet_id: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Price, self).__init__()

        if not isinstance(price, (int, float)):
            raise ValueError("Price must be an int or a float")

        if not isinstance(wallet_id, str):
            raise ValueError("Wallet id must be a string")

        if price < 0:
            raise ValueError("Price must be positive or zero")

        self._price = price
        self._wallet_id = wallet_id

    @property
    def wallet_id(self):
        """
        :rtype: str
        """
        return self._wallet_id

    @property
    def int_wallet_id(self):
        """
        :rtype: int
        """
        return ASSET_MAP[self._wallet_id]

    def __int__(self):
        return int(self._price)

    def __float__(self):
        return float(self._price)

    def __str__(self):
        return "%f %s" % (self._price, self.wallet_id)

    def __add__(self, other):
        if isinstance(other, Price) and self.wallet_id == other.wallet_id:
            return Price(self._price + float(other), self._wallet_id)
        else:
            return NotImplemented

    def __sub__(self, other):
        if isinstance(other, Price) and self.wallet_id == other.wallet_id:
            return Price(self._price - float(other), self._wallet_id)
        else:
            return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Price) and self.wallet_id == other.wallet_id:
            return self._price < float(other)
        else:
            return NotImplemented

    def __le__(self, other):
        if isinstance(other, Price) and self.wallet_id == other.wallet_id:
            return self._price <= float(other)
        else:
            return NotImplemented

    def __eq__(self, other):
        if not isinstance(other, Price) or self.wallet_id != other.wallet_id:
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._price == float(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        if isinstance(other, Price) and self.wallet_id == other.wallet_id:
            return self._price > float(other)
        else:
            return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Price) and self.wallet_id == other.wallet_id:
            return self._price >= float(other)
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self._price)
