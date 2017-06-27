from struct import pack, unpack_from

from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionNumber
from Tribler.community.market.core.ttl import Ttl
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.wallet import INV_ASSET_MAP
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


class MarketConversion(BinaryConversion):
    """Class that handles all encoding and decoding of Market messages."""

    def __init__(self, community):
        super(MarketConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"ask"),
                                 self._encode_offer, self._decode_offer)
        self.define_meta_message(chr(2), community.get_meta_message(u"bid"),
                                 self._encode_offer, self._decode_offer)
        self.define_meta_message(chr(3), community.get_meta_message(u"cancel-order"),
                                 self._encode_cancel_order, self._decode_cancel_order)
        self.define_meta_message(chr(4), community.get_meta_message(u"offer-sync"),
                                 self._encode_offer_sync, self._decode_offer_sync)
        self.define_meta_message(chr(5), community.get_meta_message(u"proposed-trade"),
                                 self._encode_proposed_trade, self._decode_proposed_trade)
        self.define_meta_message(chr(6), community.get_meta_message(u"declined-trade"),
                                 self._encode_declined_trade, self._decode_declined_trade)
        self.define_meta_message(chr(7), community.get_meta_message(u"counter-trade"),
                                 self._encode_proposed_trade, self._decode_proposed_trade)
        self.define_meta_message(chr(8), community.get_meta_message(u"start-transaction"),
                                 self._encode_start_transaction, self._decode_start_transaction)
        self.define_meta_message(chr(9), community.get_meta_message(u"wallet-info"),
                                 self._encode_wallet_info, self._decode_wallet_info)
        self.define_meta_message(chr(10), community.get_meta_message(u"payment"),
                                 self._encode_payment, self._decode_payment)
        self.define_meta_message(chr(11), community.get_meta_message(u"end-transaction"),
                                 self._encode_transaction, self._decode_transaction)

    def _encode_introduction_request(self, message):
        data = BinaryConversion._encode_introduction_request(self, message)

        if message.payload.orders_bloom_filter:
            data.extend((pack('!BH', message.payload.orders_bloom_filter.functions,
                              message.payload.orders_bloom_filter.size), message.payload.orders_bloom_filter.prefix,
                         message.payload.orders_bloom_filter.bytes))
        return data

    def _decode_introduction_request(self, placeholder, offset, data):
        offset, payload = BinaryConversion._decode_introduction_request(self, placeholder, offset, data)

        if len(data) > offset:
            if len(data) < offset + 5:
                raise DropPacket("Insufficient packet size")

            functions, size = unpack_from('!BH', data, offset)
            offset += 3

            prefix = data[offset]
            offset += 1

            if functions <= 0 or size <= 0 or size % 8 != 0:
                raise DropPacket("Invalid bloom filter")

            length = size / 8
            if length != len(data) - offset:
                raise DropPacket("Invalid number of bytes available (irq) %d, %d, %d" %
                                 (length, len(data) - offset, size))

            orders_bloom_filter = BloomFilter(data[offset:offset + length], functions, prefix=prefix)
            offset += length

            payload.set_orders_bloom_filter(orders_bloom_filter)

        return offset, payload

    def _decode_payload(self, placeholder, offset, data, types):
        try:
            offset, payload = decode(data, offset)
        except (ValueError, AssertionError, KeyError):
            raise DropPacket("Unable to decode the payload")

        args = []
        cur_ind = 0
        for arg_type in types:
            try:
                if arg_type == Price or arg_type == Quantity:  # They contain an additional wallet ID
                    args.append(arg_type(payload[cur_ind], INV_ASSET_MAP[payload[cur_ind + 1]]))
                    cur_ind += 2
                elif arg_type == str or arg_type == int:
                    args.append(payload[cur_ind])
                    cur_ind += 1
                else:
                    args.append(arg_type(payload[cur_ind]))
                    cur_ind += 1
            except (ValueError, KeyError):
                raise DropPacket("Invalid '" + arg_type.__name__ + "' type")
        return offset, placeholder.meta.payload.implement(*args)

    def _encode_offer(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), int(payload.order_number), float(payload.price),
            int(payload.price.int_wallet_id), float(payload.quantity), int(payload.quantity.int_wallet_id),
            float(payload.timeout), float(payload.timestamp), str(payload.public_key), str(payload.signature),
            int(payload.ttl), str(payload.address.ip), int(payload.address.port)
        ))
        return packet,

    def _decode_offer(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, Price, Quantity, Timeout, Timestamp,
                                     str, str, Ttl, str, int])

    def _encode_cancel_order(self, message):
        payload = message.payload
        packet = encode((str(payload.trader_id), str(payload.message_number), float(payload.timestamp),
                         int(payload.order_number), int(payload.ttl)))
        return packet,

    def _decode_cancel_order(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data, [TraderId, MessageNumber, Timestamp, OrderNumber, Ttl])

    def _encode_offer_sync(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), int(payload.order_number), float(payload.price),
            int(payload.price.int_wallet_id), float(payload.quantity), int(payload.quantity.int_wallet_id),
            float(payload.timeout), float(payload.timestamp), str(payload.public_key), str(payload.signature),
            int(payload.ttl), str(payload.address.ip), int(payload.address.port), bool(payload.is_ask)
        ))
        return packet,

    def _decode_offer_sync(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, Price, Quantity, Timeout, Timestamp,
                                     str, str, Ttl, str, int, bool])

    def _encode_proposed_trade(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), int(payload.order_number),
            str(payload.recipient_trader_id), int(payload.recipient_order_number), payload.proposal_id,
            float(payload.price), int(payload.price.int_wallet_id), float(payload.quantity),
            int(payload.quantity.int_wallet_id), float(payload.timestamp), str(payload.address.ip),
            int(payload.address.port)
        ))
        return packet,

    def _decode_proposed_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, int, Price, Quantity,
                                     Timestamp, str, int])

    def _encode_declined_trade(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), int(payload.order_number),
            str(payload.recipient_trader_id), int(payload.recipient_order_number), payload.proposal_id,
            float(payload.timestamp)
        ))
        return packet,

    def _decode_declined_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, int, Timestamp])

    def _encode_start_transaction(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            int(payload.transaction_number), str(payload.order_trader_id), int(payload.order_number),
            str(payload.recipient_trader_id), int(payload.recipient_order_number), payload.proposal_id,
            float(payload.price), int(payload.price.int_wallet_id), float(payload.quantity),
            int(payload.quantity.int_wallet_id), float(payload.timestamp)
        ))
        return packet,

    def _decode_start_transaction(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, TraderId, OrderNumber,
                                     TraderId, OrderNumber, int, Price, Quantity, Timestamp])

    def _encode_transaction(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            int(payload.transaction_number), float(payload.timestamp)
        ))
        return packet,

    def _decode_transaction(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, Timestamp])

    def _encode_wallet_info(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            int(payload.transaction_number), str(payload.incoming_address), str(payload.outgoing_address),
            float(payload.timestamp)
        ))
        return packet,

    def _decode_wallet_info(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber,
                                     WalletAddress, WalletAddress, Timestamp])

    def _encode_payment(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            int(payload.transaction_number), float(payload.transferee_quantity),
            int(payload.transferee_quantity.int_wallet_id), float(payload.transferee_price),
            int(payload.transferee_price.int_wallet_id), str(payload.address_from), str(payload.address_to),
            str(payload.payment_id), float(payload.timestamp), bool(payload.success)
        ))
        return packet,

    def _decode_payment(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, Quantity, Price,
                                     WalletAddress, WalletAddress, PaymentId, Timestamp, bool])
