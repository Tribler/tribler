import unittest

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionId, TransactionNumber
from Tribler.community.market.core.wallet_address import WalletAddress


class PaymentTestSuite(unittest.TestCase):
    """Payment test cases."""

    def setUp(self):
        # Object creation
        self.payment = Payment(TraderId(b"0"),
                               TransactionId(TraderId(b'2'), TransactionNumber(2)),
                               AssetAmount(3, 'BTC'),
                               WalletAddress('a'), WalletAddress('b'),
                               PaymentId('aaa'), Timestamp(4.0), True)

    def test_from_network(self):
        # Test for from network
        data = Payment.from_network(
            type('Data', (object,), {"trader_id": TraderId(b"0"),
                                     "transaction_id": TransactionId(TraderId(b'2'), TransactionNumber(2)),
                                     "transferred_assets": AssetAmount(3, 'BTC'),
                                     "address_from": WalletAddress('a'),
                                     "address_to": WalletAddress('b'),
                                     "payment_id": PaymentId('aaa'),
                                     "timestamp": Timestamp(4.0),
                                     "success": True}))

        self.assertEquals(TraderId(b"0"), data.trader_id)
        self.assertEquals(TransactionId(TraderId(b'2'), TransactionNumber(2)), data.transaction_id)
        self.assertEquals(AssetAmount(3, 'BTC'), data.transferred_assets)
        self.assertEquals(Timestamp(4.0), data.timestamp)
        self.assertTrue(data.success)

    def test_to_network(self):
        # Test for to network
        data = self.payment.to_network()

        self.assertEquals(data[0], TraderId(b"0"))
        self.assertEquals(data[1], Timestamp(4.0))
        self.assertEquals(data[2], TransactionId(TraderId(b"2"), TransactionNumber(2)))
        self.assertEquals(data[3], AssetAmount(3, 'BTC'))
        self.assertEquals(data[4], WalletAddress('a'))
        self.assertEquals(data[5], WalletAddress('b'))
        self.assertEquals(data[6], PaymentId('aaa'))
        self.assertEquals(data[7], True)

    def test_to_dictionary(self):
        """
        Test the dictionary representation of a payment
        """
        self.assertDictEqual(self.payment.to_dictionary(), {
            "trader_id": '2',
            "transaction_number": 2,
            "transferred": {
                "amount": 3,
                "type": "BTC"
            },
            "payment_id": 'aaa',
            "address_from": 'a',
            "address_to": 'b',
            "timestamp": 4.0,
            "success": True
        })
