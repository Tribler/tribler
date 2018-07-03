import unittest

from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.timeout import Timestamp
from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction, StartTransaction
from Tribler.community.market.core.transaction_repository import MemoryTransactionRepository
from Tribler.community.market.core.transaction_manager import TransactionManager
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.core.wallet_address import WalletAddress


class TransactionManagerTestSuite(unittest.TestCase):
    """Transaction manager test cases."""

    def setUp(self):
        # Object creation
        self.memory_transaction_repository = MemoryTransactionRepository("0")
        self.transaction_manager = TransactionManager(self.memory_transaction_repository)

        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber(1))
        self.transaction = Transaction(self.transaction_id, Price(100, 'BTC'), Quantity(30, 'MC'),
                                       OrderId(TraderId('3'), OrderNumber(2)),
                                       OrderId(TraderId('2'), OrderNumber(1)), Timestamp(0.0))
        self.proposed_trade = Trade.propose(TraderId('0'),
                                            OrderId(TraderId('0'), OrderNumber(1)),
                                            OrderId(TraderId('1'), OrderNumber(2)),
                                            Price(63400, 'BTC'), Quantity(30, 'MC'), Timestamp(1462224447.117))
        self.start_transaction = StartTransaction(TraderId('0'),
                                                  TransactionId(TraderId("0"), TransactionNumber(1)),
                                                  OrderId(TraderId('0'), OrderNumber(1)),
                                                  OrderId(TraderId('1'), OrderNumber(2)), 1235,
                                                  Price(3600, 'BTC'), Quantity(20, 'MC'), Timestamp(0.0))

    def test_create_from_proposed_trade(self):
        # Test for create from a proposed trade
        transaction = self.transaction_manager.create_from_proposed_trade(self.proposed_trade, 'a')
        self.assertEquals(transaction, self.transaction_manager.find_by_id(transaction.transaction_id))

    def test_find_by_id(self):
        # Test for find by id
        self.assertEquals(None, self.transaction_manager.find_by_id(self.transaction_id))
        self.memory_transaction_repository.add(self.transaction)
        self.assertEquals(self.transaction, self.transaction_manager.find_by_id(self.transaction_id))

    def test_find_all(self):
        # Test for find all
        self.assertEquals([], self.transaction_manager.find_all())
        self.memory_transaction_repository.add(self.transaction)
        self.assertEquals([self.transaction], self.transaction_manager.find_all())

    def test_create_from_start_transaction(self):
        # Test for create from start transaction
        transaction = self.transaction_manager.create_from_start_transaction(self.start_transaction, 'a')
        self.assertEquals(transaction, self.transaction_manager.find_by_id(transaction.transaction_id))

    def test_create_payment_message(self):
        """
        Test the creation of a payment message
        """
        self.transaction.incoming_address = WalletAddress('abc')
        self.transaction.outgoing_address = WalletAddress('def')
        self.transaction.partner_incoming_address = WalletAddress('ghi')
        self.transaction.partner_outgoing_address = WalletAddress('jkl')
        payment_msg = self.transaction_manager.create_payment_message(TraderId("0"),
                                                                      PaymentId('abc'), self.transaction,
                                                                      (Quantity(3, 'MC'), Price(4, 'BTC')),
                                                                      True)
        self.assertIsInstance(payment_msg, Payment)
