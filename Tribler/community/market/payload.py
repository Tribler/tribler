from ...dispersy.payload import Payload


class AskPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, price, quantity, timeout, timestamp, ttl):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(price, int), type(price)
            assert isinstance(quantity, int), type(quantity)
            assert isinstance(timeout, float), type(timeout)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(ttl, int), type(ttl)
            super(AskPayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._price = price
            self._quantity = quantity
            self._timeout = timeout
            self._timestamp = timestamp
            self._ttl = ttl

        @property
        def trader_id(self):
            return self._trader_id

        @property
        def message_number(self):
            return self._message_number

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


class BidPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, price, quantity, timeout, timestamp, ttl):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(price, int), type(price)
            assert isinstance(quantity, int), type(quantity)
            assert isinstance(timeout, float), type(timeout)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(ttl, int), type(ttl)
            super(BidPayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._price = price
            self._quantity = quantity
            self._timeout = timeout
            self._timestamp = timestamp
            self._ttl = ttl

        @property
        def trader_id(self):
            return self._trader_id

        @property
        def message_number(self):
            return self._message_number

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


class ProposedTradePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, trader_id, message_number, sender_trader_id, sender_message_number,
                     recipient_trader_id, recipient_message_number, price, quantity, timestamp, quick):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(sender_trader_id, str), type(sender_trader_id)
            assert isinstance(sender_message_number, str), type(sender_message_number)
            assert isinstance(recipient_trader_id, str), type(recipient_trader_id)
            assert isinstance(recipient_message_number, str), type(recipient_message_number)
            assert isinstance(price, int), type(price)
            assert isinstance(quantity, int), type(quantity)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(quick, bool), type(quick)
            super(ProposedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._sender_trader_id = sender_trader_id
            self._sender_message_number = sender_message_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_message_number = recipient_message_number
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
        def sender_trader_id(self):
            return self._sender_trader_id

        @property
        def sender_message_number(self):
            return self._sender_message_number

        @property
        def recipient_trader_id(self):
            return self._recipient_trader_id

        @property
        def recipient_message_number(self):
            return self._recipient_message_number

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
        def __init__(self, meta, trader_id, message_number, sender_trader_id, sender_message_number,
                     recipient_trader_id, recipient_message_number, price, quantity, timestamp, quick, ttl):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(sender_trader_id, str), type(sender_trader_id)
            assert isinstance(sender_message_number, str), type(sender_message_number)
            assert isinstance(recipient_trader_id, str), type(recipient_trader_id)
            assert isinstance(recipient_message_number, str), type(recipient_message_number)
            assert isinstance(price, int), type(price)
            assert isinstance(quantity, int), type(quantity)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(quick, bool), type(quick)
            assert isinstance(ttl, int), type(ttl)
            super(AcceptedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._sender_trader_id = sender_trader_id
            self._sender_message_number = sender_message_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_message_number = recipient_message_number
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
        def sender_trader_id(self):
            return self._sender_trader_id

        @property
        def sender_message_number(self):
            return self._sender_message_number

        @property
        def recipient_trader_id(self):
            return self._recipient_trader_id

        @property
        def recipient_message_number(self):
            return self._recipient_message_number

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
        def __init__(self, meta, trader_id, message_number, recipient_trader_id, recipient_message_number, timestamp,
                     quick):
            assert isinstance(trader_id, str), type(trader_id)
            assert isinstance(message_number, str), type(message_number)
            assert isinstance(recipient_trader_id, str), type(recipient_trader_id)
            assert isinstance(recipient_message_number, str), type(recipient_message_number)
            assert isinstance(timestamp, float), type(timestamp)
            assert isinstance(quick, bool), type(quick)
            super(DeclinedTradePayload.Implementation, self).__init__(meta)
            self._trader_id = trader_id
            self._message_number = message_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_message_number = recipient_message_number
            self._timestamp = timestamp
            self._quick = quick

        @property
        def trader_id(self):
            return self._trader_id

        @property
        def message_number(self):
            return self._message_number

        @property
        def recipient_trader_id(self):
            return self._recipient_trader_id

        @property
        def recipient_message_number(self):
            return self._recipient_message_number

        @property
        def timestamp(self):
            return self._timestamp

        @property
        def quick(self):
            return self._quick
