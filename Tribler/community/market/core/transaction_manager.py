import logging

from price import Price
from quantity import Quantity
from timeout import Timeout
from timestamp import Timestamp
from trade import AcceptedTrade
from transaction import TransactionId, Transaction
from transaction_repository import TransactionRepository


class TransactionManager(object):
    """Manager for retrieving and creating transactions"""

    def __init__(self, transaction_repository):
        """
        :type transaction_repository: TransactionRepository
        """
        super(TransactionManager, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Transaction Manager initialized")

        assert isinstance(transaction_repository, TransactionRepository), type(transaction_repository)

        self.transaction_repository = transaction_repository

    def create_from_accepted_trade(self, accepted_trade):
        """
        :type accepted_trade: AcceptedTrade
        :rtype: Transaction
        """
        assert isinstance(accepted_trade, AcceptedTrade), type(accepted_trade)

        transaction = Transaction.from_accepted_trade(accepted_trade, self.transaction_repository.next_identity())
        self.transaction_repository.add(transaction)

        self._logger.info("Transaction created with id: " + str(transaction.transaction_id))
        return transaction

    def create_transaction(self, price, quantity, timeout):
        """
        :param price: The price for the transaction
        :param quantity: The quantity of the transaction
        :param timeout: The timeout of the transaction, when does the transaction need to be timed out
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :rtype: Transaction
        """
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)

        transaction = Transaction(self.transaction_repository.next_identity(), price, quantity, timeout,
                                  Timestamp.now())
        self.transaction_repository.add(transaction)

        self._logger.info("Transaction created with id: " + str(transaction.transaction_id))

        return transaction

    def find_by_id(self, transaction_id):
        """
        :param transaction_id: The transaction id to look for
        :type transaction_id: TransactionId
        :return: The transaction or null if it cannot be found
        :rtype: Transaction
        """
        assert isinstance(transaction_id, TransactionId), type(transaction_id)

        return self.transaction_repository.find_by_id(transaction_id)

    def find_all(self):
        """
        :rtype: [Transaction]
        """
        return self.transaction_repository.find_all()
