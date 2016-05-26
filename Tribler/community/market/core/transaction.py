from message import TraderId
from price import Price
from quantity import Quantity
from timeout import Timeout
from timestamp import Timestamp
from trade import AcceptedTrade


class TransactionNumber(object):
    """Immutable class for representing the number of a transaction."""

    def __init__(self, transaction_number):
        """
        Initialise the transaction number

        :param transaction_number: String representing the number of a transaction
        :type transaction_number: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(TransactionNumber, self).__init__()

        if not isinstance(transaction_number, str):
            raise ValueError("Transaction number must be a string")

        self._transaction_number = transaction_number

    def __str__(self):
        """
        Return the string representation of the order number

        :return: The string representation of the order number
        :rtype: str
        """
        return "%s" % self._transaction_number

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, TransactionNumber):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._transaction_number == \
                   other._transaction_number

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._transaction_number)


class TransactionId(object):
    """Immutable class for representing the id of a transaction."""

    def __init__(self, trader_id, transaction_number):
        """
        Initialise the transaction id

        :param trader_id: The trader id who created the order
        :param transaction_number: The number of the transaction created
        :type trader_id: TraderId
        :type transaction_number: TransactionNumber
        """
        super(TransactionId, self).__init__()

        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(transaction_number, TransactionNumber), type(transaction_number)

        self._trader_id = trader_id
        self._transaction_number = transaction_number

    @property
    def trader_id(self):
        """
        Return the trader id

        :return: The trader id of the message id
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def transaction_number(self):
        """
        Return the transaction number

        :return: The transaction number of the transaction id
        :rtype: TransactionNumber
        """
        return self._transaction_number

    def __str__(self):
        """
        Return the string representation of the transaction id

        format: <trader_id>.<transaction_number>

        :return: The string representation of the transaction id
        :rtype: str
        """
        return "%s.%s" % (self._trader_id, self._transaction_number)

    def __eq__(self, other):
        """
        Check if two objects are the same

        :param other: An object to compare with
        :return: True if the object is the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, TransactionId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self._trader_id, self._transaction_number) == \
                   (other._trader_id, other._transaction_number)

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the object is not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash((self._trader_id, self._transaction_number))


class Transaction(object):
    """Class for representing a transaction between two nodes"""

    def __init__(self, transaction_id, price, quantity, timeout, timestamp):
        """
        Initialise the transaction

        :param transaction_id: An transaction id to identify the order
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param timeout: A timeout when this transaction is going to expire
        :param timestamp: A timestamp when the transaction was created
        :type transaction_id: TransactionId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        """
        super(Transaction, self).__init__()

        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)
        assert isinstance(timestamp, Timestamp), type(timestamp)

        self._transaction_id = transaction_id
        self._price = price
        self._quantity = quantity
        self._timeout = timeout
        self._timestamp = timestamp

    @classmethod
    def from_accepted_trade(cls, accepted_trade, transaction_id):
        """

        :param accepted_trade: The accepted trade to create the transaction for
        :param transaction_id: The transaction id to use for this transaction
        :type accepted_trade: AcceptedTrade
        :type transaction_id: TransactionId
        :return: The created transaction
        :rtype: Transaction
        """
        assert isinstance(accepted_trade, AcceptedTrade), type(accepted_trade)
        assert isinstance(transaction_id, TransactionId), type(transaction_id)

        return cls(transaction_id, accepted_trade.price, accepted_trade.quantity, Timeout(float('inf')),
                   accepted_trade.timestamp)

    @property
    def transaction_id(self):
        """
        Return the transaction id of the transaction

        :return: The transaction id
        :rtype: TransactionId
        """
        return self._transaction_id

    @property
    def price(self):
        """
        Return the price of the order

        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def total_quantity(self):
        """
        Return the total quantity of the order

        :return: The total quantity
        :rtype: Quantity
        """
        return self._quantity

    @property
    def timeout(self):
        """
        Return when the transaction is going to expire

        :return: The timeout
        :rtype: Timeout
        """
        return self._timeout

    @property
    def timestamp(self):
        """
        Return the timestamp of the message

        :return: The timestamp
        :rtype: Timestamp
        """
        return self._timestamp
