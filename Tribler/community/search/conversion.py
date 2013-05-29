# Written by Niels Zeilemaker
from struct import pack, unpack_from
from random import choice, sample
from math import ceil

from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.Core.Swift.SwiftDef import SwiftDef
import zlib
from Tribler.community.search.payload import TasteIntroPayload


class SearchConversion(BinaryConversion):

    def __init__(self, community):
        super(SearchConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"search-request"), lambda message: self._encode_decode(self._encode_search_request, self._decode_search_request, message), self._decode_search_request)
        self.define_meta_message(chr(2), community.get_meta_message(u"search-response"), lambda message: self._encode_decode(self._encode_search_response, self._decode_search_response, message), self._decode_search_response)
        self.define_meta_message(chr(3), community.get_meta_message(u"torrent-request"), lambda message: self._encode_decode(self._encode_torrent_request, self._decode_torrent_request, message), self._decode_torrent_request)
        self.define_meta_message(chr(4), community.get_meta_message(u"torrent-collect-request"), lambda message: self._encode_decode(self._encode_torrent_collect_request, self._decode_torrent_collect_request, message), self._decode_torrent_collect_request)
        self.define_meta_message(chr(5), community.get_meta_message(u"torrent-collect-response"), lambda message: self._encode_decode(self._encode_torrent_collect_response, self._decode_torrent_collect_response, message), self._decode_torrent_collect_response)
        self.define_meta_message(chr(6), community.get_meta_message(u"torrent"), lambda message: self._encode_decode(self._encode_torrent, self._decode_torrent, message), self._decode_torrent)

    def _encode_introduction_request(self, message):
        data = BinaryConversion._encode_introduction_request(self, message)

        if message.payload.taste_bloom_filter:
            data.extend((pack('!IBH', message.payload.num_preferences, message.payload.taste_bloom_filter.functions, message.payload.taste_bloom_filter.size), message.payload.taste_bloom_filter.prefix, message.payload.taste_bloom_filter.bytes))
        return data

    def _decode_introduction_request(self, placeholder, offset, data):
        offset, payload = BinaryConversion._decode_introduction_request(self, placeholder, offset, data)

        # if there's still bytes in this request, treat them as taste_bloom_filter
        has_stuff = len(data) > offset
        if has_stuff:
            if len(data) < offset + 8:
                raise DropPacket("Insufficient packet size")

            num_preferences, functions, size = unpack_from('!IBH', data, offset)
            offset += 7

            prefix = data[offset]
            offset += 1

            if not 0 < num_preferences:
                raise DropPacket("Invalid num_preferences value")
            if not 0 < functions:
                raise DropPacket("Invalid functions value")
            if not 0 < size:
                raise DropPacket("Invalid size value")
            if not size % 8 == 0:
                raise DropPacket("Invalid size value, must be a multiple of eight")

            length = int(ceil(size / 8))
            if not length == len(data) - offset:
                raise DropPacket("Invalid number of bytes available (irq) %d, %d, %d" % (length, len(data) - offset, size))

            taste_bloom_filter = BloomFilter(data[offset:offset + length], functions, prefix=prefix)
            offset += length

            payload.set_num_preferences(num_preferences)
            payload.set_taste_bloom_filter(taste_bloom_filter)

        return offset, payload

    def _encode_decode(self, encode, decode, message):
        result = encode(message)
        try:
            decode(None, 0, result[0])

        except DropPacket:
            raise
        except:
            pass
        return result

    def _encode_search_request(self, message):
        packet = pack('!H', message.payload.identifier), message.payload.keywords
        if message.payload.bloom_filter:
            packet = packet + (message.payload.bloom_filter.functions, message.payload.bloom_filter.prefix, message.payload.bloom_filter.bytes)
        packet = encode(packet)
        return packet,

    def _decode_search_request(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decodr 21, 2012 e the search-payload")

        if len(payload) < 2:
            raise DropPacket("Invalid payload length")

        identifier, keywords = payload[:2]

        if len(identifier) != 2:
            raise DropPacket("Unable to decode the search-payload, got %d bytes expected 2" % (len(identifier)))
        identifier, = unpack_from('!H', identifier)

        if not isinstance(keywords, list):
            raise DropPacket("Invalid 'keywords' type")
        for keyword in keywords:
            if not isinstance(keyword, unicode):
                raise DropPacket("Invalid 'keyword' type")

        if len(payload) > 5:
            functions, prefix, bytes_ = payload[2:6]

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

        return offset, placeholder.meta.payload.implement(identifier, keywords, bloom_filter)

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

    def _encode_torrent_collect_request(self, message):
        import sys
        for torrent in message.payload.torrents:
            if torrent[2] > 2 ** 16 or torrent[2] < 0:
                print >> sys.stderr, "seeder value is incorrect", torrent[2]
            if torrent[3] > 2 ** 16 or torrent[3] < 0:
                print >> sys.stderr, "leecher value is incorrect", torrent[3]
            if torrent[4] > 2 ** 16 or torrent[4] < 0:
                print >> sys.stderr, "since value is incorrect", torrent[4]

        hashpack = '20s20sHHH' * len(message.payload.torrents)
        torrents = [item for sublist in message.payload.torrents for item in sublist]
        return pack('!HH' + hashpack, message.payload.identifier, message.payload.hashtype, *torrents),

    def _decode_torrent_collect_request(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")

        identifier, hashtype = unpack_from('!HH', data, offset)
        offset += 4

        length = len(data) - offset
        if length % 46 != 0:
            raise DropPacket("Invalid number of bytes available (tcr)")

        if length:
            hashpack = '20s20sHHH' * (length / 46)
            hashes = unpack_from('!' + hashpack, data, offset)
            offset += length

            torrents = []
            for i in range(0, len(hashes), 5):
                torrents.append([hashes[i], hashes[i + 1], hashes[i + 2], hashes[i+3], hashes[i+4]])
        else:
            torrents = []
        return offset, placeholder.meta.payload.implement(identifier, hashtype, torrents)

    def _encode_torrent_collect_response(self, message):
        return self._encode_torrent_collect_request(message)

    def _decode_torrent_collect_response(self, placeholder, offset, data):
        return self._decode_torrent_collect_request(placeholder, offset, data)

    def _encode_torrent(self, message):
        max_len = self._community.dispersy_sync_bloom_filter_bits / 8

        files = message.payload.files
        trackers = message.payload.trackers

        def create_msg():
            normal_msg = pack('!20sQ', message.payload.infohash, message.payload.timestamp), message.payload.name, tuple(files), tuple(trackers)
            normal_msg = encode(normal_msg)
            return zlib.compress(normal_msg)

        compressed_msg = create_msg()
        while len(compressed_msg) > max_len:
            if len(trackers) > 10:
                # only use first 10 trackers, .torrents in the wild have been seen to have 1000+ trackers...
                trackers = trackers[:10]
            else:
                # reduce files by the amount we are currently to big
                reduce_by = max_len / (len(compressed_msg) * 1.0)
                nr_files_to_include = int(len(files) * reduce_by)
                files = sample(files, nr_files_to_include)

            compressed_msg = create_msg()
        return compressed_msg,

    def _decode_torrent(self, placeholder, offset, data):
        uncompressed_data = zlib.decompress(data[offset:])
        offset = len(data)

        try:
            _, values = decode(uncompressed_data)
        except ValueError:
            raise DropPacket("Unable to decode the torrent-payload")

        infohash_time, name, files, trackers = values
        if len(infohash_time) != 28:
            raise DropPacket("Unable to decode the torrent-payload, got %d bytes expected 28" % (len(infohash_time)))
        infohash, timestamp = unpack_from('!20sQ', infohash_time)

        if not isinstance(name, unicode):
            raise DropPacket("Invalid 'name' type")

        if not isinstance(files, tuple):
            raise DropPacket("Invalid 'files' type")

        if len(files) == 0:
            raise DropPacket("Should have at least one file")

        for file in files:
            if len(file) != 2:
                raise DropPacket("Invalid 'file_len' type")

            path, length = file
            if not isinstance(path, unicode):
                raise DropPacket("Invalid 'files_path' type is %s" % type(path))
            if not isinstance(length, (int, long)):
                raise DropPacket("Invalid 'files_length' type is %s" % type(length))

        if not isinstance(trackers, tuple):
            raise DropPacket("Invalid 'trackers' type")
        for tracker in trackers:
            if not isinstance(tracker, str):
                raise DropPacket("Invalid 'tracker' type")

        return offset, placeholder.meta.payload.implement(infohash, timestamp, name, files, trackers)
