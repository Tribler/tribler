import unittest

from Tribler.community.market.core.transaction import TransactionNumber, TransactionId
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.wallet_address import WalletAddress


class PaymentTestSuite(unittest.TestCase):
    """Payment test cases."""

    def setUp(self):
        # Object creation
        self.payment = Payment(MessageId(TraderId("0"), MessageNumber("1")),
                               TransactionId(TraderId('2'), TransactionNumber(2)),
                               Quantity(3, 'MC'), Price(2, 'BTC'),
                               WalletAddress('a'), WalletAddress('b'),
                               PaymentId('aaa'), Timestamp(4.0), True)

    def test_from_network(self):
        # Test for from network
        data = Payment.from_network(
            type('Data', (object,), {"trader_id": TraderId("0"),
                                     "message_number": MessageNumber("1"),
                                     "transaction_trader_id": TraderId('2'),
                                     "transaction_number": TransactionNumber(2),
                                     "transferee_quantity": Quantity(3, 'MC'),
                                     "transferee_price": Price(2, 'BTC'),
                                     "address_from": WalletAddress('a'),
                                     "address_to": WalletAddress('b'),
                                     "payment_id": PaymentId('aaa'),
                                     "timestamp": Timestamp(4.0),
                                     "success": True}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionId(TraderId('2'), TransactionNumber(2)), data.transaction_id)
        self.assertEquals(Quantity(3, 'MC'), data.transferee_quantity)
        self.assertEquals(Price(2, 'BTC'), data.transferee_price)
        self.assertEquals(Timestamp(4.0), data.timestamp)
        self.assertTrue(data.success)

    def test_to_network(self):
        # Test for to network
        data = self.payment.to_network()

        self.assertEquals(data[0], TraderId("0"))
        self.assertEquals(data[1], MessageNumber("1"))
        self.assertEquals(data[2], TraderId("2"))
        self.assertEquals(data[3], TransactionNumber(2))
        self.assertEquals(data[4], Quantity(3, 'MC'))
        self.assertEquals(data[5], Price(2, 'BTC'))
        self.assertEquals(data[6], WalletAddress('a'))
        self.assertEquals(data[7], WalletAddress('b'))
        self.assertEquals(data[8], PaymentId('aaa'))
        self.assertEquals(data[9], Timestamp(4.0))
        self.assertEquals(data[10], True)

    def test_to_dictionary(self):
        """
        Test the dictionary representation of a payment
        """
        self.assertDictEqual(self.payment.to_dictionary(), {
            "trader_id": '2',
            "transaction_number": 2,
            "price": 2.0,
            "price_type": 'BTC',
            "quantity": 3.0,
            "quantity_type": 'MC',
            "payment_id": 'aaa',
            "address_from": 'a',
            "address_to": 'b',
            "timestamp": 4.0,
            "success": True
        })
