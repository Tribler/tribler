from struct import pack, unpack_from

from Tribler.Core.dispersy.message import DropPacket
from Tribler.Core.dispersy.conversion import BinaryConversion

class AllChannelConversion(BinaryConversion):
    def __init__(self, community):
        super(AllChannelConversion, self).__init__(community, "\x00\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"propagate-torrents"), self._encode_propagate_torrents, self._decode_propagate_torrents)
        self.define_meta_message(chr(2), community.get_meta_message(u"torrent-request"), self._encode_torrent_request, self._decode_torrent_request)

    def _encode_propagate_torrents(self, message):
        return message.payload.infohashes

    def _decode_propagate_torrents(self, meta_message, offset, data):
        if len(data) < offset + 20:
            raise DropPacket("Insufficient packet size")

        infohashes = []
        while len(data) >= offset + 20:
            infohashes.append(data[offset:offset+20])
            offset += 20

        return offset, meta_message.payload.implement(infohashes)

    def _encode_torrent_request(self, message):
        return message.payload.infohash,

    def _decode_torrent_request(self, meta_message, offset, data):
        if len(data) < offset + 20:
            raise DropPacket("Insufficient packet size")

        infohash = data[offset:offset+20]
        offset += 20

        return offset, meta_message.payload.implement(infohash)
