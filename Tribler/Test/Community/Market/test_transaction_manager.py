import unittest

from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.timeout import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction
from Tribler.community.market.core.transaction_repository import MemoryTransactionRepository
from Tribler.community.market.core.transaction_manager import TransactionManager
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.trade import Trade


class TransactionManagerTestSuite(unittest.TestCase):
    """Transaction manager test cases."""

    def setUp(self):
        # Object creation
        self.memory_transaction_repository = MemoryTransactionRepository("0")
        self.transaction_manager = TransactionManager(self.memory_transaction_repository)

        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber("1"))
        self.transaction = Transaction(self.transaction_id, Price(100), Quantity(30), Timeout(0.0), Timestamp(0.0))
        proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                       OrderId(TraderId('0'), OrderNumber('order_number')),
                                       OrderId(TraderId('1'), OrderNumber('recipient_order_number')),
                                       Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.accepted_trade = Trade.accept(MessageId(TraderId('0'), MessageNumber('message_number')),
                                           Timestamp(1462224447.117), proposed_trade)

    def test_create_from_accepted_trade(self):
        # Test for create from accepted trade
        transaction = self.transaction_manager.create_from_accepted_trade(self.accepted_trade)
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

    def test_create_transaction(self):
        # Test for create transaction
        transaction = self.transaction_manager.create_transaction(Price(100), Quantity(30), Timeout(0.0))
        self.assertEquals(transaction, self.transaction_manager.find_by_id(transaction.transaction_id))


if __name__ == '__main__':
    unittest.main()
