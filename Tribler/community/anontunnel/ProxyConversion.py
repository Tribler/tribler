import struct
from Tribler.Core.Utilities.encoding import encode, decode

from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.payload import Payload


class StatsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, stats):
            super(StatsPayload.Implementation, self).__init__(meta)
            self.stats = stats


class ProxyConversion(BinaryConversion):
    def __init__(self, community):
        super(ProxyConversion, self).__init__(community, "\x01")

        self.define_meta_message(
            chr(1),
            community.get_meta_message(u"stats")
            , self._encode_stats
            , self._decode_stats
        )

        #self.define_meta_message(
        #    chr(10),
        #    community.get_meta_message(u"circuit")
        #    , self._encode_circuit
        #    , self._decode_circuit
        #)

    @staticmethod
    def _encode_stats(message):
        return encode(message.payload.stats),

    @staticmethod
    def _decode_stats(placeholder, offset, data):
        offset, stats = decode(data, offset)

        return offset, placeholder.meta.payload.implement(stats)