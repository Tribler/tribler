from Tribler.dispersy.payload import Payload


class OfferPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, price, quantity, timeout, timestamp, ttl,
                     address):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(order_number, str), type(order_number)
            assert isinstance(price, int), type(price)
            assert isinstance(quantity, int), type(quantity)
            assert isinstance(timeout, float), type(timeout)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(ttl, int), type(ttl)
            assert isinstance(address, tuple), type(address)
            assert isinstance(address[0], str)
            assert isinstance(address[1], int)
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
                     price, quantity, timestamp, quick):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(order_number, str), type(order_number)
            assert isinstance(recipient_trader_id, str), type(recipient_trader_id)
            assert isinstance(recipient_order_number, str), type(recipient_order_number)
            assert isinstance(price, int), type(price)
            assert isinstance(quantity, int), type(quantity)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(quick, bool), type(quick)
            super(ProposedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._price = price
            self._quantity = quantity
            self._timestamp = timestamp
            self._quick = quick

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
        def quick(self):
            return self._quick


class AcceptedTradePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     price, quantity, timestamp, quick, ttl):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(order_number, str), type(order_number)
            assert isinstance(recipient_trader_id, str), type(recipient_trader_id)
            assert isinstance(recipient_order_number, str), type(recipient_order_number)
            assert isinstance(price, int), type(price)
            assert isinstance(quantity, int), type(quantity)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(quick, bool), type(quick)
            assert isinstance(ttl, int), type(ttl)
            super(AcceptedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._price = price
            self._quantity = quantity
            self._timestamp = timestamp
            self._quick = quick
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
        def quick(self):
            return self._quick

        @property
        def ttl(self):
            return self._ttl


class DeclinedTradePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     timestamp, quick):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(order_number, str), type(order_number)
            assert isinstance(recipient_trader_id, str), type(recipient_trader_id)
            assert isinstance(recipient_order_number, str), type(recipient_order_number)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(quick, bool), type(quick)
            super(DeclinedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._timestamp = timestamp
            self._quick = quick

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

        @property
        def quick(self):
            return self._quick
