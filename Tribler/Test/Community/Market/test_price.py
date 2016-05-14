import unittest

from Tribler.community.market.core.price import Price


class PriceTestSuite(unittest.TestCase):
    """Price test cases."""

    def test_price(self):
        # Object creation
        price = Price(63400)
        price2 = Price.from_float(6.34)
        price3 = Price.from_mil(63400)
        price4 = Price.from_float(18.3)
        price5 = Price(0)

        # Test for init validation
        with self.assertRaises(ValueError):
            Price(-1)

        # Test for conversions
        self.assertEqual(63400, int(price))
        self.assertEqual(63400, int(price2))
        self.assertEqual('6.3400', str(price))
        self.assertEqual('6.3400', str(price2))

        # Test for addition
        self.assertEqual(Price.from_float(24.64), price2 + price4)
        self.assertFalse(price4 is (price4 + price))
        price3 += price5
        self.assertEqual(Price.from_float(6.34), price3)
        self.assertEqual(NotImplemented, price.__add__(10))

        # Test for subtraction
        self.assertEqual(Price.from_float(11.96), price4 - price2)
        self.assertFalse(price is (price - price))
        price3 -= price5
        self.assertEqual(Price.from_float(6.34), price3)
        self.assertEqual(NotImplemented, price.__sub__(10))
        with self.assertRaises(ValueError):
            price - price4

        # Test for comparison
        self.assertTrue(price2 < price4)
        self.assertTrue(price4 <= price4)
        self.assertTrue(price4 > price2)
        self.assertTrue(price4 >= price4)
        self.assertEqual(NotImplemented, price.__le__(10))
        self.assertEqual(NotImplemented, price.__lt__(10))
        self.assertEqual(NotImplemented, price.__ge__(10))
        self.assertEqual(NotImplemented, price.__gt__(10))

        # Test for equality
        self.assertTrue(price == price3)
        self.assertTrue(price == price)
        self.assertTrue(price != price4)
        self.assertFalse(price == 6)

        # Test for hashes
        self.assertEqual(price.__hash__(), price3.__hash__())
        self.assertNotEqual(price.__hash__(), price4.__hash__())


if __name__ == '__main__':
    unittest.main()