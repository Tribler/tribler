from struct import pack, unpack_from
from random import choice, sample
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.bloomfilter import BloomFilter


class SearchConversion(BinaryConversion):

    def __init__(self, community):
        super(SearchConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"search-request"), lambda message: self._encode_decode(self._encode_search_request, self._decode_search_request, message), self._decode_search_request)
        self.define_meta_message(chr(2), community.get_meta_message(u"search-response"), lambda message: self._encode_decode(self._encode_search_response, self._decode_search_response, message), self._decode_search_response)
        self.define_meta_message(chr(3), community.get_meta_message(u"torrent-request"), lambda message: self._encode_decode(self._encode_torrent_request, self._decode_torrent_request, message), self._decode_torrent_request)

    def _encode_search_request(self, message):
        packet = pack('!HH', message.payload.identifier, message.payload.ttl), message.payload.keywords
        if message.payload.bloom_filter:
            packet = packet + (message.payload.bloom_filter.functions, message.payload.bloom_filter.prefix, message.payload.bloom_filter.bytes)
        packet = encode(packet)
        return packet,

    def _decode_search_request(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the search-payload")

        if len(payload) < 2:
            raise DropPacket("Invalid payload length")

        identifier, keywords = payload[:2]

        if len(identifier) != 4:
            raise DropPacket("Unable to decode the search-payload, got %d bytes expected 4" % (len(identifier)))
        identifier, ttl = unpack_from('!HH', identifier)

        if not isinstance(keywords, list):
            raise DropPacket("Invalid 'keywords' type")
        for keyword in keywords:
            if not isinstance(keyword, unicode):
                raise DropPacket("Invalid 'keyword' type")

        if len(payload) == 5:
            functions, prefix, bytes_ = payload[2:5]

            if not isinstance(functions, int):
                raise DropPacket("Invalid functions type")
            if not 0 < functions:
                raise DropPacket("Invalid functions value")

            size = len(bytes_)
            if not 0 < size:
                raise DropPacket("Invalid size of bloomfilter")
            if not size % 8 == 0:
                raise DropPacket("Invalid size of bloomfilter, must be a multiple of eight")

            if not isinstance(prefix, str):
                raise DropPacket("Invalid prefix type")
            if not 0 <= len(prefix) < 256:
                raise DropPacket("Invalid prefix length")

            bloom_filter = BloomFilter(bytes_, functions, prefix=prefix)
        else:
            bloom_filter = None

        return offset, placeholder.meta.payload.implement(identifier, ttl, keywords, bloom_filter)

    def _encode_search_response(self, message):
        packet = pack('!H', message.payload.identifier), message.payload.results
        return encode(packet),

    def _decode_search_response(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the search-reponse-payload")

        if len(payload) < 2:
            raise DropPacket("Invalid payload length")

        identifier, results = payload[:2]

        if len(identifier) != 2:
            raise DropPacket("Unable to decode the search-response-payload, got %d bytes expected 2" % (len(identifier)))
        identifier, = unpack_from('!H', identifier)

        if not isinstance(results, list):
            raise DropPacket("Invalid 'results' type")

        for result in results:
            if not isinstance(result, tuple):
                raise DropPacket("Invalid result type")

            if len(result) < 11:
                raise DropPacket("Invalid result length")

            infohash, swarmname, length, nrfiles, categorykeys, creation_date, seeders, leechers, swift_hash, swift_torrent_hash, cid = result[:11]

            if not isinstance(infohash, str):
                raise DropPacket("Invalid infohash type")
            if len(infohash) != 20:
                raise DropPacket("Invalid infohash length")

            if not isinstance(swarmname, unicode):
                raise DropPacket("Invalid swarmname type")

            if not isinstance(length, long):
                raise DropPacket("Invalid length type '%s'" % type(length))

            if not isinstance(nrfiles, int):
                raise DropPacket("Invalid nrfiles type")

            if not isinstance(categorykeys, list):
                raise DropPacket("Invalid categorykeys type")

            if not all(isinstance(key, unicode) for key in categorykeys):
                raise DropPacket("Invalid categorykey type")

            if not isinstance(creation_date, long):
                raise DropPacket("Invalid creation_date type")

            if not isinstance(seeders, int):
                raise DropPacket("Invalid seeders type '%s'" % type(seeders))

            if not isinstance(leechers, int):
                raise DropPacket("Invalid leechers type '%s'" % type(leechers))

            if swift_hash:
                if not isinstance(swift_hash, str):
                    raise DropPacket("Invalid swift_hash type '%s'" % type(swift_hash))

                if len(swift_hash) != 20:
                    raise DropPacket("Invalid swift_hash length")

            if swift_torrent_hash:
                if not isinstance(swift_torrent_hash, str):
                    raise DropPacket("Invalid swift_torrent_hash type")

                if len(swift_torrent_hash) != 20:
                    raise DropPacket("Invalid swift_torrent_hash length")

            if cid:
                if not isinstance(cid, str):
                    raise DropPacket("Invalid cid type")

                if len(cid) != 20:
                    raise DropPacket("Invalid cid length")

        return offset, placeholder.meta.payload.implement(identifier, results)

    def _encode_torrent_request(self, message):
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

    def _decode_torrent_request(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the torrent-request")

        if not isinstance(payload, dict):
            raise DropPacket("Invalid payload type")

        for cid, infohashes in payload.iteritems():
            if not (isinstance(cid, str) and len(cid) == 20):
                raise DropPacket("Invalid 'cid' type or value")

            for infohash in infohashes:
                if not (isinstance(infohash, str) and len(infohash) == 20):
                    raise DropPacket("Invalid 'infohash' type or value")
        return offset, placeholder.meta.payload.implement(payload)

    def _encode_decode(self, encode, decode, message):
        result = encode(message)
        try:
            decode(None, 0, result[0])

        except DropPacket:
            raise
        except:
            pass
        return result
