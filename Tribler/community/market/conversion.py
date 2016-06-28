from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket
from core.bitcoin_address import BitcoinAddress
from core.message import TraderId, MessageNumber
from core.order import OrderNumber
from core.price import Price
from core.quantity import Quantity
from core.timeout import Timeout
from core.timestamp import Timestamp
from core.transaction import TransactionNumber, TransactionId
from ttl import Ttl


class MarketConversion(BinaryConversion):
    """Class that handles all encoding and decoding of Market messages."""

    def __init__(self, community):
        super(MarketConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"ask"),
                                 self._encode_offer, self._decode_offer)
        self.define_meta_message(chr(2), community.get_meta_message(u"bid"),
                                 self._encode_offer, self._decode_offer)
        self.define_meta_message(chr(3), community.get_meta_message(u"proposed-trade"),
                                 self._encode_proposed_trade, self._decode_proposed_trade)
        self.define_meta_message(chr(4), community.get_meta_message(u"accepted-trade"),
                                 self._encode_accepted_trade, self._decode_accepted_trade)
        self.define_meta_message(chr(5), community.get_meta_message(u"declined-trade"),
                                 self._encode_declined_trade, self._decode_declined_trade)
        self.define_meta_message(chr(6), community.get_meta_message(u"counter-trade"),
                                 self._encode_proposed_trade, self._decode_proposed_trade)
        self.define_meta_message(chr(7), community.get_meta_message(u"start-transaction"),
                                 self._encode_start_transaction, self._decode_start_transaction)
        self.define_meta_message(chr(8), community.get_meta_message(u"continue-transaction"),
                                 self._encode_transaction, self._decode_transaction)
        self.define_meta_message(chr(9), community.get_meta_message(u"multi-chain-payment"),
                                 self._encode_multi_chain_payment, self._decode_multi_chain_payment)
        self.define_meta_message(chr(10), community.get_meta_message(u"bitcoin-payment"),
                                 self._encode_bitcoin_payment, self._decode_bitcoin_payment)
        self.define_meta_message(chr(11), community.get_meta_message(u"end-transaction"),
                                 self._encode_transaction, self._decode_transaction)

    def _decode_payload(self, placeholder, offset, data, types):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not isinstance(payload, tuple):
            raise DropPacket("Invalid payload type")

        if not len(payload) == len(types):
            raise DropPacket("Invalid payload length")

        args = []
        for i, arg_type in enumerate(types):
            try:
                if arg_type == Price or arg_type == Quantity:
                    args.append(arg_type.from_mil(payload[i]))
                elif arg_type == str or arg_type == int:
                    args.append(payload[i])
                else:
                    args.append(arg_type(payload[i]))
            except ValueError:
                raise DropPacket("Invalid '" + arg_type.__name__ + "' type")
        return offset, placeholder.meta.payload.implement(*args)

    def _encode_offer(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number), int(payload.price),
            int(payload.quantity), float(payload.timeout), float(payload.timestamp), int(payload.ttl),
            str(payload.address.ip), int(payload.address.port)
        ))
        return packet,

    def _decode_offer(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, Price, Quantity, Timeout, Timestamp, Ttl,
                                     str, int])

    def _encode_proposed_trade(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number),
            str(payload.recipient_trader_id), str(payload.recipient_order_number), int(payload.price),
            int(payload.quantity), float(payload.timestamp)
        ))
        return packet,

    def _decode_proposed_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, Price, Quantity,
                                     Timestamp])

    def _encode_accepted_trade(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number),
            str(payload.recipient_trader_id), str(payload.recipient_order_number), int(payload.price),
            int(payload.quantity), float(payload.timestamp), int(payload.ttl)
        ))
        return packet,

    def _decode_accepted_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, Price, Quantity,
                                     Timestamp, Ttl])

    def _encode_declined_trade(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number),
            str(payload.recipient_trader_id), str(payload.recipient_order_number), float(payload.timestamp)
        ))
        return packet,

    def _decode_declined_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, Timestamp])

    def _encode_start_transaction(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), str(payload.order_trader_id), str(payload.order_number),
            str(payload.trade_message_number), float(payload.timestamp)
        ))
        return packet,

    def _decode_start_transaction(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, TraderId, OrderNumber,
                                     MessageNumber, Timestamp])

    def _encode_transaction(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), float(payload.timestamp)
        ))
        return packet,

    def _decode_transaction(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, Timestamp])

    def _encode_multi_chain_payment(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), str(payload.bitcoin_address), int(payload.transferor_quantity),
            int(payload.transferee_price), float(payload.timestamp)
        ))
        return packet,

    def _decode_multi_chain_payment(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, BitcoinAddress, Quantity,
                                     Price, Timestamp])

    def _encode_bitcoin_payment(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), str(payload.bitcoin_address), int(payload.price), float(payload.timestamp)
        ))
        return packet,

    def _decode_bitcoin_payment(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, BitcoinAddress, Price,
                                     Timestamp])
