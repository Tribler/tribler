import unittest

from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.transaction_repository import MemoryTransactionRepository
from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.timestamp import Timestamp


class MemoryTransactionRepositoryTestSuite(unittest.TestCase):
    """Memory transaction repository test cases."""

    def setUp(self):
        # Object creation
        self.memory_transaction_repository = MemoryTransactionRepository("0")
        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber(1))
        self.transaction = Transaction(self.transaction_id, Price(100, 'BTC'), Quantity(30, 'MC'),
                                       OrderId(TraderId("0"), OrderNumber(1)),
                                       OrderId(TraderId("2"), OrderNumber(2)), Timestamp(0.0))

    def test_find_by_id(self):
        # Test for find by id
        self.assertEquals(None, self.memory_transaction_repository.find_by_id(self.transaction_id))
        self.memory_transaction_repository.add(self.transaction)
        self.assertEquals(self.transaction, self.memory_transaction_repository.find_by_id(self.transaction_id))

    def test_delete_by_id(self):
        # Test for delete by id
        self.memory_transaction_repository.add(self.transaction)
        self.assertEquals(self.transaction, self.memory_transaction_repository.find_by_id(self.transaction_id))
        self.memory_transaction_repository.delete_by_id(self.transaction_id)
        self.assertEquals(None, self.memory_transaction_repository.find_by_id(self.transaction_id))

    def test_find_all(self):
        # Test for find all
        self.assertEquals([], self.memory_transaction_repository.find_all())
        self.memory_transaction_repository.add(self.transaction)
        self.assertEquals([self.transaction], self.memory_transaction_repository.find_all())

    def test_next_identity(self):
        # Test for next identity
        self.assertEquals(TransactionId(TraderId("0"), TransactionNumber(1)),
                          self.memory_transaction_repository.next_identity())
        self.assertEquals(TransactionId(TraderId("0"), TransactionNumber(2)),
                          self.memory_transaction_repository.next_identity())

    def test_update(self):
        # Test for update
        self.memory_transaction_repository.add(self.transaction)
        self.memory_transaction_repository.update(self.transaction)
        self.assertEquals(self.transaction, self.memory_transaction_repository.find_by_id(self.transaction_id))
