import unittest

from Tribler.community.market.core.quantity import Quantity


class QuantityTestSuite(unittest.TestCase):
    """Quantity test cases."""

    def test_quantity(self):
        # Object creation
        quantity = Quantity(30)
        quantity2 = Quantity.from_mil(100000)
        quantity3 = Quantity.from_mil(0)
        quantity4 = Quantity.from_float(10.0)

        # Test for init validation
        with self.assertRaises(ValueError):
            Quantity(-1)

        # Test for conversions
        self.assertEqual(30, int(quantity))
        self.assertEqual(100000, int(quantity2))
        self.assertEqual('0.0030', str(quantity))
        self.assertEqual('10.0000', str(quantity2))

        # Test for addition
        self.assertEqual(Quantity.from_mil(100030), quantity + quantity2)
        self.assertFalse(quantity is (quantity + quantity3))
        quantity += quantity3
        self.assertEqual(Quantity(30), quantity)
        self.assertEqual(NotImplemented, quantity.__add__(10))

        # Test for subtraction
        self.assertEqual(Quantity(99970), quantity2 - quantity)
        self.assertFalse(quantity is (quantity - quantity3))
        quantity -= quantity3
        self.assertEqual(Quantity(30), quantity)
        self.assertEqual(NotImplemented, quantity.__sub__(10))
        with self.assertRaises(ValueError):
            quantity - quantity2

        # Test for comparison
        self.assertTrue(quantity < quantity2)
        self.assertTrue(quantity <= quantity)
        self.assertTrue(quantity2 > quantity)
        self.assertTrue(quantity2 >= quantity2)
        self.assertEqual(NotImplemented, quantity.__lt__(10))
        self.assertEqual(NotImplemented, quantity.__le__(10))
        self.assertEqual(NotImplemented, quantity.__gt__(10))
        self.assertEqual(NotImplemented, quantity.__ge__(10))

        # Test for equality
        self.assertTrue(quantity2 == quantity4)
        self.assertTrue(quantity == quantity)
        self.assertTrue(quantity != quantity2)
        self.assertFalse(quantity == 6)

        # Test for hashes
        self.assertEqual(quantity2.__hash__(), quantity4.__hash__())
        self.assertNotEqual(quantity.__hash__(), quantity2.__hash__())


if __name__ == '__main__':
    unittest.main()