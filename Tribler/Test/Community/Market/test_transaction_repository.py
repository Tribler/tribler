import unittest

from Tribler.community.market.core.transaction_repository import TransactionRepository, MemoryTransactionRepository
from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class TransactionRepositoryTestSuite(unittest.TestCase):
    """Transaction repository test cases."""

    def setUp(self):
        # Object creation
        self.transaction_repository = TransactionRepository()
        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber("1"))
        self.transaction = Transaction(self.transaction_id, Price(100), Quantity(30), Timeout(0.0), Timestamp(0.0))

    def test_abstraction(self):
        # Test for abstract functions
        self.assertEquals(NotImplemented, self.transaction_repository.add(self.transaction))
        self.assertEquals(NotImplemented, self.transaction_repository.delete_by_id(self.transaction))
        self.assertEquals(NotImplemented, self.transaction_repository.find_all())
        self.assertEquals(NotImplemented, self.transaction_repository.find_by_id(self.transaction_id))
        self.assertEquals(NotImplemented, self.transaction_repository.next_identity())
        self.assertEquals(NotImplemented, self.transaction_repository.update(self.transaction))


class MemoryTransactionRepositoryTestSuite(unittest.TestCase):
    """Memory transaction repository test cases."""

    def setUp(self):
        # Object creation
        self.memory_transaction_repository = MemoryTransactionRepository("0")
        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber("1"))
        self.transaction = Transaction(self.transaction_id, Price(100), Quantity(30), Timeout(0.0), Timestamp(0.0))

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
        self.assertEquals(TransactionId(TraderId("0"), TransactionNumber("1")),
                          self.memory_transaction_repository.next_identity())
        self.assertEquals(TransactionId(TraderId("0"), TransactionNumber("2")),
                          self.memory_transaction_repository.next_identity())

    def test_update(self):
        # Test for update
        self.memory_transaction_repository.add(self.transaction)
        self.memory_transaction_repository.update(self.transaction)
        self.assertEquals(self.transaction, self.memory_transaction_repository.find_by_id(self.transaction_id))


if __name__ == '__main__':
    unittest.main()
