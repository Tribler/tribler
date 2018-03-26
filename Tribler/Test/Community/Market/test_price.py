import unittest

from Tribler.community.market.core.price import Price


class PriceTestSuite(unittest.TestCase):
    """Price test cases."""

    def setUp(self):
        # Object creation
        self.price1 = Price(2.3, 'BTC')
        self.price2 = Price(100, 'BTC')
        self.price3 = Price(0, 'BTC')
        self.price4 = Price(2.3, 'MC')

    def test_init(self):
        """
        Test the initialization of a price
        """
        with self.assertRaises(ValueError):
            Price('1', 'MC')
        with self.assertRaises(ValueError):
            Price(1, 2)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(100, int(self.price2))
        self.assertEqual(float('2.3'), self.price1.__float__())

    def test_addition(self):
        # Test for addition
        self.assertEqual(Price(102.3, 'BTC'), self.price1 + self.price2)
        self.assertFalse(self.price1 is (self.price1 + self.price2))
        self.assertEqual(NotImplemented, self.price1.__add__(10))
        self.assertEqual(NotImplemented, self.price1.__add__(self.price4))

    def test_subtraction(self):
        # Test for subtraction
        self.assertEqual(Price(97.7, 'BTC'), self.price2 - self.price1)
        self.assertFalse(self.price2 is (self.price2 - self.price2))
        self.assertEqual(NotImplemented, self.price1.__sub__(10))
        self.assertEqual(NotImplemented, self.price1.__sub__(self.price4))
        with self.assertRaises(ValueError):
            self.price1 - self.price2

    def test_comparison(self):
        # Test for comparison
        self.assertTrue(self.price1 < self.price2)
        self.assertTrue(self.price1 <= self.price1)
        self.assertTrue(self.price2 > self.price1)
        self.assertTrue(self.price3 >= self.price3)
        self.assertEqual(NotImplemented, self.price1.__le__(10))
        self.assertEqual(NotImplemented, self.price1.__lt__(10))
        self.assertEqual(NotImplemented, self.price1.__ge__(10))
        self.assertEqual(NotImplemented, self.price1.__gt__(10))
        self.assertEqual(NotImplemented, self.price1.__le__(self.price4))
        self.assertEqual(NotImplemented, self.price1.__lt__(self.price4))
        self.assertEqual(NotImplemented, self.price1.__ge__(self.price4))
        self.assertEqual(NotImplemented, self.price1.__gt__(self.price4))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.price1 == Price(2.3, 'BTC'))
        self.assertTrue(self.price1 != self.price2)
        self.assertFalse(self.price1 == 2.3)
        self.assertFalse(self.price1 == self.price4)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.price1.__hash__(), Price(2.3, 'BTC').__hash__())
        self.assertNotEqual(self.price1.__hash__(), self.price2.__hash__())

    def test_str(self):
        """
        Test the string representation of a Price object
        """
        self.assertEqual(str(self.price1), "2.300000 BTC")
