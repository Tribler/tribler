from socket import inet_ntoa, inet_aton
from struct import pack, unpack_from

from Tribler.Core.dispersy.conversion import BinaryConversion
from Tribler.Core.dispersy.message import DropPacket

class Conversion(BinaryConversion):
    def __init__(self, community):
        super(Conversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"introduction-request"), self._encode_introduction_request, self._decode_introduction_request)
        self.define_meta_message(chr(2), community.get_meta_message(u"introduction-response"), self._encode_introduction_response, self._decode_introduction_response)
        self.define_meta_message(chr(3), community.get_meta_message(u"puncture-request"), self._encode_puncture_request, self._decode_puncture_request)
        self.define_meta_message(chr(4), community.get_meta_message(u"puncture"), self._encode_puncture, self._decode_puncture)

    def _encode_introduction_request(self, message):
        return inet_aton(message.payload.public_address[0]), pack("!HH", message.payload.public_address[1], message.payload.identifier)

    def _decode_introduction_request(self, placeholder, offset, data):
        if len(data) < offset + 8:
            raise DropPacket("Insufficient packet size")

        # public address
        host = inet_ntoa(data[offset:offset+4])
        port, identifier = unpack_from("!HH", data, offset+4)
        offset += 8

        return offset, placeholder.meta.payload.implement((host, port), identifier)

    def _encode_introduction_response(self, message):
        return inet_aton(message.payload.public_address[0]), pack("!H", message.payload.public_address[1]),\
               inet_aton(message.payload.introduction_address[0]), pack("!H", message.payload.introduction_address[1]),\
               pack("!H", message.payload.identifier)

    def _decode_introduction_response(self, placeholder, offset, data):
        if len(data) < offset + 14:
            raise DropPacket("Insufficient packet size")

        public_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        introduction_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6
        
        identifier, = unpack_from("!H", data, offset)
        offset += 2

        return offset, placeholder.meta.payload.implement(public_address, introduction_address, identifier)

    def _encode_puncture_request(self, message):
        return inet_aton(message.payload.walker_address[0]), pack("!H", message.payload.walker_address[1])

    def _decode_puncture_request(self, placeholder, offset, data):
        if len(data) < offset + 6:
            raise DropPacket("Insufficient packet size")

        walker_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        return offset, placeholder.meta.payload.implement(walker_address)

    def _encode_puncture(self, message):
        return ()

    def _decode_puncture(self, placeholder, offset, data):
        return offset, placeholder.meta.payload.implement()

