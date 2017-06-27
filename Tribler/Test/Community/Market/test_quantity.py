import unittest

from Tribler.community.market.core.quantity import Quantity


class QuantityTestSuite(unittest.TestCase):
    """Quantity test cases."""

    def setUp(self):
        # Object creation
        self.quantity1 = Quantity(30, 'MC')
        self.quantity2 = Quantity(40, 'MC')
        self.quantity3 = Quantity(30, 'BTC')

    def test_init(self):
        """
        Test the initialization of a quantity
        """
        with self.assertRaises(ValueError):
            Quantity('1', 'MC')
        with self.assertRaises(ValueError):
            Quantity(1, 2)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(30, int(self.quantity1))
        self.assertEqual("40.000000 MC", str(self.quantity2))

    def test_addition(self):
        # Test for addition
        self.assertFalse(self.quantity1 is (self.quantity1 + self.quantity2))
        self.quantity1 += self.quantity2
        self.assertEqual(self.quantity1, Quantity(70, 'MC'))
        self.assertEqual(NotImplemented, self.quantity1.__add__(10))
        self.assertEqual(NotImplemented, self.quantity1.__add__(self.quantity3))

    def test_subtraction(self):
        # Test for subtraction
        self.assertEqual(Quantity(10, 'MC'), self.quantity2 - self.quantity1)
        self.assertFalse(self.quantity2 is (self.quantity1 - self.quantity1))
        self.assertEqual(NotImplemented, self.quantity1.__sub__(10))
        self.assertEqual(NotImplemented, self.quantity1.__sub__(self.quantity3))
        with self.assertRaises(ValueError):
            self.quantity1 - self.quantity2

    def test_comparison(self):
        # Test for comparison
        self.assertTrue(self.quantity1 < self.quantity2)
        self.assertTrue(self.quantity1 <= self.quantity2)
        self.assertTrue(self.quantity2 > self.quantity1)
        self.assertTrue(self.quantity2 >= self.quantity2)
        self.assertEqual(NotImplemented, self.quantity1.__lt__(10))
        self.assertEqual(NotImplemented, self.quantity1.__le__(10))
        self.assertEqual(NotImplemented, self.quantity1.__gt__(10))
        self.assertEqual(NotImplemented, self.quantity1.__ge__(10))
        self.assertEqual(NotImplemented, self.quantity1.__lt__(self.quantity3))
        self.assertEqual(NotImplemented, self.quantity1.__le__(self.quantity3))
        self.assertEqual(NotImplemented, self.quantity1.__gt__(self.quantity3))
        self.assertEqual(NotImplemented, self.quantity1.__ge__(self.quantity3))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.quantity1 == self.quantity1)
        self.assertNotEqual(self.quantity1, self.quantity2)
        self.assertFalse(self.quantity1 == 6)
        self.assertFalse(self.quantity1 == self.quantity3)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.quantity1.__hash__(), Quantity(30, 'MC').__hash__())
        self.assertNotEqual(self.quantity1.__hash__(), self.quantity2.__hash__())
