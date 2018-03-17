from Tribler.community.market.core.message import MessageId, TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber, OrderId
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.socket_address import SocketAddress
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionId, TransactionNumber
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.pyipv8.ipv8.deprecated.bloomfilter import BloomFilter
from Tribler.pyipv8.ipv8.deprecated.payload import Payload


class MessagePayload(Payload):
    """
    Payload for a generic message in the market community.
    """

    format_list = ['varlenI', 'I', 'f']

    def __init__(self, message_id, timestamp):
        super(MessagePayload, self).__init__()
        self.message_id = message_id
        self.timestamp = timestamp

    def to_pack_list(self):
        data = [('varlenI', str(self.message_id.trader_id)),
                ('I', int(self.message_id.message_number)),
                ('f', self.timestamp)]

        return data

    @property
    def trader_id(self):
        return self.message_id.trader_id

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp):
        return MessagePayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), timestamp)


class InfoPayload(MessagePayload):
    """
    Payload for an info message in the market community.
    """

    format_list = ['varlenI', 'I', 'f', '?']

    def __init__(self, message_id, timestamp, is_matchmaker):
        super(InfoPayload, self).__init__(message_id, timestamp)
        self.is_matchmaker = is_matchmaker

    def to_pack_list(self):
        data = super(InfoPayload, self).to_pack_list()
        data.append(('?', self.is_matchmaker))
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, is_matchmaker):
        return InfoPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), timestamp, is_matchmaker)


class OfferPayload(MessagePayload):
    """
    Payload for a message with an offer in the market community.
    """

    format_list = ['varlenI', 'I', 'f', 'I', 'f', 'varlenI', 'f', 'varlenI', 'f', 'varlenI', 'I']

    def __init__(self, message_id, timestamp, order_number, price, quantity, timeout, address):
        super(OfferPayload, self).__init__(message_id, timestamp)
        self.order_number = order_number
        self.price = price
        self.quantity = quantity
        self.timeout = timeout
        self.address = address

    def to_pack_list(self):
        data = super(OfferPayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('f', float(self.price)),
                 ('varlenI', self.price.wallet_id),
                 ('f', float(self.quantity)),
                 ('varlenI', self.quantity.wallet_id),
                 ('f', float(self.timeout)),
                 ('varlenI', self.address.ip),
                 ('I', self.address.port)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, order_number, price, price_type, quantity,
                         quantity_type, timeout, ip, port):
        return OfferPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                            OrderNumber(order_number), Price(price, price_type), Quantity(quantity, quantity_type),
                            Timeout(timeout), SocketAddress(ip, port))


class MatchPayload(OfferPayload):
    """
    Payload for a match in the market community.
    """

    format_list = OfferPayload.format_list + ['I', 'f', 'varlenI', 'varlenI', 'varlenI', 'varlenI']

    def __init__(self, message_id, timestamp, order_number, price, quantity, timeout, address, recipient_order_number,
                 match_quantity, match_trader_id, matchmaker_trader_id, match_id):
        super(MatchPayload, self).__init__(message_id, timestamp, order_number, price, quantity, timeout, address)
        self.recipient_order_number = recipient_order_number
        self.match_quantity = match_quantity
        self.match_trader_id = match_trader_id
        self.matchmaker_trader_id = matchmaker_trader_id
        self.match_id = match_id

    def to_pack_list(self):
        data = super(MatchPayload, self).to_pack_list()
        data += [('I', int(self.recipient_order_number)),
                 ('f', float(self.match_quantity)),
                 ('varlenI', self.match_quantity.wallet_id),
                 ('varlenI', str(self.match_trader_id)),
                 ('varlenI', str(self.matchmaker_trader_id)),
                 ('varlenI', self.match_id)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, order_number, price, price_type, quantity,
                         quantity_type, timeout, ip, port, recipient_order_number, match_quantity, match_quantity_type,
                         match_trader_id, matchmaker_trader_id, match_id):
        return MatchPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                            OrderNumber(order_number), Price(price, price_type), Quantity(quantity, quantity_type),
                            Timeout(timeout), SocketAddress(ip, port), OrderNumber(recipient_order_number),
                            Quantity(match_quantity, match_quantity_type), TraderId(match_trader_id),
                            TraderId(matchmaker_trader_id), match_id)


class AcceptMatchPayload(MessagePayload):
    """
    Payload for an accepted match in the market community.
    """

    format_list = ['varlenI', 'I', 'f', 'varlenI', 'f', 'varlenI']

    def __init__(self, message_id, timestamp, match_id, quantity):
        super(AcceptMatchPayload, self).__init__(message_id, timestamp)
        self.match_id = match_id
        self.quantity = quantity

    def to_pack_list(self):
        data = super(AcceptMatchPayload, self).to_pack_list()
        data += [('varlenI', self.match_id),
                 ('f', float(self.quantity)),
                 ('varlenI', self.quantity.wallet_id)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, match_id, quantity, quantity_type):
        return AcceptMatchPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                                  match_id, Quantity(quantity, quantity_type))


class DeclineMatchPayload(MessagePayload):
    """
    Payload for a declined match in the market community.
    """

    format_list = ['varlenI', 'I', 'f', 'varlenI', 'I']

    def __init__(self, message_id, timestamp, match_id, decline_reason):
        super(DeclineMatchPayload, self).__init__(message_id, timestamp)
        self.match_id = match_id
        self.decline_reason = decline_reason

    def to_pack_list(self):
        data = super(DeclineMatchPayload, self).to_pack_list()
        data += [('varlenI', self.match_id),
                 ('I', self.decline_reason)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, match_id, decline_reason):
        return DeclineMatchPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                                   match_id, decline_reason)


class TradePayload(MessagePayload):
    """
    Payload that contains a trade in the market community.
    """

    format_list = ['varlenI', 'I', 'f', 'I', 'varlenI', 'I', 'I', 'f', 'varlenI', 'f', 'varlenI', 'varlenI', 'I']

    def __init__(self, message_id, timestamp, order_number, recipient_order_id, proposal_id, price, quantity, address):
        super(TradePayload, self).__init__(message_id, timestamp)
        self.order_number = order_number
        self.recipient_order_id = recipient_order_id
        self.proposal_id = proposal_id
        self.price = price
        self.quantity = quantity
        self.address = address

    def to_pack_list(self):
        data = super(TradePayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('varlenI', str(self.recipient_order_id.trader_id)),
                 ('I', int(self.recipient_order_id.order_number)),
                 ('I', self.proposal_id),
                 ('f', float(self.price)),
                 ('varlenI', self.price.wallet_id),
                 ('f', float(self.quantity)),
                 ('varlenI', self.quantity.wallet_id),
                 ('varlenI', self.address.ip),
                 ('I', self.address.port)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, order_number, recipient_trader_id,
                         recipient_order_number, proposal_id, price, price_type, quantity, quantity_type, ip, port):
        return TradePayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                            OrderNumber(order_number),
                            OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)),
                            proposal_id, Price(price, price_type),
                            Quantity(quantity, quantity_type), SocketAddress(ip, port))


class DeclineTradePayload(MessagePayload):

    format_list = ['varlenI', 'I', 'f', 'I', 'varlenI', 'I', 'I', 'I']

    def __init__(self, message_id, timestamp, order_number, recipient_order_id, proposal_id, decline_reason):
        super(DeclineTradePayload, self).__init__(message_id, timestamp)
        self.order_number = order_number
        self.recipient_order_id = recipient_order_id
        self.proposal_id = proposal_id
        self.decline_reason = decline_reason

    def to_pack_list(self):
        data = super(DeclineTradePayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('varlenI', str(self.recipient_order_id.trader_id)),
                 ('I', int(self.recipient_order_id.order_number)),
                 ('I', self.proposal_id),
                 ('I', self.decline_reason)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, order_number, recipient_trader_id,
                         recipient_order_number, proposal_id, decline_reason):
        return DeclineTradePayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                                   OrderNumber(order_number),
                                   OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)),
                                   proposal_id, decline_reason)


class TransactionPayload(MessagePayload):
    """
    This payload contains a transaction in the market community.
    """

    format_list = ['varlenI', 'I', 'f', 'varlenI', 'I']

    def __init__(self, message_id, timestamp, transaction_id):
        super(TransactionPayload, self).__init__(message_id, timestamp)
        self.transaction_id = transaction_id

    def to_pack_list(self):
        data = super(TransactionPayload, self).to_pack_list()
        data += [('varlenI', str(self.transaction_id.trader_id)),
                 ('I', int(self.transaction_id.transaction_number))]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, transaction_trader_id, transaction_number):
        return TransactionPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                                  TransactionId(TraderId(transaction_trader_id), TransactionNumber(transaction_number)))


class StartTransactionPayload(TransactionPayload):
    """
    This payload contains a transaction and order information in the market community.
    """

    format_list = ['varlenI', 'I', 'f', 'varlenI', 'I', 'varlenI', 'I', 'varlenI', 'I', 'I', 'f',
                   'varlenI', 'f', 'varlenI']

    def __init__(self, message_id, timestamp, transaction_id, order_id, recipient_order_id,
                 proposal_id, price, quantity):
        super(StartTransactionPayload, self).__init__(message_id, timestamp, transaction_id)
        self.order_id = order_id
        self.recipient_order_id = recipient_order_id
        self.proposal_id = proposal_id
        self.price = price
        self.quantity = quantity

    def to_pack_list(self):
        data = super(StartTransactionPayload, self).to_pack_list()
        data += [('varlenI', str(self.order_id.trader_id)),
                 ('I', int(self.order_id.order_number)),
                 ('varlenI', str(self.recipient_order_id.trader_id)),
                 ('I', int(self.recipient_order_id.order_number)),
                 ('I', self.proposal_id),
                 ('f', float(self.price)),
                 ('varlenI', self.price.wallet_id),
                 ('f', float(self.quantity)),
                 ('varlenI', self.quantity.wallet_id)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, transaction_trader_id, transaction_number,
                         order_trader_id, order_number, recipient_trader_id, recipient_order_number, proposal_id,
                         price, price_type, quantity, quantity_type):
        return StartTransactionPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)),
                                       Timestamp(timestamp), TransactionId(TraderId(transaction_trader_id),
                                                                           TransactionNumber(transaction_number)),
                                       OrderId(TraderId(order_trader_id), OrderNumber(order_number)),
                                       OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)),
                                       proposal_id, Price(price, price_type), Quantity(quantity, quantity_type))


class WalletInfoPayload(TransactionPayload):
    """
    This payload contains wallet information.
    """

    format_list = TransactionPayload.format_list + ['varlenI', 'varlenI']

    def __init__(self, message_id, timestamp, transaction_id, incoming_address, outgoing_address):
        super(WalletInfoPayload, self).__init__(message_id, timestamp, transaction_id)
        self.incoming_address = incoming_address
        self.outgoing_address = outgoing_address

    def to_pack_list(self):
        data = super(WalletInfoPayload, self).to_pack_list()
        data += [('varlenI', str(self.incoming_address)),
                 ('varlenI', str(self.outgoing_address))]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, transaction_trader_id, transaction_number,
                         incoming_address, outgoing_address):
        return WalletInfoPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                                 TransactionId(TraderId(transaction_trader_id), TransactionNumber(transaction_number)),
                                 WalletAddress(incoming_address), WalletAddress(outgoing_address))


class PaymentPayload(TransactionPayload):
    """
    This payload contains a payment in the market community.
    """

    format_list = TransactionPayload.format_list + ['f', 'varlenI', 'f', 'varlenI', 'varlenI', 'varlenI',
                                                    'varlenI', '?']

    def __init__(self, message_id, timestamp, transaction_id, transferee_quantity, transferee_price, address_from,
                 address_to, payment_id, success):
        super(PaymentPayload, self).__init__(message_id, timestamp, transaction_id)
        self.transferee_quantity = transferee_quantity
        self.transferee_price = transferee_price
        self.address_from = address_from
        self.address_to = address_to
        self.payment_id = payment_id
        self.success = success

    def to_pack_list(self):
        data = super(PaymentPayload, self).to_pack_list()
        data += [('f', float(self.transferee_quantity)),
                 ('varlenI', self.transferee_quantity.wallet_id),
                 ('f', float(self.transferee_price)),
                 ('varlenI', self.transferee_price.wallet_id),
                 ('varlenI', str(self.address_from)),
                 ('varlenI', str(self.address_to)),
                 ('varlenI', str(self.payment_id)),
                 ('?', self.success)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, transaction_trader_id, transaction_number,
                         transferee_quantity, transferee_quantity_type, transferee_price, transferee_price_type,
                         address_from, address_to, payment_id, success):
        return PaymentPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), Timestamp(timestamp),
                              TransactionId(TraderId(transaction_trader_id), TransactionNumber(transaction_number)),
                              Quantity(transferee_quantity, transferee_quantity_type),
                              Price(transferee_price, transferee_price_type),
                              WalletAddress(address_from), WalletAddress(address_to), PaymentId(payment_id),
                              success)


class OrderStatusRequestPayload(MessagePayload):
    """
    This payload contains a request for an order status.
    """

    format_list = ['varlenI', 'I', 'f', 'varlenI', 'I', 'I']

    def __init__(self, message_id, timestamp, order_id, identifier):
        super(OrderStatusRequestPayload, self).__init__(message_id, timestamp)
        self.order_id = order_id
        self.identifier = identifier

    def to_pack_list(self):
        data = super(OrderStatusRequestPayload, self).to_pack_list()
        data += [('varlenI', str(self.order_id.trader_id)),
                 ('I', int(self.order_id.order_number)),
                 ('I', self.identifier)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, order_trader_id, order_number, identifier):
        return OrderStatusRequestPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)),
                                         Timestamp(timestamp),
                                         OrderId(TraderId(order_trader_id), OrderNumber(order_number)), identifier)


class OrderStatusResponsePayload(OfferPayload):
    """
    This payload contains the status of an order in the market community.
    """

    format_list = OfferPayload.format_list + ['f', 'varlenI', 'I']

    def __init__(self, message_id, timestamp, order_number, price, quantity, timeout, address,
                 traded_quantity, identifier):
        super(OrderStatusResponsePayload, self).__init__(message_id, timestamp, order_number, price, quantity,
                                                         timeout, address)
        self.traded_quantity = traded_quantity
        self.identifier = identifier

    def to_pack_list(self):
        data = super(OrderStatusResponsePayload, self).to_pack_list()
        data += [('f', float(self.traded_quantity)),
                 ('varlenI', self.traded_quantity.wallet_id),
                 ('I', self.identifier)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, order_number, price, price_type, quantity,
                         quantity_type, timeout, ip, port, traded_quantity, traded_quantity_type, identifier):
        return OrderStatusResponsePayload(MessageId(TraderId(trader_id), MessageNumber(message_number)),
                                          Timestamp(timestamp), OrderNumber(order_number), Price(price, price_type),
                                          Quantity(quantity, quantity_type), Timeout(timeout), SocketAddress(ip, port),
                                          Quantity(traded_quantity, traded_quantity_type), identifier)


class OrderbookSyncPayload(MessagePayload):
    """
    Payload for synchronization of orders in the market community.
    """

    format_list = ['varlenI', 'I', 'f', 'B', 'c', 'varlenI']

    def __init__(self, message_id, timestamp, bloomfilter):
        super(OrderbookSyncPayload, self).__init__(message_id, timestamp)
        self.message_id = message_id
        self.timestamp = timestamp
        self.bloomfilter = bloomfilter

    def to_pack_list(self):
        data = [('varlenI', str(self.message_id.trader_id)),
                ('I', int(self.message_id.message_number)),
                ('f', self.timestamp),
                ('B', self.bloomfilter.functions),
                ('c', self.bloomfilter.prefix),
                ('varlenI', self.bloomfilter.bytes)]

        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, bf_functions, bf_prefix, bf_bytes):
        bloomfilter = BloomFilter(bf_bytes, bf_functions, prefix=bf_prefix)
        return OrderbookSyncPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), timestamp,
                                    bloomfilter)


class PingPongPayload(MessagePayload):
    """
    Payload for a ping and pong message in the market community.
    """

    format_list = ['varlenI', 'I', 'f', 'I']

    def __init__(self, message_id, timestamp, identifier):
        super(PingPongPayload, self).__init__(message_id, timestamp)
        self.message_id = message_id
        self.timestamp = timestamp
        self.identifier = identifier

    def to_pack_list(self):
        data = [('varlenI', str(self.message_id.trader_id)),
                ('I', int(self.message_id.message_number)),
                ('f', self.timestamp),
                ('I', self.identifier)]

        return data

    @classmethod
    def from_unpack_list(cls, trader_id, message_number, timestamp, identifier):
        return PingPongPayload(MessageId(TraderId(trader_id), MessageNumber(message_number)), timestamp, identifier)
