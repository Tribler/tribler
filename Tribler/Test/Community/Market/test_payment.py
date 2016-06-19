import unittest

from Tribler.community.market.core.transaction import TransactionNumber, TransactionId
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.bitcoin_address import BitcoinAddress
from Tribler.community.market.core.payment import MultiChainPayment, BitcoinPayment


class MultiChainPaymentTestSuite(unittest.TestCase):
    """Multi chain payment test cases."""

    def setUp(self):
        # Object creation
        self.multi_chain_payment = MultiChainPayment(MessageId(TraderId("0"), MessageNumber("1")),
                                                     TransactionId(TraderId('2'), TransactionNumber("2")),
                                                     BitcoinAddress("0"), Quantity(3), Price(2), Timestamp(4.0))

    def test_from_network(self):
        # Test for from network
        data = MultiChainPayment.from_network(
            type('Data', (object,), {"trader_id": TraderId("0"),
                                     "message_number": MessageNumber("1"),
                                     "transaction_trader_id": TraderId('2'),
                                     "transaction_number": TransactionNumber('2'),
                                     "transferor_quantity": Quantity(3),
                                     "transferee_price": Price(2),
                                     "bitcoin_address": BitcoinAddress("0"),
                                     "timestamp": Timestamp(4.0)}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionId(TraderId('2'), TransactionNumber("2")), data.transaction_id)
        self.assertEquals(Quantity(3), data.transferor_quantity)
        self.assertEquals(Price(2), data.transferee_price)
        self.assertEquals("0", str(data.bitcoin_address))
        self.assertEquals(Timestamp(4.0), data.timestamp)

    def test_to_network(self):
        # Test for to network
        data = self.multi_chain_payment.to_network()

        self.assertEquals(data[1][0], TraderId("0"))
        self.assertEquals(data[1][1], MessageNumber("1"))
        self.assertEquals(data[1][2], TraderId("2"))
        self.assertEquals(data[1][3], TransactionNumber('2'))
        self.assertEquals(str(data[1][4]), "0")
        self.assertEquals(data[1][5], Quantity(3))
        self.assertEquals(data[1][6], Price(2))
        self.assertEquals(data[1][7], Timestamp(4.0))


class BitcoinPaymentTestSuite(unittest.TestCase):
    """Bitcoin payment test cases."""

    def setUp(self):
        # Object creation
        self.bitcoin_payment = BitcoinPayment(MessageId(TraderId("0"), MessageNumber("1")),
                                              TransactionId(TraderId('2'), TransactionNumber("2")),
                                              BitcoinAddress('1'),
                                              Price(10),
                                              Timestamp(4.0))

    def test_from_network(self):
        # Test for from network
        data = BitcoinPayment.from_network(
            type('Data', (object,), {"message_number": MessageNumber("1"),
                                     "trader_id": TraderId('0'),
                                     "transaction_trader_id": TraderId('2'),
                                     "transaction_number": TransactionNumber('2'),
                                     "bitcoin_address": BitcoinAddress('1'),
                                     "price": Price(10),
                                     "timestamp": Timestamp(4.0)}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionId(TraderId('2'), TransactionNumber("2")), data.transaction_id)
        self.assertEquals(Price(10), data.price)
        self.assertEquals(Timestamp(4.0), data.timestamp)

    def test_to_network(self):
        # Test for to network
        data = self.bitcoin_payment.to_network()

        self.assertEquals(data[1][0], TraderId("0"))
        self.assertEquals(data[1][1], MessageNumber("1"))
        self.assertEquals(data[1][2], TraderId("2"))
        self.assertEquals(data[1][3], TransactionNumber('2'))
        self.assertEquals(str(data[1][4]), '1')
        self.assertEquals(data[1][5], Price(10))
        self.assertEquals(data[1][6], Timestamp(4.0))


if __name__ == '__main__':
    unittest.main()
