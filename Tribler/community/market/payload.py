from Tribler.dispersy.payload import Payload
from core.message import TraderId, MessageNumber
from core.order import OrderNumber
from core.price import Price
from core.quantity import Quantity
from core.timeout import Timeout
from core.timestamp import Timestamp
from socket_address import SocketAddress
from ttl import Ttl


class OfferPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, price, quantity, timeout, timestamp, ttl,
                     address):
            assert isinstance(trader_id, TraderId), type(trader_id)
            assert isinstance(message_number, MessageNumber), type(message_number)
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(price, Price), type(price)
            assert isinstance(quantity, Quantity), type(quantity)
            assert isinstance(timeout, Timeout), type(timeout)
            assert isinstance(timestamp, Timestamp), type(timestamp)
            assert isinstance(ttl, Ttl), type(ttl)
            assert isinstance(address, SocketAddress), type(address)
            super(OfferPayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._order_number = order_number
            self._price = price
            self._quantity = quantity
            self._timeout = timeout
            self._timestamp = timestamp
            self._ttl = ttl
            self._address = address

        @property
        def trader_id(self):
            return self._trader_id

        @property
        def message_number(self):
            return self._message_number

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
        def timestamp(self):
            return self._timestamp

        @property
        def ttl(self):
            return self._ttl

        @property
        def address(self):
            return self._address


class ProposedTradePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     price, quantity, timestamp):
            assert isinstance(trader_id, TraderId), type(trader_id)
            assert isinstance(message_number, MessageNumber), type(message_number)
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(recipient_trader_id, TraderId), type(recipient_trader_id)
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            assert isinstance(price, Price), type(price)
            assert isinstance(quantity, Quantity), type(quantity)
            assert isinstance(timestamp, Timestamp), type(timestamp)
            super(ProposedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._price = price
            self._quantity = quantity
            self._timestamp = timestamp

        @property
        def trader_id(self):
            return self._trader_id

        @property
        def message_number(self):
            return self._message_number

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

        @property
        def timestamp(self):
            return self._timestamp


class AcceptedTradePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     price, quantity, timestamp, ttl):
            assert isinstance(trader_id, TraderId), type(trader_id)
            assert isinstance(message_number, MessageNumber), type(message_number)
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(recipient_trader_id, TraderId), type(recipient_trader_id)
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            assert isinstance(price, Price), type(price)
            assert isinstance(quantity, Quantity), type(quantity)
            assert isinstance(timestamp, Timestamp), type(timestamp)
            assert isinstance(ttl, Ttl), type(ttl)
            super(AcceptedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._price = price
            self._quantity = quantity
            self._timestamp = timestamp
            self._ttl = ttl

        @property
        def trader_id(self):
            return self._trader_id

        @property
        def message_number(self):
            return self._message_number

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

        @property
        def timestamp(self):
            return self._timestamp

        @property
        def ttl(self):
            return self._ttl


class DeclinedTradePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     timestamp):
            assert isinstance(trader_id, TraderId), type(trader_id)
            assert isinstance(message_number, MessageNumber), type(message_number)
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(recipient_trader_id, TraderId), type(recipient_trader_id)
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            assert isinstance(timestamp, Timestamp), type(timestamp)
            super(DeclinedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._timestamp = timestamp

        @property
        def trader_id(self):
            return self._trader_id

        @property
        def message_number(self):
            return self._message_number

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
        def timestamp(self):
            return self._timestamp
