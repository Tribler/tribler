import unittest

from Tribler.community.market.core.transaction_repository import TransactionRepository, MemoryTransactionRepository
from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction
from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.bitcoin_address import BitcoinAddress
from Tribler.community.market.core.payment import Payment, MultiChainPayment, BitcoinPayment


class PaymentTestSuite(unittest.TestCase):
    """Payment test cases."""

    def setUp(self):
        # Object creation
        self.payment = Payment(TraderId("0"), MessageNumber("1"), TransactionNumber("3"), Timestamp(4.0))

    def test_init(self):
        self.assertIsInstance(self.payment, Payment)


class MultiChainPaymentTestSuite(unittest.TestCase):
    """Multi chain payment test cases."""

    def setUp(self):
        # Object creation
        self.multi_chain_payment = MultiChainPayment(TraderId("0"), MessageNumber("1"), TransactionNumber("3"),
                                                     BitcoinAddress("0"), Quantity(3), Quantity(2), Timestamp(4.0))

    def test_init(self):
        self.assertIsInstance(self.multi_chain_payment, MultiChainPayment)


class BitcoinPaymentTestSuite(unittest.TestCase):
    """Bitcoin payment test cases."""

    def setUp(self):
        # Object creation
        self.bitcoin_payment = BitcoinPayment(TraderId("0"), MessageNumber("1"), TransactionNumber("3"), Quantity(10),
                                              Timestamp(4.0))

    def test_init(self):
        self.assertIsInstance(self.bitcoin_payment, BitcoinPayment)


if __name__ == '__main__':
    unittest.main()
