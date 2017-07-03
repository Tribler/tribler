from Tribler.dispersy.conversion import BinaryConversion
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.message import DropPacket

class LatencyConversion(BinaryConversion):

    def __init__(self, community):
        #super(MarketConversion, self).__init__(community, "\x01")
        super(LatencyConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"ping"),
                                 self._encode_ping, self._decode_ping)
        self.define_meta_message(chr(2), community.get_meta_message(u"pong"),
                                 self._encode_pong, self._decode_pong)
        self.define_meta_message(chr(3), community.get_meta_message(u"request_latencies"),
                                 self._encode_request_latencies, self._decode_request_latencies)
        self.define_meta_message(chr(4), community.get_meta_message(u"response_latencies"),
                                 self._encode_response_latencies, self._decode_response_latencies)

    def _encode_ping(self, message):
        payload = message.payload
        packet = encode((
            str(payload.ip), int(payload.port), str(payload.time)
        ))
        return packet,

    def _decode_ping(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [str,int,str])

    def _encode_pong(self, message):
        payload = message.payload
        packet = encode((
            str(payload.ip), int(payload.port), str(payload.time)
        ))
        return packet,

    def _decode_pong(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [str,int,str])

    def _encode_request_latencies(self, message):
        payload = message.payload
        packet = encode((
            str(payload.ip), int(payload.port), int(payload.hops), list(payload.relay_list)
        ))
        return packet,

    def _decode_request_latencies(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [str,int,int,list])

    def _encode_response_latencies(self, message):
        payload = message.payload
        packet = encode((
            str(payload.ip), int(payload.port), str(payload.latencies), list(payload.relay_list)
        ))
        return packet,

    def _decode_response_latencies(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [str,int,str,list])

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
                if arg_type == str or arg_type == int:
                    args.append(payload[i])
                else:
                    args.append(arg_type(payload[i]))
            except ValueError:
                raise DropPacket("Invalid '" + arg_type.__name__ + "' type")
        return offset, placeholder.meta.payload.implement(*args)