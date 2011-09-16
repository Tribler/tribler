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
        payload = message.payload
        return inet_aton(payload.destination_address[0]), pack("!H", payload.destination_address[1]), \
            inet_aton(payload.source_internal_address[0]), pack("!H", payload.source_internal_address[1]), \
            pack("!BH", int(payload.advice), payload.identifier)

    def _decode_introduction_request(self, placeholder, offset, data):
        if len(data) < offset + 15:
            raise DropPacket("Insufficient packet size")

        destination_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        source_internal_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        advice, identifier = unpack_from("!BH", data, offset)
        advice = bool(advice)
        offset += 3

        return offset, placeholder.meta.payload.implement(destination_address, source_internal_address, advice, identifier)

    def _encode_introduction_response(self, message):
        payload = message.payload
        return inet_aton(payload.destination_address[0]), pack("!H", payload.destination_address[1]), \
            inet_aton(payload.internal_introduction_address[0]), pack("!H", payload.internal_introduction_address[1]), \
            inet_aton(payload.external_introduction_address[0]), pack("!H", payload.external_introduction_address[1]), \
            pack("!H", payload.identifier)

    def _decode_introduction_response(self, placeholder, offset, data):
        if len(data) < offset + 20:
            raise DropPacket("Insufficient packet size")

        destination_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        internal_introduction_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        external_introduction_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6
        
        identifier, = unpack_from("!H", data, offset)
        offset += 2

        return offset, placeholder.meta.payload.implement(destination_address, internal_introduction_address, external_introduction_address, identifier)

    def _encode_puncture_request(self, message):
        payload = message.payload
        return inet_aton(payload.internal_walker_address[0]), pack("!H", payload.internal_walker_address[1]), \
            inet_aton(payload.external_walker_address[0]), pack("!H", payload.external_walker_address[1])

    def _decode_puncture_request(self, placeholder, offset, data):
        if len(data) < offset + 12:
            raise DropPacket("Insufficient packet size")

        internal_walker_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        external_walker_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        return offset, placeholder.meta.payload.implement(internal_walker_address, external_walker_address)

    def _encode_puncture(self, message):
        return ()

    def _decode_puncture(self, placeholder, offset, data):
        return offset, placeholder.meta.payload.implement()

