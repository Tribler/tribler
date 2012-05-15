from struct import pack, unpack_from

from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.conversion import BinaryConversion

class BarterCommunityConversion(BinaryConversion):
    def __init__(self, community):
        super(BarterCommunityConversion, self).__init__(community, "\x00\x02")
        self.define_meta_message(chr(1), community.get_meta_message(u"barter-record"), self._encode_barter_record, self._decode_barter_record)

    def _encode_barter_record(self, message):
        return pack("!LL", message.payload.first_upload, message.payload.second_upload),

    def _decode_barter_record(self, placeholder, offset, data):
        if len(data) < offset + 8:
            raise DropPacket("Insufficient packet size")

        first_upload, second_upload = unpack_from("!LL", data, offset)
        offset += 8

        return offset, placeholder.meta.payload.implement(first_upload, second_upload)
