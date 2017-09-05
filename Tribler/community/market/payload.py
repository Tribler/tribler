from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.socket_address import SocketAddress
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionNumber
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.dispersy.payload import Payload


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


class InfoPayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, timestamp, is_matchmaker):
            assert isinstance(is_matchmaker, bool), type(is_matchmaker)
            super(InfoPayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._is_matchmaker = is_matchmaker

        @property
        def is_matchmaker(self):
            return self._is_matchmaker


class OfferPayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, price, quantity, timeout, timestamp,
                     ip, port):
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(price, Price), type(price)
            assert isinstance(quantity, Quantity), type(quantity)
            assert isinstance(timeout, Timeout), type(timeout)
            assert isinstance(ip, str), type(ip)
            assert isinstance(port, int), type(port)
            super(OfferPayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._order_number = order_number
            self._price = price
            self._quantity = quantity
            self._timeout = timeout
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
        def address(self):
            return SocketAddress(self._ip, self._port)


class MatchPayload(OfferPayload):
    class Implementation(OfferPayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, price, quantity, timeout, timestamp,
                     ip, port, recipient_order_number, match_quantity, match_trader_id,
                     matchmaker_trader_id, match_id):
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            assert isinstance(match_quantity, Quantity), type(match_quantity)
            assert isinstance(match_trader_id, TraderId), type(match_trader_id)
            assert isinstance(matchmaker_trader_id, TraderId), type(matchmaker_trader_id)
            assert isinstance(match_id, str), type(match_id)
            super(MatchPayload.Implementation, self).__init__(meta, trader_id, message_number, order_number, price,
                                                              quantity, timeout, timestamp, ip, port)
            self._recipient_order_number = recipient_order_number
            self._match_quantity = match_quantity
            self._match_trader_id = match_trader_id
            self._matchmaker_trader_id = matchmaker_trader_id
            self._match_id = match_id

        @property
        def recipient_order_number(self):
            return self._recipient_order_number

        @property
        def match_quantity(self):
            return self._match_quantity

        @property
        def match_trader_id(self):
            return self._match_trader_id

        @property
        def matchmaker_trader_id(self):
            return self._matchmaker_trader_id

        @property
        def match_id(self):
            return self._match_id


class AcceptMatchPayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, timestamp, match_id, quantity):
            assert isinstance(match_id, str), type(match_id)
            assert isinstance(quantity, Quantity), type(quantity)
            super(AcceptMatchPayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._match_id = match_id
            self._quantity = quantity

        @property
        def match_id(self):
            return self._match_id

        @property
        def quantity(self):
            return self._quantity


class DeclineMatchPayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, timestamp, match_id, decline_reason):
            assert isinstance(match_id, str), type(match_id)
            assert isinstance(decline_reason, int), type(decline_reason)
            super(DeclineMatchPayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._match_id = match_id
            self._decline_reason = decline_reason

        @property
        def match_id(self):
            return self._match_id

        @property
        def decline_reason(self):
            return self._decline_reason


class TradePayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     proposal_id, price, quantity, timestamp, ip, port):
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(recipient_trader_id, TraderId), type(recipient_trader_id)
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            assert isinstance(proposal_id, int), type(proposal_id)
            assert isinstance(price, Price), type(price)
            assert isinstance(quantity, Quantity), type(quantity)
            super(TradePayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._proposal_id = proposal_id
            self._price = price
            self._quantity = quantity
            self._ip = ip
            self._port = port

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
        def proposal_id(self):
            return self._proposal_id

        @property
        def price(self):
            return self._price

        @property
        def quantity(self):
            return self._quantity

        @property
        def address(self):
            return SocketAddress(self._ip, self._port)


class DeclinedTradePayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, recipient_trader_id, recipient_order_number,
                     proposal_id, timestamp, decline_reason):
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(recipient_trader_id, TraderId), type(recipient_trader_id)
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            assert isinstance(proposal_id, int), type(proposal_id)
            assert isinstance(decline_reason, int), type(decline_reason)
            super(DeclinedTradePayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._proposal_id = proposal_id
            self._decline_reason = decline_reason

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
        def proposal_id(self):
            return self._proposal_id

        @property
        def decline_reason(self):
            return self._decline_reason


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
                     order_number, recipient_trader_id, recipient_order_number, proposal_id,
                     price, quantity, timestamp):
            assert isinstance(order_trader_id, TraderId), type(order_trader_id)
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(recipient_trader_id, TraderId), type(recipient_trader_id)
            assert isinstance(recipient_order_number, OrderNumber), type(recipient_order_number)
            assert isinstance(proposal_id, int), type(proposal_id)
            assert isinstance(price, Price), type(price)
            assert isinstance(quantity, Quantity), type(quantity)
            super(StartTransactionPayload.Implementation, self).__init__(meta, trader_id, message_number,
                                                                         transaction_trader_id, transaction_number,
                                                                         timestamp)
            self._order_trader_id = order_trader_id
            self._order_number = order_number
            self._recipient_trader_id = recipient_trader_id
            self._recipient_order_number = recipient_order_number
            self._proposal_id = proposal_id
            self._price = price
            self._quantity = quantity

        @property
        def order_trader_id(self):
            return self._order_trader_id

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
        def proposal_id(self):
            return self._proposal_id

        @property
        def price(self):
            return self._price

        @property
        def quantity(self):
            return self._quantity


class WalletInfoPayload(TransactionPayload):
    class Implementation(TransactionPayload.Implementation):
        def __init__(self, meta, trader_id, message_number, transaction_trader_id, transaction_number,
                     incoming_address, outgoing_address, timestamp):
            assert isinstance(incoming_address, WalletAddress), type(incoming_address)
            assert isinstance(outgoing_address, WalletAddress), type(outgoing_address)
            super(WalletInfoPayload.Implementation, self).__init__(meta, trader_id, message_number,
                                                                   transaction_trader_id, transaction_number, timestamp)
            self._incoming_address = incoming_address
            self._outgoing_address = outgoing_address

        @property
        def incoming_address(self):
            return self._incoming_address

        @property
        def outgoing_address(self):
            return self._outgoing_address


class PaymentPayload(TransactionPayload):
    class Implementation(TransactionPayload.Implementation):
        def __init__(self, meta, trader_id, message_number, transaction_trader_id, transaction_number,
                     transferee_quantity, transferee_price, address_from, address_to, payment_id, timestamp, success):
            assert isinstance(transferee_quantity, Quantity), type(transferee_quantity)
            assert isinstance(transferee_price, Price), type(transferee_price)
            assert isinstance(address_from, WalletAddress), type(address_from)
            assert isinstance(address_to, WalletAddress), type(address_to)
            assert isinstance(payment_id, PaymentId), type(payment_id)
            assert isinstance(success, bool), type(success)
            super(PaymentPayload.Implementation, self).__init__(meta, trader_id, message_number,
                                                                transaction_trader_id, transaction_number, timestamp)
            self._transferee_quantity = transferee_quantity
            self._transferee_price = transferee_price
            self._address_from = address_from
            self._address_to = address_to
            self._payment_id = payment_id
            self._success = success

        @property
        def transferee_quantity(self):
            return self._transferee_quantity

        @property
        def transferee_price(self):
            return self._transferee_price

        @property
        def address_from(self):
            return self._address_from

        @property
        def address_to(self):
            return self._address_to

        @property
        def payment_id(self):
            return self._payment_id

        @property
        def success(self):
            return self._success


class OrderStatusRequestPayload(MessagePayload):
    class Implementation(MessagePayload.Implementation):
        def __init__(self, meta, trader_id, message_number, timestamp, order_trader_id, order_number, identifier):
            assert isinstance(order_trader_id, TraderId), type(order_trader_id)
            assert isinstance(order_number, OrderNumber), type(order_number)
            assert isinstance(identifier, int), type(identifier)
            super(OrderStatusRequestPayload.Implementation, self).__init__(meta, trader_id, message_number, timestamp)
            self._order_trader_id = order_trader_id
            self._order_number = order_number
            self._identifier = identifier

        @property
        def order_trader_id(self):
            return self._order_trader_id

        @property
        def order_number(self):
            return self._order_number

        @property
        def identifier(self):
            return self._identifier


class OrderStatusResponsePayload(OfferPayload):
    class Implementation(OfferPayload.Implementation):
        def __init__(self, meta, trader_id, message_number, order_number, price, quantity, timeout, timestamp,
                     traded_quantity, ip, port, identifier):
            assert isinstance(traded_quantity, Quantity), type(traded_quantity)
            super(OrderStatusResponsePayload.Implementation, self).__init__(meta, trader_id, message_number,
                                                                            order_number, price, quantity, timeout,
                                                                            timestamp, ip, port)
            self._traded_quantity = traded_quantity
            self._identifier = identifier

        @property
        def traded_quantity(self):
            return self._traded_quantity

        @property
        def identifier(self):
            return self._identifier
