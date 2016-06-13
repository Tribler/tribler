from decimal import Decimal


class Price(object):
    """Price is used for having a consistent comparable and usable class that deals with mils and floats."""

    def __init__(self, price):
        """
        Don't call this method directly, but use one of the factory methods: from_mil, from_float

        :param price: Integer representation of a price that is positive or zero
        :type price: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Price, self).__init__()

        if not isinstance(price, int):
            raise ValueError("Price must be an int")

        if price < 0:
            raise ValueError("Price must be positive or zero")

        self._price = price

    @classmethod
    def from_mil(cls, mil_price):
        """
        A mil is 0.0001 of a price unit

        :param mil_price: A mil price (mil = 0.0001)
        :type mil_price: int
        :return: The price
        :rtype: Price
        """
        return cls(mil_price)

    @classmethod
    def from_float(cls, float_price):
        """
        :param float_price: A float representation of a price
        :type float_price: float
        :return: The price
        :rtype: Price
        """
        price = int(Decimal(str(float_price)) * Decimal('10000'))
        return cls(price)

    def __int__(self):
        return self._price

    def __float__(self):
        return (Decimal(str(self._price)) / Decimal('10000')).quantize(Decimal('0.0001'))

    def __str__(self):
        return "%s" % (Decimal(str(self._price)) / Decimal('10000')).quantize(Decimal('0.0001'))

    def __add__(self, other):
        if isinstance(other, Price):
            return Price.from_mil(self._price + other._price)
        else:
            return NotImplemented

    def __iadd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, Price):
            return Price.from_mil(self._price - other._price)
        else:
            return NotImplemented

    def __isub__(self, other):
        return self.__sub__(other)

    def __lt__(self, other):
        if isinstance(other, Price):
            return self._price < other._price
        else:
            return NotImplemented

    def __le__(self, other):
        if isinstance(other, Price):
            return self._price <= other._price
        else:
            return NotImplemented

    def __eq__(self, other):
        if not isinstance(other, Price):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._price == \
                   other._price

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        if isinstance(other, Price):
            return self._price > other._price
        else:
            return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Price):
            return self._price >= other._price
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self._price)
