from random import choice, sample
from struct import pack, unpack_from

from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


class AllChannelConversion(BinaryConversion):

    def __init__(self, community):
        super(AllChannelConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"channelcast"),
                                 self._encode_channelcast, self._decode_channelcast)
        self.define_meta_message(chr(2), community.get_meta_message(u"channelcast-request"),
                                 self._encode_channelcast, self._decode_channelcast)
        self.define_meta_message(chr(3), community.get_meta_message(u"channelsearch"),
                                 self._encode_channelsearch, self._decode_channelsearch)
        self.define_meta_message(chr(4), community.get_meta_message(u"channelsearch-response"),
                                 self._encode_channelsearch_response, self._decode_channelsearch_response)
        self.define_meta_message(chr(5), community.get_meta_message(u"votecast"),
                                 self._encode_votecast, self._decode_votecast)

    def _encode_channelcast(self, message):
        max_len = self._community.dispersy_sync_bloom_filter_bits / 8

        def create_msg():
            return encode(message.payload.torrents)

        packet = create_msg()
        while len(packet) > max_len:
            community = choice(message.payload.torrents.keys())
            nrTorrents = len(message.payload.torrents[community])
            if nrTorrents == 1:
                del message.payload.torrents[community]
            else:
                message.payload.torrents[community] = set(sample(message.payload.torrents[community], nrTorrents - 1))

            packet = create_msg()

        return packet,

    def _decode_channelcast(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the channelcast-payload")

        if not isinstance(payload, dict):
            raise DropPacket("Invalid payload type")

        for cid, infohashes in payload.iteritems():
            if not (isinstance(cid, str) and len(cid) == 20):
                raise DropPacket("Invalid 'cid' type or value")

            for infohash in infohashes:
                if not (isinstance(infohash, str) and len(infohash) == 20):
                    raise DropPacket("Invalid 'infohash' type or value")
        return offset, placeholder.meta.payload.implement(payload)

    def _encode_channelsearch(self, message):
        packet = encode(message.payload.keywords)
        return packet,

    def _decode_channelsearch(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the channelcast-payload")

        if not isinstance(payload, list):
            raise DropPacket("Invalid payload type")

        for keyword in payload:
            if not isinstance(keyword, unicode):
                raise DropPacket("Invalid 'keyword' type")
        return offset, placeholder.meta.payload.implement(payload)

    def _encode_channelsearch_response(self, message):
        packet = encode((message.payload.keywords, message.payload.torrents))
        return packet,

    def _decode_channelsearch_response(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the channelcast-payload")

        if not isinstance(payload, tuple):
            raise DropPacket("Invalid payload type")

        keywords, torrents = payload
        for keyword in keywords:
            if not isinstance(keyword, unicode):
                raise DropPacket("Invalid 'keyword' type")

        for cid, infohashes in torrents.iteritems():
            if not (isinstance(cid, str) and len(cid) == 20):
                raise DropPacket("Invalid 'cid' type or value")

            for infohash in infohashes:
                if not (isinstance(infohash, str) and len(infohash) == 20):
                    raise DropPacket("Invalid 'infohash' type or value")

        return offset, placeholder.meta.payload.implement(keywords, torrents)

    def _encode_votecast(self, message):
        return pack('!20shl', message.payload.cid, message.payload.vote, message.payload.timestamp),

    def _decode_votecast(self, placeholder, offset, data):
        if len(data) < offset + 26:
            raise DropPacket("Unable to decode the payload")

        cid, vote, timestamp = unpack_from('!20shl', data, offset)
        if not vote in [-1, 0, 2]:
            raise DropPacket("Invalid 'vote' type or value")

        return offset + 26, placeholder.meta.payload.implement(cid, vote, timestamp)

    # def _encode_torrent_request(self, message):
    #     return message.payload.infohash,

    # def _decode_torrent_request(self, placeholder, offset, data):
    #     if len(data) < offset + 20:
    #         raise DropPacket("Insufficient packet size")

    #     infohash = data[offset:offset+20]
    #     offset += 20

    #     return offset, placeholder.meta.payload.implement(infohash)
