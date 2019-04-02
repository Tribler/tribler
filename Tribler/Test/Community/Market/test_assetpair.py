import unittest

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair


class TestAssetPair(unittest.TestCase):
    """
    Test the asset pair class
    """

    def setUp(self):
        # Object creation
        self.assetpair1 = AssetPair(AssetAmount(2, 'BTC'), AssetAmount(2, 'MB'))
        self.assetpair2 = AssetPair(AssetAmount(4, 'BTC'), AssetAmount(2, 'MB'))
        self.assetpair3 = AssetPair(AssetAmount(2, 'BTC'), AssetAmount(2, 'MB'))

    def test_init(self):
        """
        Test initializing an AssetPair object
        """
        with self.assertRaises(ValueError):
            AssetPair(AssetAmount(2, 'MB'), AssetAmount(2, 'BTC'))

    def test_equality(self):
        """
        Test the equality method of an AssetPair
        """
        self.assertFalse(self.assetpair1 == self.assetpair2)
        self.assertTrue(self.assetpair1 == self.assetpair3)

    def test_to_dictionary(self):
        """
        Test the method to convert an AssetPair object to a dictionary
        """
        self.assertDictEqual({
            "first": {
                "amount": 2,
                "type": "BTC",
            },
            "second": {
                "amount": 2,
                "type": "MB"
            }
        }, self.assetpair1.to_dictionary())

    def test_from_dictionary(self):
        """
        Test the method to create an AssetPair object from a given dictionary
        """
        self.assertEqual(AssetPair.from_dictionary({
            "first": {
                "amount": 2,
                "type": "BTC",
            },
            "second": {
                "amount": 2,
                "type": "MB"
            }
        }), self.assetpair1)

    def test_price(self):
        """
        Test creating a price from an asset pair
        """
        self.assertEqual(self.assetpair1.price.amount, 1)
        self.assertEqual(self.assetpair2.price.amount, 0.5)

    def test_proportional_downscale(self):
        """
        Test the method to proportionally scale down an asset pair
        """
        self.assertEqual(self.assetpair2.proportional_downscale(2).second.amount, 1)

    def test_to_str(self):
        """
        Test string conversion from an asset pair
        """
        self.assertEqual("2 BTC 2 MB", str(self.assetpair1))
