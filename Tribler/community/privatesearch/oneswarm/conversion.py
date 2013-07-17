from struct import pack, unpack_from
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.conversion import BinaryConversion

class SearchConversion(BinaryConversion):
    def __init__(self, community):
        super(SearchConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(6), community.get_meta_message(u"search-cancel"), lambda message: self._encode_decode(self._encode_search_cancel, self._decode_search_cancel, message), self._decode_search_cancel)

    def _encode_search_cancel(self, message):
        return pack('!H', message.payload.identifier),

    def _decode_search_cancel(self, placeholder, offset, data):
        identifier, = unpack_from('!H', data, offset)
        offset += 2

        return offset, placeholder.meta.payload.implement(identifier)

    def _encode_decode(self, encode, decode, message):
        result = encode(message)
        try:
            decode(None, 0, result[0])

        except DropPacket:
            raise
        except:
            pass
        return result
