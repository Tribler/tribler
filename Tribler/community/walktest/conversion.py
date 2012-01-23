from struct import pack, unpack_from

from Tribler.Core.dispersy.conversion import BinaryConversion
from Tribler.Core.dispersy.message import DropPacket

class WalktestConversion(BinaryConversion):
    def __init__(self, community):
        super(WalktestConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"contact"), self._encode_contact, self._decode_contact)

    def _encode_contact(self, message):
        return pack("!H", message.payload.identifier),

    def _decode_contact(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size")

        identifier, = unpack_from("!H", data, offset)
        offset += 2

        return offset, placeholder.meta.payload.implement(identifier)
