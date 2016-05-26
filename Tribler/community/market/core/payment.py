from message import TraderId, MessageNumber, Message, MessageId
from transaction import TransactionNumber
from timestamp import Timestamp
from quantity import Quantity
from price import Price
from bitcoin_address import BitcoinAddress


class Payment(Message):
    """Abstract class for representing a payment."""

    def __init__(self, trader_id, message_number, transaction_number, timestamp):
        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(message_number, MessageNumber), type(message_number)
        assert isinstance(transaction_number, TransactionNumber), type(transaction_number)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        super(Payment, self).__init__(MessageId(trader_id, message_number), timestamp)
        self._trader_id = trader_id
        self._message_number = message_number
        self._transaction_number = transaction_number
        self._timestamp = timestamp


class MultiChainPayment(Payment):
    """Class representing a multi chain payment."""

    def __init__(self, trader_id, message_number, transaction_number, bitcoin_address, transferor_quantity,
                 transferee_quantity, timestamp):
        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(message_number, MessageNumber), type(message_number)
        assert isinstance(transaction_number, TransactionNumber), type(transaction_number)
        assert isinstance(bitcoin_address, BitcoinAddress), type(bitcoin_address)
        assert isinstance(transferor_quantity, Quantity), type(transferor_quantity)
        assert isinstance(transferee_quantity, Quantity), type(transferee_quantity)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        super(MultiChainPayment, self).__init__(trader_id, message_number, transaction_number, timestamp)
        self._trader_id = trader_id
        self._message_number = message_number
        self._transaction_number = transaction_number
        self._bitcoin_address = bitcoin_address
        self._transferor_quantity = transferor_quantity
        self._transferee_quantity = transferee_quantity
        self._timestamp = timestamp


class BitcoinPayment(Payment):
    """Class representing a bitcoin payment."""

    def __init__(self, trader_id, message_number, transaction_number, quantity, timestamp):
        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(message_number, MessageNumber), type(message_number)
        assert isinstance(transaction_number, TransactionNumber), type(transaction_number)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        super(BitcoinPayment, self).__init__(trader_id, message_number, transaction_number, timestamp)
        self._trader_id = trader_id
        self._message_number = message_number
        self._transaction_number = transaction_number
        self._quantity = quantity
        self._timestamp = timestamp
