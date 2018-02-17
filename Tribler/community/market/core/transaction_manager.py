import logging

from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import ProposedTrade
from Tribler.community.market.core.transaction import TransactionId, Transaction, StartTransaction
from Tribler.community.market.core.transaction_repository import TransactionRepository


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

    def create_from_proposed_trade(self, proposed_trade, match_id):
        """
        :type proposed_trade: ProposedTrade
        :type match_id: str
        :rtype: Transaction
        """
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)

        transaction = Transaction.from_proposed_trade(proposed_trade, self.transaction_repository.next_identity())
        transaction.match_id = match_id
        self.transaction_repository.add(transaction)

        self._logger.info("Transaction created with id: %s, quantity: %s, price: %s",
                          str(transaction.transaction_id), str(transaction.total_quantity), str(transaction.price))
        return transaction

    def create_from_start_transaction(self, start_transaction, match_id):
        """
        :type start_transaction: StartTransaction
        :type match_id: str
        :rtype: Transaction
        """
        assert isinstance(start_transaction, StartTransaction), type(start_transaction)

        transaction = Transaction(start_transaction.transaction_id, start_transaction.price, start_transaction.quantity,
                                  start_transaction.recipient_order_id, start_transaction.order_id, Timestamp.now())
        transaction.match_id = match_id
        self.transaction_repository.add(transaction)

        self._logger.info("Transaction created with id: %s, quantity: %s, price: %s",
                          str(transaction.transaction_id), str(transaction.total_quantity), str(transaction.price))

        return transaction

    def create_payment_message(self, message_id, payment_id, transaction, payment, success):
        payment_message = Payment(message_id, transaction.transaction_id, payment[0], payment[1],
                                  transaction.outgoing_address, transaction.partner_incoming_address,
                                  payment_id, Timestamp.now(), success)
        transaction.add_payment(payment_message)
        self.transaction_repository.update(transaction)

        return payment_message

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
