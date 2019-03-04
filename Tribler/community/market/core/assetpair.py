# pylint: disable=long-builtin,redefined-builtin

from __future__ import absolute_import

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.price import Price

try:
    long
except NameError:
    long = int


class AssetPair(object):
    """
    An asset pair represents a pair of specific amounts of assets, i.e. 10 BTC - 20 MB.
    It is used when dealing with orders in the market.
    """

    def __init__(self, first, second):
        if first.asset_id > second.asset_id:
            raise ValueError("Asset %s must be smaller than %s" % (first, second))

        self.first = first
        self.second = second

    def __eq__(self, other):
        if not isinstance(other, AssetPair):
            return NotImplemented
        else:
            return self.first == other.first and self.second == other.second

    def to_dictionary(self):
        return {
            "first": self.first.to_dictionary(),
            "second": self.second.to_dictionary()
        }

    @classmethod
    def from_dictionary(cls, dictionary):
        return cls(AssetAmount(dictionary["first"]["amount"], dictionary["first"]["type"]),
                   AssetAmount(dictionary["second"]["amount"], dictionary["second"]["type"]))

    @property
    def price(self):
        """
        Return a Price object of this asset pair, which expresses the second asset into the first asset.
        """
        return Price(float(self.second.amount) / float(self.first.amount), self.second.asset_id, self.first.asset_id)

    def proportional_downscale(self, new_amount):
        """
        This method constructs a new AssetPair where the ratio between the first/second asset is preserved.
        One should specify a new amount for the first asset.
        For instance, if we have an asset pair (4 BTC, 8 MB), the price is 8/4 = 2 MB/BTC.
        If we now change the amount of the first asset from 4 BTC to 1 BTC, the new AssetPair becomes (1 BTC, 2 MB).
        """
        return AssetPair(AssetAmount(new_amount, self.first.asset_id),
                         AssetAmount(long(self.price.amount * new_amount), self.second.asset_id))

    def __str__(self):
        return "%s %s" % (self.first, self.second)
