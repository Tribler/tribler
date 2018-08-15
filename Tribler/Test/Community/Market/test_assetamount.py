import unittest

from Tribler.community.market.core.assetamount import AssetAmount


class TestAssetAmount(unittest.TestCase):
    """
    Test the asset amount class
    """

    def setUp(self):
        # Object creation
        self.assetamount1 = AssetAmount(2, 'BTC')
        self.assetamount2 = AssetAmount(100, 'BTC')
        self.assetamount3 = AssetAmount(0, 'BTC')
        self.assetamount4 = AssetAmount(2, 'MC')

    def test_init(self):
        """
        Test the initialization of a price
        """
        with self.assertRaises(ValueError):
            AssetAmount('1', 'MC')
        with self.assertRaises(ValueError):
            AssetAmount(1, 2)

    def test_addition(self):
        # Test for addition
        self.assertEqual(AssetAmount(102, 'BTC'), self.assetamount1 + self.assetamount2)
        self.assertFalse(self.assetamount1 is (self.assetamount1 + self.assetamount2))
        self.assertEqual(NotImplemented, self.assetamount1.__add__(10))
        self.assertEqual(NotImplemented, self.assetamount1.__add__(self.assetamount4))

    def test_subtraction(self):
        # Test for subtraction
        self.assertEqual(AssetAmount(98, 'BTC'), self.assetamount2 - self.assetamount1)
        self.assertEqual(NotImplemented, self.assetamount1.__sub__(10))
        self.assertEqual(NotImplemented, self.assetamount1.__sub__(self.assetamount4))

    def test_comparison(self):
        # Test for comparison
        self.assertTrue(self.assetamount1 < self.assetamount2)
        self.assertTrue(self.assetamount2 > self.assetamount1)
        self.assertEqual(NotImplemented, self.assetamount1.__le__(10))
        self.assertEqual(NotImplemented, self.assetamount1.__lt__(10))
        self.assertEqual(NotImplemented, self.assetamount1.__ge__(10))
        self.assertEqual(NotImplemented, self.assetamount1.__gt__(10))
        self.assertEqual(NotImplemented, self.assetamount1.__le__(self.assetamount4))
        self.assertEqual(NotImplemented, self.assetamount1.__lt__(self.assetamount4))
        self.assertEqual(NotImplemented, self.assetamount1.__ge__(self.assetamount4))
        self.assertEqual(NotImplemented, self.assetamount1.__gt__(self.assetamount4))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.assetamount1 == AssetAmount(2, 'BTC'))
        self.assertTrue(self.assetamount1 != self.assetamount2)
        self.assertFalse(self.assetamount1 == 2)
        self.assertFalse(self.assetamount1 == self.assetamount4)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.assetamount1.__hash__(), AssetAmount(2, 'BTC').__hash__())
        self.assertNotEqual(self.assetamount1.__hash__(), self.assetamount2.__hash__())

    def test_str(self):
        """
        Test the string representation of a Price object
        """
        self.assertEqual(str(self.assetamount1), "2 BTC")
