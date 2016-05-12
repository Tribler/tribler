from decimal import Decimal


class Price(object):
    """Immutable class for representing a price."""

    def __init__(self, price):
        """
        Initialise the price

        Don't call this method directly, but use one of the factory methods: from_mil, from_float

        :param price: Integer representation of a price that is positive or zero
        :type price: int
        """
        super(Price, self).__init__()

        assert isinstance(price, int), type(price)

        if price < 0:
            raise ValueError("Price can not be negative")

        self._price = price

    @classmethod
    def from_mil(cls, mil_price):
        """
        Create a price from a mil format

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
        Create a price from a float format

        :param float_price: A float representation of a price
        :type float_price: float
        :return: The price
        :rtype: Price
        """
        price = int(Decimal(str(float_price)) * Decimal('10000'))
        return cls(price)

    def __int__(self):
        """
        Return the integer representation of the price

        :return: The string representation of the price
        :rtype: integer
        """
        return self._price

    def __str__(self):
        """
        Return the string representation of the price in mil units

        :return: The string representation of the price in mil units
        :rtype: str
        """
        return "%s" % (Decimal(str(self._price)) / Decimal('10000')).quantize(Decimal('0.0001'))

    def __add__(self, other):
        """
        Add two prices together and return a new object with that amount

        :param other: A price object to add to the current price
        :type other: Price
        :return: The new price when both prices are added
        :rtype: Price
        """
        if isinstance(other, Price):
            return Price.from_mil(self._price + other._price)
        else:
            return NotImplemented

    def __iadd__(self, other):
        """
        Add two prices together and return a new object with that amount

        :param other: A price object to add to the current price
        :type other: Price
        :return: The new price when both prices are added
        :rtype: Price
        """
        return self.__add__(other)

    def __sub__(self, other):
        """
        Subtract two prices from each other and return a new object with that amount

        :param other: A price object to subtract from the current price
        :type other: Price
        :return: The new price when the second price is subtracted from the first
        :rtype: Price
        """
        if isinstance(other, Price):
            return Price.from_mil(self._price - other._price)
        else:
            return NotImplemented

    def __isub__(self, other):
        """
        Subtract two prices from each other and return a new object with that amount

        :param other: A price object to subtract from the current price
        :type other: Price
        :return: The new price when the second price is subtracted from the first
        :rtype: Price
        """
        return self.__sub__(other)

    def __lt__(self, other):
        """
        Check if the supplied object is less than this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower, False otherwise
        :rtype: bool
        """
        if isinstance(other, Price):
            return self._price < other._price
        else:
            return NotImplemented

    def __le__(self, other):
        """
        Check if the supplied object is less than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Price):
            return self._price <= other._price
        else:
            return NotImplemented

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, Price):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._price == \
                   other._price

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __gt__(self, other):
        """
        Check if the supplied object is greater than this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger, False otherwise
        :rtype: bool
        """
        if isinstance(other, Price):
            return self._price > other._price
        else:
            return NotImplemented

    def __ge__(self, other):
        """
        Check if the supplied object is greater than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Price):
            return self._price >= other._price
        else:
            return NotImplemented

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._price)
