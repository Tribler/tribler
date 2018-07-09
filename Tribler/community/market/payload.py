from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderNumber, OrderId
from Tribler.community.market.core.payment_id import PaymentId
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

    format_list = ['varlenI', 'f']

    def __init__(self, trader_id, timestamp):
        super(MessagePayload, self).__init__()
        self.trader_id = trader_id
        self.timestamp = timestamp

    def to_pack_list(self):
        data = [('varlenI', str(self.trader_id)),
                ('f', self.timestamp)]

        return data


class InfoPayload(MessagePayload):
    """
    Payload for an info message in the market community.
    """

    format_list = MessagePayload.format_list + ['?']

    def __init__(self, trader_id, timestamp, is_matchmaker):
        super(InfoPayload, self).__init__(trader_id, timestamp)
        self.is_matchmaker = is_matchmaker

    def to_pack_list(self):
        data = super(InfoPayload, self).to_pack_list()
        data.append(('?', self.is_matchmaker))
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, is_matchmaker):
        return InfoPayload(TraderId(trader_id), timestamp, is_matchmaker)


class OfferPayload(MessagePayload):
    """
    Payload for a message with an offer in the market community.
    """

    format_list = MessagePayload.format_list + ['I', 'Q', 'varlenI', 'Q', 'varlenI', 'I', 'Q', 'varlenI', 'I']

    def __init__(self, trader_id, timestamp, order_number, assets, timeout, traded, address):
        super(OfferPayload, self).__init__(trader_id, timestamp)
        self.order_number = order_number
        self.assets = assets
        self.timeout = timeout
        self.traded = traded
        self.address = address

    def to_pack_list(self):
        data = super(OfferPayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('Q', self.assets.first.amount),
                 ('varlenI', self.assets.first.asset_id),
                 ('Q', self.assets.second.amount),
                 ('varlenI', self.assets.second.asset_id),
                 ('I', int(self.timeout)),
                 ('Q', self.traded),
                 ('varlenI', self.address.ip),
                 ('I', self.address.port)]
        return data


class MatchPayload(OfferPayload):
    """
    Payload for a match in the market community.
    """

    format_list = OfferPayload.format_list + ['I', 'Q', 'varlenI', 'varlenI', 'varlenI']

    def __init__(self, trader_id, timestamp, order_number, assets, timeout, traded, address, recipient_order_number,
                 match_quantity, match_trader_id, matchmaker_trader_id, match_id):
        super(MatchPayload, self).__init__(trader_id, timestamp, order_number, assets, timeout, traded, address)
        self.recipient_order_number = recipient_order_number
        self.match_quantity = match_quantity
        self.match_trader_id = match_trader_id
        self.matchmaker_trader_id = matchmaker_trader_id
        self.match_id = match_id

    def to_pack_list(self):
        data = super(MatchPayload, self).to_pack_list()
        data += [('I', int(self.recipient_order_number)),
                 ('Q', self.match_quantity),
                 ('varlenI', str(self.match_trader_id)),
                 ('varlenI', str(self.matchmaker_trader_id)),
                 ('varlenI', self.match_id)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, asset1_amount, asset1_type, asset2_amount,
                         asset2_type, timeout, traded, ip, port, recipient_order_number, match_quantity,
                         match_trader_id, matchmaker_trader_id, match_id):
        return MatchPayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                            AssetPair(AssetAmount(asset1_amount, asset1_type), AssetAmount(asset2_amount, asset2_type)),
                            Timeout(timeout), traded, SocketAddress(ip, port), OrderNumber(recipient_order_number),
                            match_quantity, TraderId(match_trader_id), TraderId(matchmaker_trader_id), match_id)


class AcceptMatchPayload(MessagePayload):
    """
    Payload for an accepted match in the market community.
    """

    format_list = MessagePayload.format_list + ['varlenI', 'Q']

    def __init__(self, trader_id, timestamp, match_id, quantity):
        super(AcceptMatchPayload, self).__init__(trader_id, timestamp)
        self.match_id = match_id
        self.quantity = quantity

    def to_pack_list(self):
        data = super(AcceptMatchPayload, self).to_pack_list()
        data += [('varlenI', self.match_id),
                 ('Q', self.quantity)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, match_id, quantity):
        return AcceptMatchPayload(TraderId(trader_id), Timestamp(timestamp), match_id, quantity)


class DeclineMatchPayload(MessagePayload):
    """
    Payload for a declined match in the market community.
    """

    format_list = MessagePayload.format_list + ['varlenI', 'I']

    def __init__(self, trader_id, timestamp, match_id, decline_reason):
        super(DeclineMatchPayload, self).__init__(trader_id, timestamp)
        self.match_id = match_id
        self.decline_reason = decline_reason

    def to_pack_list(self):
        data = super(DeclineMatchPayload, self).to_pack_list()
        data += [('varlenI', self.match_id),
                 ('I', self.decline_reason)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, match_id, decline_reason):
        return DeclineMatchPayload(TraderId(trader_id), Timestamp(timestamp), match_id, decline_reason)


class TradePayload(MessagePayload):
    """
    Payload that contains a trade in the market community.
    """

    format_list = MessagePayload.format_list + ['I', 'varlenI', 'I', 'I', 'Q',
                                                'varlenI', 'Q', 'varlenI', 'varlenI', 'I']

    def __init__(self, trader_id, timestamp, order_number, recipient_order_id, proposal_id, assets, address):
        super(TradePayload, self).__init__(trader_id, timestamp)
        self.order_number = order_number
        self.recipient_order_id = recipient_order_id
        self.proposal_id = proposal_id
        self.assets = assets
        self.address = address

    def to_pack_list(self):
        data = super(TradePayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('varlenI', str(self.recipient_order_id.trader_id)),
                 ('I', int(self.recipient_order_id.order_number)),
                 ('I', self.proposal_id),
                 ('Q', self.assets.first.amount),
                 ('varlenI', self.assets.first.asset_id),
                 ('Q', self.assets.second.amount),
                 ('varlenI', self.assets.second.asset_id),
                 ('varlenI', self.address.ip),
                 ('I', self.address.port)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, recipient_trader_id, recipient_order_number,
                         proposal_id, asset1_amount, asset1_type, asset2_amount, asset2_type, ip, port):
        return TradePayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                            OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)), proposal_id,
                            AssetPair(AssetAmount(asset1_amount, asset1_type), AssetAmount(asset2_amount, asset2_type)),
                            SocketAddress(ip, port))


class DeclineTradePayload(MessagePayload):

    format_list = MessagePayload.format_list + ['I', 'varlenI', 'I', 'I', 'I']

    def __init__(self, trader_id, timestamp, order_number, recipient_order_id, proposal_id, decline_reason):
        super(DeclineTradePayload, self).__init__(trader_id, timestamp)
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
    def from_unpack_list(cls, trader_id, timestamp, order_number, recipient_trader_id,
                         recipient_order_number, proposal_id, decline_reason):
        return DeclineTradePayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                                   OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)),
                                   proposal_id, decline_reason)


class TransactionPayload(MessagePayload):
    """
    This payload contains a transaction in the market community.
    """

    format_list = MessagePayload.format_list + ['varlenI', 'I']

    def __init__(self, trader_id, timestamp, transaction_id):
        super(TransactionPayload, self).__init__(trader_id, timestamp)
        self.transaction_id = transaction_id

    def to_pack_list(self):
        data = super(TransactionPayload, self).to_pack_list()
        data += [('varlenI', str(self.transaction_id.trader_id)),
                 ('I', int(self.transaction_id.transaction_number))]
        return data


class StartTransactionPayload(TransactionPayload):
    """
    This payload contains a transaction and order information in the market community.
    """

    format_list = TransactionPayload.format_list + ['varlenI', 'I', 'varlenI', 'I', 'I', 'Q', 'varlenI', 'Q', 'varlenI']

    def __init__(self, trader_id, timestamp, transaction_id, order_id, recipient_order_id,
                 proposal_id, assets):
        super(StartTransactionPayload, self).__init__(trader_id, timestamp, transaction_id)
        self.order_id = order_id
        self.recipient_order_id = recipient_order_id
        self.proposal_id = proposal_id
        self.assets = assets

    def to_pack_list(self):
        data = super(StartTransactionPayload, self).to_pack_list()
        data += [('varlenI', str(self.order_id.trader_id)),
                 ('I', int(self.order_id.order_number)),
                 ('varlenI', str(self.recipient_order_id.trader_id)),
                 ('I', int(self.recipient_order_id.order_number)),
                 ('I', self.proposal_id),
                 ('Q', self.assets.first.amount),
                 ('varlenI', self.assets.first.asset_id),
                 ('Q', self.assets.second.amount),
                 ('varlenI', self.assets.second.asset_id)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, tx_trader_id, transaction_number,
                         order_trader_id, order_number, recipient_trader_id, recipient_order_number, proposal_id,
                         asset1_amount, asset1_type, asset2_amount, asset2_type):
        return StartTransactionPayload(TraderId(trader_id), Timestamp(timestamp),
                                       TransactionId(TraderId(tx_trader_id), TransactionNumber(transaction_number)),
                                       OrderId(TraderId(order_trader_id), OrderNumber(order_number)),
                                       OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)),
                                       proposal_id, AssetPair(AssetAmount(asset1_amount, asset1_type),
                                                              AssetAmount(asset2_amount, asset2_type)))


class WalletInfoPayload(TransactionPayload):
    """
    This payload contains wallet information.
    """

    format_list = TransactionPayload.format_list + ['varlenI', 'varlenI']

    def __init__(self, trader_id, timestamp, transaction_id, incoming_address, outgoing_address):
        super(WalletInfoPayload, self).__init__(trader_id, timestamp, transaction_id)
        self.incoming_address = incoming_address
        self.outgoing_address = outgoing_address

    def to_pack_list(self):
        data = super(WalletInfoPayload, self).to_pack_list()
        data += [('varlenI', str(self.incoming_address)),
                 ('varlenI', str(self.outgoing_address))]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, transaction_trader_id, transaction_number,
                         incoming_address, outgoing_address):
        return WalletInfoPayload(TraderId(trader_id), Timestamp(timestamp),
                                 TransactionId(TraderId(transaction_trader_id), TransactionNumber(transaction_number)),
                                 WalletAddress(incoming_address), WalletAddress(outgoing_address))


class PaymentPayload(TransactionPayload):
    """
    This payload contains a payment in the market community.
    """

    format_list = TransactionPayload.format_list + ['Q', 'varlenI', 'varlenI', 'varlenI', 'varlenI', '?']

    def __init__(self, trader_id, timestamp, transaction_id, transferred_assets, address_from,
                 address_to, payment_id, success):
        super(PaymentPayload, self).__init__(trader_id, timestamp, transaction_id)
        self.transferred_assets = transferred_assets
        self.address_from = address_from
        self.address_to = address_to
        self.payment_id = payment_id
        self.success = success

    def to_pack_list(self):
        data = super(PaymentPayload, self).to_pack_list()
        data += [('Q', self.transferred_assets.amount),
                 ('varlenI', self.transferred_assets.asset_id),
                 ('varlenI', str(self.address_from)),
                 ('varlenI', str(self.address_to)),
                 ('varlenI', str(self.payment_id)),
                 ('?', self.success)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, transaction_trader_id, transaction_number,
                         transferred_amount, transferred_type, address_from, address_to, payment_id, success):
        return PaymentPayload(TraderId(trader_id), Timestamp(timestamp),
                              TransactionId(TraderId(transaction_trader_id), TransactionNumber(transaction_number)),
                              AssetAmount(transferred_amount, transferred_type),
                              WalletAddress(address_from), WalletAddress(address_to), PaymentId(payment_id), success)


class OrderStatusRequestPayload(MessagePayload):
    """
    This payload contains a request for an order status.
    """

    format_list = MessagePayload.format_list + ['varlenI', 'I', 'I']

    def __init__(self, trader_id, timestamp, order_id, identifier):
        super(OrderStatusRequestPayload, self).__init__(trader_id, timestamp)
        self.order_id = order_id
        self.identifier = identifier

    def to_pack_list(self):
        data = super(OrderStatusRequestPayload, self).to_pack_list()
        data += [('varlenI', str(self.order_id.trader_id)),
                 ('I', int(self.order_id.order_number)),
                 ('I', self.identifier)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_trader_id, order_number, identifier):
        return OrderStatusRequestPayload(TraderId(trader_id), Timestamp(timestamp),
                                         OrderId(TraderId(order_trader_id), OrderNumber(order_number)), identifier)


class OrderStatusResponsePayload(OfferPayload):
    """
    This payload contains the status of an order in the market community.
    """

    format_list = OfferPayload.format_list + ['I']

    def __init__(self, trader_id, timestamp, order_number, assets, timeout, traded, address, identifier):
        super(OrderStatusResponsePayload, self).__init__(trader_id, timestamp, order_number, assets, timeout,
                                                         traded, address)
        self.identifier = identifier

    def to_pack_list(self):
        data = super(OrderStatusResponsePayload, self).to_pack_list()
        data += [('I', self.identifier)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, asset1_amount, asset1_type, asset2_amount,
                         asset2_type, timeout, traded, ip, port, identifier):
        return OrderStatusResponsePayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                                          AssetPair(AssetAmount(asset1_amount, asset1_type),
                                                    AssetAmount(asset2_amount, asset2_type)),
                                          Timeout(timeout), traded, SocketAddress(ip, port), identifier)


class OrderbookSyncPayload(MessagePayload):
    """
    Payload for synchronization of orders in the market community.
    """

    format_list = MessagePayload.format_list + ['B', 'c', 'varlenI']

    def __init__(self, trader_id, timestamp, bloomfilter):
        super(OrderbookSyncPayload, self).__init__(trader_id, timestamp)
        self.bloomfilter = bloomfilter

    def to_pack_list(self):
        data = super(OrderbookSyncPayload, self).to_pack_list()
        data += [('B', self.bloomfilter.functions),
                 ('c', self.bloomfilter.prefix),
                 ('varlenI', self.bloomfilter.bytes)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, bf_functions, bf_prefix, bf_bytes):
        bloomfilter = BloomFilter(bf_bytes, bf_functions, prefix=bf_prefix)
        return OrderbookSyncPayload(TraderId(trader_id), timestamp, bloomfilter)


class PingPongPayload(MessagePayload):
    """
    Payload for a ping and pong message in the market community.
    """

    format_list = MessagePayload.format_list + ['I']

    def __init__(self, trader_id, timestamp, identifier):
        super(PingPongPayload, self).__init__(trader_id, timestamp)
        self.identifier = identifier

    def to_pack_list(self):
        data = super(PingPongPayload, self).to_pack_list()
        data += [('I', self.identifier)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, identifier):
        return PingPongPayload(TraderId(trader_id), timestamp, identifier)
