from socket import inet_ntoa, inet_aton
from struct import pack, unpack_from

from Tribler.Core.dispersy.conversion import BinaryConversion
from Tribler.Core.dispersy.message import DropPacket

class Conversion(BinaryConversion):
    def __init__(self, community):
        super(Conversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"introduction-request"), self._encode_nothing, self._decode_nothing)
        self.define_meta_message(chr(2), community.get_meta_message(u"introduction-response"), self._encode_address, self._decode_address)
        self.define_meta_message(chr(3), community.get_meta_message(u"puncture-request"), self._encode_address, self._decode_address)
        self.define_meta_message(chr(4), community.get_meta_message(u"puncture"), self._encode_nothing, self._decode_nothing)

    def _encode_nothing(self, message):
        return ()

    def _decode_nothing(self, placeholder, offset, data):
        return offset, placeholder.meta.payload.implement()

    def _encode_address(self, message):
        return inet_aton(message.payload.address[0]), pack("!H", message.payload.address[1])

    def _decode_address(self, placeholder, offset, data):
        if len(data) < offset + 6:
            raise DropPacket("Insufficient packet size")

        address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        return offset, placeholder.meta.payload.implement(address)
