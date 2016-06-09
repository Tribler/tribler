from bitcoin_address import BitcoinAddress
from message import MessageId, Message
from quantity import Quantity
from timestamp import Timestamp
from transaction import TransactionNumber


class Payment(Message):
    """Abstract class for representing a payment."""

    def __init__(self, message_id, transaction_number, timestamp):
        assert isinstance(message_id, MessageId), type(message_id)
        assert isinstance(transaction_number, TransactionNumber), type(transaction_number)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        super(Payment, self).__init__(message_id, timestamp)
        self._message_id = message_id
        self._transaction_number = transaction_number
        self._timestamp = timestamp

    @property
    def message_id(self):
        return self._message_id

    @property
    def transaction_number(self):
        return self._transaction_number

    @property
    def timestamp(self):
        return self._timestamp

    @classmethod
    def from_network(cls, data):
        """
        Restore a payment from the network

        :param data: object with (message_id, transaction_number, timestamp) properties
        :return: Restored payment
        :rtype: Payment
        """
        assert hasattr(data, 'message_id'), isinstance(data.message_id, MessageId)
        assert hasattr(data, 'transaction_number'), isinstance(data.order_number, TransactionNumber)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            data.message_id,
            data.transaction_number,
            data.timestamp,
        )

    def to_network(self):
        """
        Return network representation of the payment

        :return: tuple(<destination public identifiers>),tuple(<message_id>, <transaction_number>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            self._message_id,
            self._transaction_number,
            self._timestamp,
        )


class MultiChainPayment(Payment):
    """Class representing a multi chain payment."""

    def __init__(self, message_id, transaction_number, bitcoin_address, transferor_quantity,
                 transferee_quantity, timestamp):
        assert isinstance(message_id, MessageId), type(message_id)
        assert isinstance(transaction_number, TransactionNumber), type(transaction_number)
        assert isinstance(bitcoin_address, BitcoinAddress), type(bitcoin_address)
        assert isinstance(transferor_quantity, Quantity), type(transferor_quantity)
        assert isinstance(transferee_quantity, Quantity), type(transferee_quantity)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        super(MultiChainPayment, self).__init__(message_id, transaction_number, timestamp)
        self._transaction_number = transaction_number
        self._bitcoin_address = bitcoin_address
        self._transferor_quantity = transferor_quantity
        self._transferee_quantity = transferee_quantity

    @property
    def bitcoin_address(self):
        return self._bitcoin_address

    @property
    def transferor_quantity(self):
        return self._transferor_quantity

    @property
    def transferee_quantity(self):
        return self._transferee_quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a multi chain payment from the network

        :param data: object with (message_id, transaction_number, bitcoin_address, transferor_quantity, transferee_quantity, timestamp) properties
        :return: Restored multi chain payment
        :rtype: Multi chain payment
        """
        assert hasattr(data, 'message_id'), isinstance(data.message_id, MessageId)
        assert hasattr(data, 'transaction_number'), isinstance(data.order_number, TransactionNumber)
        assert hasattr(data, 'bitcoin_address'), isinstance(data.quantity, BitcoinAddress)
        assert hasattr(data, 'transferor_quantity'), isinstance(data.quantity, Quantity)
        assert hasattr(data, 'transferee_quantity'), isinstance(data.quantity, Quantity)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            data.message_id,
            data.transaction_number,
            data.bitcoin_address,
            data.transferor_quantity,
            data.transferee_quantity,
            data.timestamp,
        )

    def to_network(self):
        """
        Return network representation of the multi chain payment

        :return: tuple(<destination public identifiers>),tuple(<message_id>, <transaction_number>, <bitcoin_address>, <transferor_quantity>, <transferee_quantity>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            self._message_id,
            self._transaction_number,
            self._bitcoin_address,
            self._transferor_quantity,
            self._transferee_quantity,
            self._timestamp,
        )


class BitcoinPayment(Payment):
    """Class representing a bitcoin payment."""

    def __init__(self, message_id, transaction_number, quantity, timestamp):
        assert isinstance(message_id, MessageId), type(message_id)
        assert isinstance(transaction_number, TransactionNumber), type(transaction_number)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        super(BitcoinPayment, self).__init__(message_id, transaction_number, timestamp)
        self._transaction_number = transaction_number
        self._quantity = quantity

    @property
    def quantity(self):
        return self._quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a bitcoin payment from the network

        :param data: object with (message_id, transaction_number, quantity, timestamp) properties
        :return: Restored bitcoin payment
        :rtype: Bitcoin payment
        """
        assert hasattr(data, 'message_id'), isinstance(data.message_id, MessageId)
        assert hasattr(data, 'transaction_number'), isinstance(data.order_number, TransactionNumber)
        assert hasattr(data, 'quantity'), isinstance(data.quantity, Quantity)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            data.message_id,
            data.transaction_number,
            data.quantity,
            data.timestamp,
        )

    def to_network(self):
        """
        Return network representation of the bitcoin payment

        :return: tuple(<destination public identifiers>),tuple(<message_id>, <transaction_number>, <quantity>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            self._message_id,
            self._transaction_number,
            self._quantity,
            self._timestamp,
        )
