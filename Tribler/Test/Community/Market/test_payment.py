import unittest

from Tribler.community.market.core.transaction import TransactionNumber
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.bitcoin_address import BitcoinAddress
from Tribler.community.market.core.payment import Payment, MultiChainPayment, BitcoinPayment


class PaymentTestSuite(unittest.TestCase):
    """Payment test cases."""

    def setUp(self):
        # Object creation
        self.payment = Payment(MessageId(TraderId("0"), MessageNumber("1")), TransactionNumber("2"), Timestamp(4.0))

    def test_from_network(self):
        # Test for from network
        data = Payment.from_network(type('Data', (object,), {"message_id": MessageId(TraderId("0"), MessageNumber("1")),
                                                             "transaction_number": TransactionNumber('2'),
                                                             "timestamp": Timestamp(4.0)}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionNumber('2'), data.transaction_number)
        self.assertEquals(Timestamp(4.0), data.timestamp)

    def test_to_network(self):
        # Test for to network
        self.assertEquals(((), (MessageId(TraderId("0"), MessageNumber("1")), TransactionNumber('2'), Timestamp(4.0))),
                          self.payment.to_network())


class MultiChainPaymentTestSuite(unittest.TestCase):
    """Multi chain payment test cases."""

    def setUp(self):
        # Object creation
        self.multi_chain_payment = MultiChainPayment(MessageId(TraderId("0"), MessageNumber("1")),
                                                     TransactionNumber("2"),
                                                     BitcoinAddress("0"), Quantity(3), Quantity(2), Timestamp(4.0))

    def test_from_network(self):
        # Test for from network
        data = MultiChainPayment.from_network(
            type('Data', (object,), {"message_id": MessageId(TraderId("0"), MessageNumber("1")),
                                     "transaction_number": TransactionNumber('2'),
                                     "transferor_quantity": Quantity(3),
                                     "transferee_quantity": Quantity(2),
                                     "bitcoin_address": BitcoinAddress("0"),
                                     "timestamp": Timestamp(4.0)}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionNumber('2'), data.transaction_number)
        self.assertEquals(Quantity(3), data.transferor_quantity)
        self.assertEquals(Quantity(2), data.transferee_price)
        self.assertEquals("0", str(data.bitcoin_address))
        self.assertEquals(Timestamp(4.0), data.timestamp)

    def test_to_network(self):
        # Test for to network
        data = self.multi_chain_payment.to_network()

        self.assertEquals(data[1][0], MessageId(TraderId("0"), MessageNumber("1")))
        self.assertEquals(data[1][1], TransactionNumber('2'))
        self.assertEquals(str(data[1][2]), "0")
        self.assertEquals(data[1][3], Quantity(3))
        self.assertEquals(data[1][4], Quantity(2))
        self.assertEquals(data[1][5], Timestamp(4.0))


class BitcoinPaymentTestSuite(unittest.TestCase):
    """Bitcoin payment test cases."""

    def setUp(self):
        # Object creation
        self.bitcoin_payment = BitcoinPayment(MessageId(TraderId("0"), MessageNumber("1")), TransactionNumber("2"),
                                              Quantity(10),
                                              Timestamp(4.0))

    def test_from_network(self):
        # Test for from network
        data = BitcoinPayment.from_network(
            type('Data', (object,), {"message_id": MessageId(TraderId("0"), MessageNumber("1")),
                                     "transaction_number": TransactionNumber('2'),
                                     "quantity": Quantity(10),
                                     "timestamp": Timestamp(4.0)}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionNumber('2'), data.transaction_number)
        self.assertEquals(Quantity(10), data.quantity)
        self.assertEquals(Timestamp(4.0), data.timestamp)

    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            ((), (MessageId(TraderId('0'), MessageNumber('1')), TransactionNumber('2'), Quantity(10), Timestamp(4.0))),
            self.bitcoin_payment.to_network())


if __name__ == '__main__':
    unittest.main()
