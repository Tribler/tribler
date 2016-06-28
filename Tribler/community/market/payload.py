from Tribler.dispersy.payload import Payload

from core.bitcoin_address import BitcoinAddress
from core.message import TraderId, MessageNumber
from core.order import OrderNumber
from core.price import Price
from core.quantity import Quantity
from core.timeout import Timeout
from core.timestamp import Timestamp
from core.transaction import TransactionNumber
from socket_address import SocketAddress
from ttl import Ttl


class MessagePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, timestamp):
            assert isinstance(trader_id, TraderId), type(trader_id)
            assert isinstance(message_number, MessageNumber), type(message_number)
            assert isinstance(timestamp, Timestamp), type(timestamp)
            super(MessagePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._timestamp = timestamp

        @property
        def trader_id(self):
            return self._trader_id

        @property
        def message_number(self):
            return self._message_number

        @property
        def timestamp(self):
            return self._timestamp


class OfferPayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, price, quantity, timeout, timestamp, ttl,
                     ip, port):
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(price, Price), type(price)
            assert isinstance(quantity, Quantity), type(quantity)
            assert isinstance(timeout, Timeout), type(timeout)
            assert isinstance(ttl, Ttl), type(ttl)
            assert isinstance(ip, str), type(ip)
            assert isinstance(port, int), type(port)
            super(OfferPayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._order_number = order_number
            self._price = price
            self._quantity = quantity
            self._timeout = timeout
            self._ttl = ttl
            self._ip = ip
            self._port = port

        @property
        def order_number(self):
            return self._order_number

        @property
        def price(self):
            return self._price

        @property
        def quantity(self):
            return self._quantity

        @property
        def timeout(self):
            return self._timeout

        @property
        def ttl(self):
            return self._ttl

        @property
        def address(self):
            return SocketAddress(self._ip, self._port)


class TradePayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     price, quantity, timestamp):
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(recipient_trader_id, TraderId), type(recipient_trader_id)
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            assert isinstance(price, Price), type(price)
            assert isinstance(quantity, Quantity), type(quantity)
            super(TradePayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._price = price
            self._quantity = quantity

        @property
        def order_number(self):
            return self._order_number

        @property
        def recipient_trader_id(self):
            return self._recipient_trader_id

        @property
        def recipient_order_number(self):
            return self._recipient_order_number

        @property
        def price(self):
            return self._price

        @property
        def quantity(self):
            return self._quantity


class AcceptedTradePayload(TradePayload):
    class Implementation(TradePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     price, quantity, timestamp, ttl):
            assert isinstance(ttl, Ttl), type(ttl)
            super(AcceptedTradePayload.Implementation, self).__init__(meta, trader_id, message_number, order_number,
                                                                      recipient_trader_id, recipient_order_number,
                                                                      price, quantity, timestamp)
            self._ttl = ttl

        @property
        def ttl(self):
            return self._ttl


class DeclinedTradePayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     timestamp):
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(recipient_trader_id, TraderId), type(recipient_trader_id)
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            super(DeclinedTradePayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number

        @property
        def order_number(self):
            return self._order_number

        @property
        def recipient_trader_id(self):
            return self._recipient_trader_id

        @property
        def recipient_order_number(self):
            return self._recipient_order_number


class TransactionPayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, transaction_trader_id, transaction_number, timestamp):
            assert isinstance(transaction_trader_id, TraderId), type(transaction_trader_id)
            assert isinstance(transaction_number, TransactionNumber), type(transaction_number)
            super(TransactionPayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._transaction_trader_id = transaction_trader_id
            self._transaction_number = transaction_number

        @property
        def transaction_trader_id(self):
            return self._transaction_trader_id

        @property
        def transaction_number(self):
            return self._transaction_number


class StartTransactionPayload(TransactionPayload):
    class Implementation(TransactionPayload.Implementation):
        def __init__(self, meta, trader_id, message_number, transaction_trader_id, transaction_number, order_trader_id,
                     order_number, trade_message_number, timestamp):
            assert isinstance(order_trader_id, TraderId), type(order_trader_id)
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(trade_message_number, MessageNumber), type(trade_message_number)
            super(StartTransactionPayload.Implementation, self).__init__(meta, trader_id, message_number,
                                                                         transaction_trader_id, transaction_number,
                                                                         timestamp)
            self._order_trader_id = order_trader_id
            self._order_number = order_number
            self._trade_message_number = trade_message_number

        @property
        def order_trader_id(self):
            return self._order_trader_id

        @property
        def order_number(self):
            return self._order_number

        @property
        def trade_message_number(self):
            return self._trade_message_number


class MultiChainPaymentPayload(TransactionPayload):
    class Implementation(TransactionPayload.Implementation):
        def __init__(self, meta, trader_id, message_number, transaction_trader_id, transaction_number, bitcoin_address,
                     transferor_quantity, transferee_price, timestamp):
            assert isinstance(bitcoin_address, BitcoinAddress), type(bitcoin_address)
            assert isinstance(transferor_quantity, Quantity), type(transferor_quantity)
            assert isinstance(transferee_price, Price), type(transferee_price)
            super(MultiChainPaymentPayload.Implementation, self).__init__(meta, trader_id, message_number,
                                                                          transaction_trader_id, transaction_number,
                                                                          timestamp)
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


class BitcoinPaymentPayload(TransactionPayload):
    class Implementation(TransactionPayload.Implementation):
        def __init__(self, meta, trader_id, message_number, transaction_trader_id, transaction_number, bitcoin_address,
                     price, timestamp):
            assert isinstance(price, Price), type(price)
            assert isinstance(bitcoin_address, BitcoinAddress), type(bitcoin_address)
            super(BitcoinPaymentPayload.Implementation, self).__init__(meta, trader_id, message_number,
                                                                       transaction_trader_id, transaction_number,
                                                                       timestamp)
            self._bitcoin_address = bitcoin_address
            self._price = price

        @property
        def bitcoin_address(self):
            return self._bitcoin_address

        @property
        def price(self):
            return self._price
