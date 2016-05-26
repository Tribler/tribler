import logging

from transaction import TransactionNumber, TransactionId, Transaction
from message import TraderId


class TransactionRepository(object):
    """A repository interface for transactions in the transaction manager"""

    def __init__(self):
        """
        Do not use this class directly

        Make a subclass of this class with a specific implementation for a storage backend
        """
        super(TransactionRepository, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

    def find_all(self):
        """
        Find all transactions
        :rtype: [Transaction]
        """
        return NotImplemented

    def find_by_id(self, transaction_id):
        """
        Find a transaction by its identity

        :param transaction_id: The transaction id to look for
        :type transaction_id: TransactionId
        :return: The transaction or null if it cannot be found
        :rtype: Transaction
        """
        return NotImplemented

    def add(self, transaction):
        """
        Add a transaction to the collection

        :param transaction: The transaction to add
        :type transaction: Transaction
        """
        return NotImplemented

    def update(self, transaction):
        """
        Update a transaction in the collection

        :param transaction: The transaction that has been updated
        :type transaction: Transaction
        """
        return NotImplemented

    def delete_by_id(self, transaction_id):
        """
        Delete the transaction with the given id

        :param transaction_id: The transaction id for the transaction to delete
        :type transaction_id: TransactionId
        """
        return NotImplemented

    def next_identity(self):
        """
        Return the next identity

        :return: The next available identity
        :rtype: TransactionId
        """
        return NotImplemented


class MemoryTransactionRepository(TransactionRepository):
    """A repository for transactions in the transaction manager stored in memory"""

    def __init__(self, pubkey):
        """
        Initialise the MemoryTransactionRepository

        :param pubkey: Hex encoded version of the public key of this node
        :type pubkey: str
        """
        super(MemoryTransactionRepository, self).__init__()

        self._logger.info("Memory transaction repository used")

        self._pubkey = pubkey
        self._next_id = 0  # Counter to keep track of the number of messages created by this repository

        self._transactions = {}

    def find_all(self):
        """
        Find all transactions
        :rtype: [Transaction]
        """
        return self._transactions.values()

    def find_by_id(self, transaction_id):
        """
        Find a transaction by its identity

        :param transaction_id: The transaction id to look for
        :type transaction_id: TransactionId
        :return: The transaction or null if it cannot be found
        :rtype: Transaction
        """
        assert isinstance(transaction_id, TransactionId), type(transaction_id)

        self._logger.debug(
            "Transaction with the id: " + str(transaction_id) + " was searched for in the transaction repository")

        return self._transactions.get(transaction_id)

    def add(self, transaction):
        """
        Add a transaction to the collection

        :param transaction: The transaction to add
        :type transaction: Transaction
        """
        assert isinstance(transaction, Transaction), type(transaction)

        self._logger.debug(
            "Transaction with the id: " + str(transaction.transaction_id) + " was added to the transaction repository")

        self._transactions[transaction.transaction_id] = transaction

    def update(self, transaction):
        """
        Update a transaction in the collection

        :param transaction: The transaction that has been updated
        :type transaction: Transaction
        """
        assert isinstance(transaction, Transaction), type(transaction)

        self._logger.debug("Transaction with the id: " + str(
            transaction.transaction_id) + " was updated to the transaction repository")

        self._transactions[transaction.transaction_id] = transaction

    def delete_by_id(self, transaction_id):
        """
        Delete the transaction with the given id

        :param transaction_id: The transaction id for the transaction to delete
        :type transaction_id: TransactionId
        """
        assert isinstance(transaction_id, TransactionId), type(transaction_id)

        self._logger.debug(
            "Transaction with the id: " + str(transaction_id) + " was deleted from the transaction repository")

        del self._transactions[transaction_id]

    def next_identity(self):
        """
        Return the next identity

        :return: The next available identity
        :rtype: TransactionId
        """
        self._next_id += 1
        return TransactionId(TraderId(self._pubkey), TransactionNumber(str(self._next_id)))
