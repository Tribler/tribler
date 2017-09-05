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
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.wallet import INV_ASSET_MAP
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


class MarketConversion(BinaryConversion):
    """Class that handles all encoding and decoding of Market messages."""

    def __init__(self, community):
        super(MarketConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(6), community.get_meta_message(u"info"),
                                 self._encode_info, self._decode_info)
        self.define_meta_message(chr(7), community.get_meta_message(u"match"),
                                 self._encode_match, self._decode_match)
        self.define_meta_message(chr(8), community.get_meta_message(u"accept-match"),
                                 self._encode_accept_match, self._decode_accept_match)
        self.define_meta_message(chr(9), community.get_meta_message(u"decline-match"),
                                 self._encode_decline_match, self._decode_decline_match)
        self.define_meta_message(chr(10), community.get_meta_message(u"proposed-trade"),
                                 self._encode_proposed_trade, self._decode_proposed_trade)
        self.define_meta_message(chr(11), community.get_meta_message(u"declined-trade"),
                                 self._encode_declined_trade, self._decode_declined_trade)
        self.define_meta_message(chr(12), community.get_meta_message(u"counter-trade"),
                                 self._encode_proposed_trade, self._decode_proposed_trade)
        self.define_meta_message(chr(13), community.get_meta_message(u"start-transaction"),
                                 self._encode_start_transaction, self._decode_start_transaction)
        self.define_meta_message(chr(14), community.get_meta_message(u"wallet-info"),
                                 self._encode_wallet_info, self._decode_wallet_info)
        self.define_meta_message(chr(15), community.get_meta_message(u"payment"),
                                 self._encode_payment, self._decode_payment)
        self.define_meta_message(chr(16), community.get_meta_message(u"order-status-request"),
                                 self._encode_order_status_request, self._decode_order_status_request)
        self.define_meta_message(chr(17), community.get_meta_message(u"order-status-response"),
                                 self._encode_order_status_response, self._decode_order_status_response)

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

    def _encode_info(self, message):
        payload = message.payload
        packet = encode((str(payload.trader_id), str(payload.message_number), float(payload.timestamp),
                         bool(payload.is_matchmaker)))
        return packet,

    def _decode_info(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, Timestamp, bool])

    def _encode_match(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), int(payload.order_number), float(payload.price),
            int(payload.price.int_wallet_id), float(payload.quantity), int(payload.quantity.int_wallet_id),
            float(payload.timeout), float(payload.timestamp), str(payload.address.ip),
            int(payload.address.port), int(payload.recipient_order_number), float(payload.match_quantity),
            int(payload.match_quantity.int_wallet_id), str(payload.match_trader_id),
            str(payload.matchmaker_trader_id), str(payload.match_id)
        ))
        return packet,

    def _decode_match(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, Price, Quantity, Timeout, Timestamp,
                                     str, int, OrderNumber, Quantity, TraderId, TraderId, str])

    def _encode_accept_match(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), float(payload.timestamp), str(payload.match_id),
            float(payload.quantity), int(payload.quantity.int_wallet_id)
        ))
        return packet,

    def _decode_accept_match(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data, [TraderId, MessageNumber, Timestamp, str, Quantity])

    def _encode_decline_match(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), float(payload.timestamp), str(payload.match_id),
            int(payload.decline_reason)
        ))
        return packet,

    def _decode_decline_match(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data, [TraderId, MessageNumber, Timestamp, str, int])

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
            float(payload.timestamp), int(payload.decline_reason)
        ))
        return packet,

    def _decode_declined_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, int, Timestamp, int])

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

    def _encode_order_status_request(self, message):
        payload = message.payload
        packet = encode((str(payload.trader_id), str(payload.message_number), float(payload.timestamp),
                         str(payload.order_trader_id), int(payload.order_number), payload.identifier))
        return packet,

    def _decode_order_status_request(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, Timestamp, TraderId, OrderNumber, int])

    def _encode_order_status_response(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), int(payload.order_number), float(payload.price),
            int(payload.price.int_wallet_id), float(payload.quantity), int(payload.quantity.int_wallet_id),
            float(payload.timeout), float(payload.timestamp), float(payload.traded_quantity),
            int(payload.traded_quantity.int_wallet_id), str(payload.address.ip), int(payload.address.port),
            int(payload.identifier)
        ))
        return packet,

    def _decode_order_status_response(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, Price, Quantity, Timeout, Timestamp,
                                     Quantity, str, int, int])
