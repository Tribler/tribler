import unittest

from Tribler.community.market.core.quantity import Quantity


class QuantityTestSuite(unittest.TestCase):
    """Quantity test cases."""

    def setUp(self):
        # Object creation
        self.quantity = Quantity(30)
        self.quantity2 = Quantity.from_mil(100000)
        self.quantity3 = Quantity.from_mil(0)
        self.quantity4 = Quantity.from_float(10.0)

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            Quantity(-1)
        with self.assertRaises(ValueError):
            Quantity(1.0)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(30, int(self.quantity))
        self.assertEqual(100000, int(self.quantity2))
        self.assertEqual('0.0030', str(self.quantity))
        self.assertEqual('10.0000', str(self.quantity2))

    def test_addition(self):
        # Test for addition
        self.assertEqual(Quantity.from_mil(100030), self.quantity + self.quantity2)
        self.assertFalse(self.quantity is (self.quantity + self.quantity3))
        self.quantity += self.quantity3
        self.assertEqual(Quantity(30), self.quantity)
        self.assertEqual(NotImplemented, self.quantity.__add__(10))

    def test_subtraction(self):
        # Test for subtraction
        self.assertEqual(Quantity(99970), self.quantity2 - self.quantity)
        self.assertFalse(self.quantity is (self.quantity - self.quantity3))
        self.quantity -= self.quantity3
        self.assertEqual(Quantity(30), self.quantity)
        self.assertEqual(NotImplemented, self.quantity.__sub__(10))
        with self.assertRaises(ValueError):
            self.quantity - self.quantity2

    def test_comparison(self):
        # Test for comparison
        self.assertTrue(self.quantity < self.quantity2)
        self.assertTrue(self.quantity <= self.quantity)
        self.assertTrue(self.quantity2 > self.quantity)
        self.assertTrue(self.quantity2 >= self.quantity2)
        self.assertEqual(NotImplemented, self.quantity.__lt__(10))
        self.assertEqual(NotImplemented, self.quantity.__le__(10))
        self.assertEqual(NotImplemented, self.quantity.__gt__(10))
        self.assertEqual(NotImplemented, self.quantity.__ge__(10))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.quantity2 == self.quantity4)
        self.assertTrue(self.quantity == self.quantity)
        self.assertTrue(self.quantity != self.quantity2)
        self.assertFalse(self.quantity == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.quantity2.__hash__(), self.quantity4.__hash__())
        self.assertNotEqual(self.quantity.__hash__(), self.quantity2.__hash__())


if __name__ == '__main__':
    unittest.main()
