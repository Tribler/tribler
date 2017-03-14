from struct import pack, unpack_from

from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


class DemersConversion(BinaryConversion):

    def __init__(self, community):
        super(DemersConversion, self).__init__(community, "\x02")
        self.define_meta_message(chr(1), community.get_meta_message(u"text"), self._encode_text, self._decode_text)

    def _encode_text(self, message):
        assert len(message.payload.text.encode("UTF-8")) < 256
        text = message.payload.text.encode("UTF-8")
        return pack("!B", len(text)), text[:255]

    def _decode_text(self, placeholder, offset, data):
        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size")

        text_length, = unpack_from("!B", data, offset)
        offset += 1

        try:
            text = data[offset:offset + text_length].decode("UTF-8")
            offset += text_length
        except UnicodeError:
            raise DropPacket("Unable to decode UTF-8")

        return offset, placeholder.meta.payload.implement(text)
