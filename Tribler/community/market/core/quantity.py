from decimal import Decimal


class Quantity(object):
    """Immutable class for representing quantity."""

    def __init__(self, quantity):
        """
        Initialise the quantity

        Don't call this method directly, but use one of the factory methods: from_mil, from_float

        :param quantity: Integer representation of a quantity that is positive or zero
        :type quantity: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Quantity, self).__init__()

        assert isinstance(quantity, int), type(quantity)

        if not isinstance(quantity, int):
            raise ValueError("Quantity must be an int")

        if quantity < 0:
            raise ValueError("Quantity must be positive or zero")

        self._quantity = quantity

    @classmethod
    def from_mil(cls, mil_quantity):
        """
        Create a quantity from a mil format

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
        Create a quantity from a float format

        :param float_quantity: A float representation of a quantity
        :type float_quantity: float
        :return: The quantity
        :rtype: Quantity
        """
        quantity = int(Decimal(str(float_quantity)) * Decimal('10000'))
        return cls(quantity)

    def __int__(self):
        """
        Return the integer representation of the quantity

        :return: The integer representation of the quantity
        :rtype: integer
        """
        return self._quantity

    def __str__(self):
        """
        Return the string representation of the quantity in mil units

        :return: The string representation of the quantity in mil units
        :rtype: str
        """
        return "%s" % (Decimal(str(self._quantity)) / Decimal('10000')).quantize(Decimal('0.0001'))

    def __add__(self, other):
        """
        Add two quantities together and return a new object with that amount

        :param other: A quantity object to add to the current quantity
        :type other: Quantity
        :return: The new quantity when both quantities are added
        :rtype: Quantity
        """
        if isinstance(other, Quantity):
            return Quantity.from_mil(self._quantity + other._quantity)
        else:
            return NotImplemented

    def __iadd__(self, other):
        """
        Add two quantities together and return a new object with that amount

        :param other: A quantity object to add to the current quantity
        :type other: Quantity
        :return: The new quantity when both quantities are added
        :rtype: Quantity
        """
        return self.__add__(other)

    def __sub__(self, other):
        """
        Subtract two quantities from each other and return a new object with that amount

        :param other: A quantity object to subtract from the current quantity
        :type other: Quantity
        :return: The new quantity when the second quantity is subtracted from the first
        :rtype: Quantity
        """
        if isinstance(other, Quantity):
            return Quantity.from_mil(self._quantity - other._quantity)
        else:
            return NotImplemented

    def __isub__(self, other):
        """
        Subtract two quantities from each other and return a new object with that amount

        :param other: A quantity object to subtract from the current quantity
        :type other: Quantity
        :return: The new quantity when the second quantity is subtracted from the first
        :rtype: Quantity
        """
        return self.__sub__(other)

    def __lt__(self, other):
        """
        Check if the supplied object is less than this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower, False otherwise
        :rtype: bool
        """
        if isinstance(other, Quantity):
            return self._quantity < other._quantity
        else:
            return NotImplemented

    def __le__(self, other):
        """
        Check if the supplied object is less than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Quantity):
            return self._quantity <= other._quantity
        else:
            return NotImplemented

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, Quantity):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._quantity == \
                   other._quantity

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
        if isinstance(other, Quantity):
            return self._quantity > other._quantity
        else:
            return NotImplemented

    def __ge__(self, other):
        """
        Check if the supplied object is greater than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Quantity):
            return self._quantity >= other._quantity
        else:
            return NotImplemented

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._quantity)
