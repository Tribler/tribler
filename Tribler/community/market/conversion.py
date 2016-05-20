from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


class MarketConversion(BinaryConversion):
    def __init__(self, community):
        super(MarketConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"ask"), self._encode_offer, self._decode_offer)
        self.define_meta_message(chr(2), community.get_meta_message(u"bid"), self._encode_offer, self._decode_offer)
        self.define_meta_message(chr(3), community.get_meta_message(u"proposed-trade"), self._encode_proposed_trade,
                                 self._decode_proposed_trade)
        self.define_meta_message(chr(4), community.get_meta_message(u"accepted-trade"), self._encode_accepted_trade,
                                 self._decode_accepted_trade)
        self.define_meta_message(chr(5), community.get_meta_message(u"declined-trade"), self._encode_declined_trade,
                                 self._decode_declined_trade)
        self.define_meta_message(chr(6), community.get_meta_message(u"counter-trade"), self._encode_proposed_trade,
                                 self._decode_proposed_trade)

    def _encode_offer(self, message):
        packet = encode((
            message.payload.trader_id,
            message.payload.message_number,
            message.payload.order_number,
            message.payload.price,
            message.payload.quantity,
            message.payload.timeout,
            message.payload.timestamp,
            message.payload.ttl,
            message.payload.address
        ))
        return packet,

    def _decode_offer(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the offer-payload")

        if not isinstance(payload, tuple):
            raise DropPacket("Invalid payload type")

        trader_id, message_number, order_number, price, quantity, timeout, timestamp, ttl, address = payload

        if not isinstance(trader_id, str):
            raise DropPacket("Invalid 'trader_id' type")
        if not isinstance(message_number, str):
            raise DropPacket("Invalid 'message_number' type")
        if not isinstance(order_number, str):
            raise DropPacket("Invalid 'message_number' type")
        if not isinstance(price, int):
            raise DropPacket("Invalid 'price' type")
        if not isinstance(quantity, int):
            raise DropPacket("Invalid 'quantity' type")
        if not isinstance(timeout, float):
            raise DropPacket("Invalid 'timeout' type")
        if not isinstance(timestamp, float):
            raise DropPacket("Invalid 'timestamp' type")
        if not isinstance(ttl, int) and ttl >= 0:
            raise DropPacket("Invalid 'ttl' type")
        if not (isinstance(address, str) and isinstance(address[0], str) and isinstance(address[1], int)):
            raise DropPacket("Invalid 'address' type")

        return offset, placeholder.meta.payload.implement(
            trader_id,
            message_number,
            order_number,
            price,
            quantity,
            timeout,
            timestamp,
            ttl,
            address
        )

    def _encode_proposed_trade(self, message):
        packet = encode((
            message.payload.trader_id,
            message.payload.message_number,
            message.payload.order_number,
            message.payload.recipient_trader_id,
            message.payload.recipient_order_number,
            message.payload.price,
            message.payload.quantity,
            message.payload.timestamp,
            message.payload.quick
        ))
        return packet,

    def _decode_proposed_trade(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the proposed-trade-payload")

        if not isinstance(payload, tuple):
            raise DropPacket("Invalid payload type")

        trader_id, message_number, order_number, recipient_trader_id, recipient_order_number, price, quantity, timestamp, quick = payload

        if not isinstance(trader_id, str):
            raise DropPacket("Invalid 'trader_id' type")
        if not isinstance(message_number, str):
            raise DropPacket("Invalid 'message_number' type")
        if not isinstance(order_number, str):
            raise DropPacket("Invalid 'order_number' type")
        if not isinstance(recipient_trader_id, str):
            raise DropPacket("Invalid 'recipient_trader_id' type")
        if not isinstance(recipient_order_number, str):
            raise DropPacket("Invalid 'recipient_order_number' type")
        if not isinstance(price, int):
            raise DropPacket("Invalid 'price' type")
        if not isinstance(quantity, int):
            raise DropPacket("Invalid 'quantity' type")
        if not isinstance(timestamp, float):
            raise DropPacket("Invalid 'timestamp' type")
        if not isinstance(quick, bool):
            raise DropPacket("Invalid 'quick' type")

        return offset, placeholder.meta.payload.implement(trader_id, message_number, order_number, recipient_trader_id,
                                                          recipient_order_number, price, quantity, timestamp, quick)

    def _encode_accepted_trade(self, message):
        packet = encode((
            message.payload.trader_id,
            message.payload.message_number,
            message.payload.order_number,
            message.payload.recipient_trader_id,
            message.payload.recipient_order_number,
            message.payload.price,
            message.payload.quantity,
            message.payload.timestamp,
            message.payload.quick,
            message.payload.ttl
        ))
        return packet,

    def _decode_accepted_trade(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the accepted-trade-payload")

        if not isinstance(payload, tuple):
            raise DropPacket("Invalid payload type")

        trader_id, message_number, order_number, recipient_trader_id, recipient_order_number, price, quantity, timestamp, quick, ttl = payload

        if not isinstance(trader_id, str):
            raise DropPacket("Invalid 'trader_id' type")
        if not isinstance(message_number, str):
            raise DropPacket("Invalid 'message_number' type")
        if not isinstance(order_number, str):
            raise DropPacket("Invalid 'order_number' type")
        if not isinstance(recipient_trader_id, str):
            raise DropPacket("Invalid 'recipient_trader_id' type")
        if not isinstance(recipient_order_number, str):
            raise DropPacket("Invalid 'recipient_message_number' type")
        if not isinstance(price, int):
            raise DropPacket("Invalid 'price' type")
        if not isinstance(quantity, int):
            raise DropPacket("Invalid 'quantity' type")
        if not isinstance(timestamp, float):
            raise DropPacket("Invalid 'timestamp' type")
        if not isinstance(quick, bool):
            raise DropPacket("Invalid 'quick' type")
        if not isinstance(ttl, int) and ttl >= 0:
            raise DropPacket("Invalid 'ttl' type")

        return offset, placeholder.meta.payload.implement(trader_id, message_number, order_number, recipient_trader_id,
                                                          recipient_order_number, price, quantity, timestamp, quick,
                                                          ttl)

    def _encode_declined_trade(self, message):
        packet = encode((
            message.payload.trader_id,
            message.payload.message_number,
            message.payload.order_number,
            message.payload.recipient_trader_id,
            message.payload.recipient_order_number,
            message.payload.timestamp,
            message.payload.quick
        ))
        return packet,

    def _decode_declined_trade(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the declined-trade-payload")

        if not isinstance(payload, tuple):
            raise DropPacket("Invalid payload type")

        trader_id, message_number, order_number, recipient_trader_id, recipient_order_number, timestamp, quick = payload

        if not isinstance(trader_id, str):
            raise DropPacket("Invalid 'trader_id' type")
        if not isinstance(message_number, str):
            raise DropPacket("Invalid 'message_number' type")
        if not isinstance(order_number, str):
            raise DropPacket("Invalid 'order_number' type")
        if not isinstance(recipient_trader_id, str):
            raise DropPacket("Invalid 'recipient_trader_id' type")
        if not isinstance(recipient_order_number, str):
            raise DropPacket("Invalid 'recipient_message_number' type")
        if not isinstance(timestamp, float):
            raise DropPacket("Invalid 'timestamp' type")
        if not isinstance(quick, bool):
            raise DropPacket("Invalid 'quick' type")

        return offset, placeholder.meta.payload.implement(trader_id, message_number, order_number, recipient_trader_id,
                                                          recipient_order_number, timestamp, quick)
