from decimal import Decimal


class Quantity(object):
    """Quantity is used for having a consistent comparable and usable class that deals with mils and floats."""

    def __init__(self, quantity):
        """
        Don't call this method directly, use one of the factory methods: from_mil, from_float

        :param quantity: Integer representation of a quantity that is positive or zero
        :type quantity: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Quantity, self).__init__()

        if not isinstance(quantity, int):
            raise ValueError("Quantity must be an int")

        if quantity < 0:
            raise ValueError("Quantity must be positive or zero")

        self._quantity = quantity

    @classmethod
    def from_mil(cls, mil_quantity):
        """
        A mil is 0.0001 of a quantity unit

        :param mil_quantity: A mil quantity (mil = 0.0001)
        :type mil_quantity: int
        :return: The quantity
        :rtype: Quantity
        """
        return cls(mil_quantity)

    @classmethod
    def from_float(cls, float_quantity):
        """
        :param float_quantity: A float representation of a quantity
        :type float_quantity: float
        :return: The quantity
        :rtype: Quantity
        """
        quantity = int(Decimal(str(float_quantity)) * Decimal('10000'))
        return cls(quantity)

    def __int__(self):
        return self._quantity

    def __str__(self):
        return "%s" % (Decimal(str(self._quantity)) / Decimal('10000')).quantize(Decimal('0.0001'))

    def __add__(self, other):
        if isinstance(other, Quantity):
            return Quantity.from_mil(self._quantity + other._quantity)
        else:
            return NotImplemented

    def __iadd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, Quantity):
            return Quantity.from_mil(self._quantity - other._quantity)
        else:
            return NotImplemented

    def __isub__(self, other):
        return self.__sub__(other)

    def __lt__(self, other):
        if isinstance(other, Quantity):
            return self._quantity < other._quantity
        else:
            return NotImplemented

    def __le__(self, other):
        if isinstance(other, Quantity):
            return self._quantity <= other._quantity
        else:
            return NotImplemented

    def __eq__(self, other):
        if not isinstance(other, Quantity):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._quantity == \
                   other._quantity

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        if isinstance(other, Quantity):
            return self._quantity > other._quantity
        else:
            return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Quantity):
            return self._quantity >= other._quantity
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self._quantity)
