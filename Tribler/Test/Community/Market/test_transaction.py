import unittest

from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction, EndTransaction,\
    StartTransaction
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.trade import Trade


class TransactionNumberTestSuite(unittest.TestCase):
    """Message number test cases."""

    def setUp(self):
        # Object creation
        self.transaction_number = TransactionNumber('message_number')
        self.transaction_number2 = TransactionNumber('message_number')
        self.transaction_number3 = TransactionNumber('message_number_2')

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('message_number', str(self.transaction_number))

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            TransactionNumber(1.0)

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.transaction_number == self.transaction_number2)
        self.assertTrue(self.transaction_number == self.transaction_number)
        self.assertTrue(self.transaction_number != self.transaction_number3)
        self.assertFalse(self.transaction_number == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.transaction_number.__hash__(), self.transaction_number2.__hash__())
        self.assertNotEqual(self.transaction_number.__hash__(), self.transaction_number3.__hash__())


class TransactionIdTestSuite(unittest.TestCase):
    """Transaction ID test cases."""

    def setUp(self):
        # Object creation
        self.transaction_id = TransactionId(TraderId('0'), TransactionNumber('1'))
        self.transaction_id2 = TransactionId(TraderId('0'), TransactionNumber('1'))
        self.transaction_id3 = TransactionId(TraderId('0'), TransactionNumber('2'))

    def test_properties(self):
        # Test for properties
        self.assertEqual(TraderId('0'), self.transaction_id.trader_id)
        self.assertEqual(TransactionNumber('1'), self.transaction_id.transaction_number)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('0.1', str(self.transaction_id))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.transaction_id == self.transaction_id2)
        self.assertTrue(self.transaction_id == self.transaction_id)
        self.assertTrue(self.transaction_id != self.transaction_id3)
        self.assertFalse(self.transaction_id == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.transaction_id.__hash__(), self.transaction_id2.__hash__())
        self.assertNotEqual(self.transaction_id.__hash__(), self.transaction_id3.__hash__())


class TransactionTestSuite(unittest.TestCase):
    """Transaction test cases."""

    def setUp(self):
        # Object creation
        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber("1"))
        self.transaction = Transaction(self.transaction_id, Price(100), Quantity(30), Timeout(float("inf")), Timestamp(0.0))
        proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('1')),
                                       OrderId(TraderId('0'), OrderNumber('2')),
                                       OrderId(TraderId('1'), OrderNumber('3')),
                                       Price(100), Quantity(30), Timestamp(0.0))
        self.accepted_trade = Trade.accept(MessageId(TraderId('0'), MessageNumber('1')),
                                           Timestamp(0.0), proposed_trade)

    def test_from_accepted_trade(self):
        # Test from accepted trade
        transaction = Transaction.from_accepted_trade(self.accepted_trade, self.transaction_id)
        self.assertEqual(transaction.price, self.transaction.price)
        self.assertEqual(transaction.total_quantity, self.transaction.total_quantity)
        self.assertEqual(float(transaction.timeout), float(self.transaction.timeout))
        self.assertEqual(transaction.timestamp, self.transaction.timestamp)


class StartTransactionTestSuite(unittest.TestCase):
    """Start transaction test cases."""

    def setUp(self):
        # Object creation
        self.start_transaction = StartTransaction(MessageId(TraderId('0'), MessageNumber('1')),
                                                  TransactionId(TraderId("0"), TransactionNumber("1")), Timestamp(0.0))

    def test_from_network(self):
        # Test for from network
        data = StartTransaction.from_network(
            type('Data', (object,), {"message_id": MessageId(TraderId("0"), MessageNumber("1")),
                                     "transaction_id": TransactionId(TraderId("0"), TransactionNumber("1")),
                                     "timestamp": Timestamp(0.0)}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionId(TraderId("0"), TransactionNumber("1")), data.transaction_id)
        self.assertEquals(Timestamp(0.0), data.timestamp)

    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            ((), (MessageId(TraderId('0'), MessageNumber('1')), TransactionId(TraderId("0"), TransactionNumber("1")),
                  Timestamp(0.0))),
            self.start_transaction.to_network())


class EndTransactionTestSuite(unittest.TestCase):
    """End transaction test cases."""

    def setUp(self):
        # Object creation
        self.end_transaction = EndTransaction(MessageId(TraderId('0'), MessageNumber('1')),
                                              TransactionId(TraderId("0"), TransactionNumber("1")), Timestamp(0.0))

    def test_from_network(self):
        # Test for from network
        data = EndTransaction.from_network(
            type('Data', (object,), {"message_id": MessageId(TraderId("0"), MessageNumber("1")),
                                     "transaction_id": TransactionId(TraderId("0"), TransactionNumber("1")),
                                     "timestamp": Timestamp(0.0)}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionId(TraderId("0"), TransactionNumber("1")), data.transaction_id)
        self.assertEquals(Timestamp(0.0), data.timestamp)

    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            ((), (MessageId(TraderId('0'), MessageNumber('1')), TransactionId(TraderId("0"), TransactionNumber("1")),
                  Timestamp(0.0))),
            self.end_transaction.to_network())
