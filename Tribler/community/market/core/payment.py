from bitcoin_address import BitcoinAddress
from message import MessageId, Message, TraderId, MessageNumber
from price import Price
from quantity import Quantity
from timestamp import Timestamp
from transaction import TransactionNumber, TransactionId


class MultiChainPayment(Message):
    """Class representing a multi chain payment."""

    def __init__(self, message_id, transaction_id, bitcoin_address, transferor_quantity,
                 transferee_price, timestamp):
        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(bitcoin_address, BitcoinAddress), type(bitcoin_address)
        assert isinstance(transferor_quantity, Quantity), type(transferor_quantity)
        assert isinstance(transferee_price, Price), type(transferee_price)
        super(MultiChainPayment, self).__init__(message_id, timestamp)
        self._transaction_id = transaction_id
        self._bitcoin_address = bitcoin_address
        self._transferor_quantity = transferor_quantity
        self._transferee_price = transferee_price

    @property
    def bitcoin_address(self):
        return self._bitcoin_address

    @property
    def transferor_quantity(self):
        return self._transferor_quantity

    @property
    def transferee_price(self):
        return self._transferee_price

    @classmethod
    def from_network(cls, data):
        """
        Restore a multi chain payment from the network

        :param data: object with (message_id, transaction_number, bitcoin_address, transferor_quantity, transferee_quantity, timestamp) properties
        :return: Restored multi chain payment
        :rtype: Multi chain payment
        """
        assert hasattr(data, 'trader_id'), isinstance(data.trader_id, TraderId)
        assert hasattr(data, 'message_number'), isinstance(data.message_number, MessageNumber)
        assert hasattr(data, 'transaction_trader_id'), isinstance(data.transaction_trader_id, TraderId)
        assert hasattr(data, 'transaction_number'), isinstance(data.transaction_number, TransactionNumber)
        assert hasattr(data, 'bitcoin_address'), isinstance(data.bitcoin_address, BitcoinAddress)
        assert hasattr(data, 'transferor_quantity'), isinstance(data.transferor_quantity, Quantity)
        assert hasattr(data, 'transferee_price'), isinstance(data.transferee_price, Price)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            MessageId(data.trader_id, data.message_number),
            TransactionId(data.transaction_trader_id, data.transaction_number),
            data.bitcoin_address,
            data.transferor_quantity,
            data.transferee_price,
            data.timestamp,
        )

    def to_network(self):
        """
        Return network representation of the multi chain payment

        :return: tuple(<destination public identifiers>),tuple(<message_id>, <transaction_number>, <bitcoin_address>, <transferor_quantity>, <transferee_quantity>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            self._message_id.trader_id,
            self._message_id.message_number,
            self._transaction_id.trader_id,
            self._transaction_id.transaction_number,
            self._bitcoin_address,
            self._transferor_quantity,
            self._transferee_price,
            self._timestamp,
        )


class BitcoinPayment(Message):
    """Class representing a bitcoin payment."""

    def __init__(self, message_id, transaction_id, bitcoin_address, price, timestamp):
        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(bitcoin_address, BitcoinAddress), type(bitcoin_address)
        assert isinstance(price, Price), type(price)
        super(BitcoinPayment, self).__init__(message_id, timestamp)
        self._transaction_id = transaction_id
        self._bitcoin_address = bitcoin_address
        self._price = price

    @property
    def transaction_id(self):
        return self._transaction_id

    @property
    def bitcoin_address(self):
        return self._bitcoin_address

    @property
    def price(self):
        return self._price

    @classmethod
    def from_network(cls, data):
        """
        Restore a bitcoin payment from the network

        :param data: object with (message_id, transaction_number, quantity, timestamp) properties
        :return: Restored bitcoin payment
        :rtype: Bitcoin payment
        """
        assert hasattr(data, 'trader_id'), isinstance(data.trader_id, TraderId)
        assert hasattr(data, 'message_number'), isinstance(data.message_number, MessageNumber)
        assert hasattr(data, 'transaction_trader_id'), isinstance(data.transaction_trader_id, TraderId)
        assert hasattr(data, 'transaction_number'), isinstance(data.transaction_number, TransactionNumber)
        assert hasattr(data, 'bitcoin_address'), isinstance(data.bitcoin_address, BitcoinAddress)
        assert hasattr(data, 'price'), isinstance(data.price, Price)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            MessageId(data.trader_id, data.message_number),
            TransactionId(data.transaction_trader_id, data.transaction_number),
            data.price,
            data.bitcoin_address,
            data.timestamp,
        )

    def to_network(self):
        """
        Return network representation of the bitcoin payment

        :return: tuple(<destination public identifiers>),tuple(<message_id>, <transaction_number>, <quantity>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            self._message_id.trader_id,
            self._message_id.message_number,
            self._transaction_id.trader_id,
            self._transaction_id.transaction_number,
            self._bitcoin_address,
            self._price,
            self._timestamp,
        )
