class Price(object):
    """
    This class represents a price in the market.
    The price is simply a fraction that expresses one asset in another asset.
    For instance, 0.5 MB/BTC means that one exchanges 0.5 MB for 1 BTC.
    """

    def __init__(self, amount, numerator, denominator):
        self.amount = amount
        self.numerator = numerator
        self.denominator = denominator

    def __str__(self):
        return "%g %s/%s" % (self.amount, self.numerator, self.denominator)

    def __lt__(self, other):
        if isinstance(other, Price) and self.numerator == other.numerator and self.denominator == other.denominator:
            return self.amount < other.amount
        else:
            return NotImplemented

    def __le__(self, other):
        if isinstance(other, Price) and self.numerator == other.numerator and self.denominator == other.denominator:
            return self.amount <= other.amount
        else:
            return NotImplemented

    def __ne__(self, other):
        if not isinstance(other, Price) or self.numerator != other.numerator or self.denominator != other.denominator:
            return NotImplemented
        return not self.__eq__(other)

    def __gt__(self, other):
        if isinstance(other, Price) and self.numerator == other.numerator and self.denominator == other.denominator:
            return self.amount > other.amount
        else:
            return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Price) and self.numerator == other.numerator and self.denominator == other.denominator:
            return self.amount >= other.amount
        else:
            return NotImplemented

    def __eq__(self, other):
        if not isinstance(other, Price) or self.numerator != other.numerator or self.denominator != other.denominator:
            return NotImplemented
        else:
            rel_tol = 1e-09
            abs_tol = 0.0
            return abs(self.amount - other.amount) <= max(rel_tol * max(abs(self.amount), abs(other.amount)), abs_tol)

    def __hash__(self):
        return hash((self.amount, self.numerator, self.denominator))
