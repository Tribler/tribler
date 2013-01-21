from struct import pack, unpack_from
from random import choice, sample
from math import ceil

from Tribler.dispersy.encoding import encode, decode
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.Core.Swift.SwiftDef import SwiftDef
import zlib
from Crypto.Util.number import long_to_bytes, bytes_to_long
from payload import EncryptedIntroPayload

class SearchConversion(BinaryConversion):
    def __init__(self, community):
        super(SearchConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"search-request"), lambda message: self._encode_decode(self._encode_search_request, self._decode_search_request, message), self._decode_search_request)
        self.define_meta_message(chr(2), community.get_meta_message(u"search-response"), lambda message: self._encode_decode(self._encode_search_response, self._decode_search_response, message), self._decode_search_response)
        self.define_meta_message(chr(3), community.get_meta_message(u"torrent-request"), lambda message: self._encode_decode(self._encode_torrent_request, self._decode_torrent_request, message), self._decode_torrent_request)
        self.define_meta_message(chr(4), community.get_meta_message(u"ping"), lambda message: self._encode_decode(self._encode_ping, self._decode_ping, message), self._decode_ping)
        self.define_meta_message(chr(5), community.get_meta_message(u"pong"), lambda message: self._encode_decode(self._encode_pong, self._decode_pong, message), self._decode_pong)
        self.define_meta_message(chr(6), community.get_meta_message(u"encrypted-response"), lambda message: self._encode_decode(self._encode_encr_response, self._decode_encr_response, message), self._decode_encr_response)
        self.define_meta_message(chr(7), community.get_meta_message(u"encrypted-hashes"), lambda message: self._encode_decode(self._encode_encr_hash_response, self._decode_encr_hash_response, message), self._decode_encr_hash_response)
        self.define_meta_message(chr(8), community.get_meta_message(u"request-key"), lambda message: self._encode_decode(self._encode_request_key, self._decode_request_key, message), self._decode_request_key)
        self.define_meta_message(chr(9), community.get_meta_message(u"encryption-key"), lambda message: self._encode_decode(self._encode_encr_key, self._decode_encr_key, message), self._decode_encr_key)
        
    def _encode_introduction_request(self, message):
        data = BinaryConversion._encode_introduction_request(self, message)

        if message.payload.preference_list:
            fmt = '128s'* (len(message.payload.preference_list) + 1)
            if message.payload.key_n:
                str_n = long_to_bytes(message.payload.key_n, 128)
            else:
                str_n = long_to_bytes(-1l, 128)
            str_prefs = [long_to_bytes(preference, 128) for preference in message.payload.preference_list]
            
            data.append(pack('!'+fmt, str_n, *str_prefs))
            
        return data
    
    def _decode_introduction_request(self, placeholder, offset, data):
        offset, payload = BinaryConversion._decode_introduction_request(self, placeholder, offset, data)
        
        #if there's still bytes in this request, treat them as taste_bloom_filter
        has_stuff = len(data) > offset
        if has_stuff:
            length = len(data) - offset
            if length % 128 != 0 or length < 128:
                raise DropPacket("Invalid number of bytes available (ir)")
            
            hashpack = '128s' * (length/128)
            hashes = unpack_from('!'+hashpack, data, offset)

            str_n = hashes[0]
            payload.set_key_n(bytes_to_long(str_n))
            
            hashes = [bytes_to_long(hash) for hash in hashes[1:]]
            payload.set_preference_list(hashes)
            
            offset += length
        return offset, payload
    
    def _encode_encr_response(self, message):
        str_prefs = [long_to_bytes(preference, 128) for preference in message.payload.preference_list]
        
        fmt = "!H" + "128s"*len(str_prefs)
        packet = pack(fmt, message.payload.identifier, *str_prefs)
        return packet,
    
    def _decode_encr_response(self, placeholder, offset, data):
        identifier, = unpack_from('!H', data, offset)
        offset += 2
       
        length = len(data) - offset
        if length % 128 != 0:
            raise DropPacket("Invalid number of bytes available (encr_res)")
        
        if length:
            hashpack = '128s' * (length/128)
            hashes = unpack_from('!'+hashpack, data, offset)
            hashes = [bytes_to_long(hash) for hash in hashes]
            offset += length
        
        return offset, placeholder.meta.payload.implement(identifier, hashes)
    
    def _encode_encr_hash_response(self, message):
        fmt = "!HH" + "20s"*len(message.payload.preference_list)
        packet = pack(fmt, message.payload.identifier, message.payload.len_preference_list, *message.payload.preference_list)
        return packet,
    
    def _decode_encr_hash_response(self, placeholder, offset, data):
        identifier, len_preference_list = unpack_from('!HH', data, offset)
        offset += 4
       
        length = len(data) - offset
        if length % 20 != 0:
            raise DropPacket("Invalid number of bytes available (encr_hash_res)")
        
        if length:
            hashpack = '20s' * (length/20)
            hashes = list(unpack_from('!'+hashpack, data, offset))
            offset += length
        else:
            hashes = []
        
        return offset, placeholder.meta.payload.implement(identifier, hashes, len_preference_list)
        
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
            raise DropPacket("Unable to decode the search-payload, got %d bytes expected 4"%(len(identifier)))
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
            raise DropPacket("Unable to decode the search-response-payload, got %d bytes expected 2"%(len(identifier)))
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
                raise DropPacket("Invalid length type '%s'"%type(length))
                
            if not isinstance(nrfiles, int):
                raise DropPacket("Invalid nrfiles type")
                
            if not isinstance(categorykeys, list):
                raise DropPacket("Invalid categorykeys type")
            
            if not all(isinstance(key, unicode) for key in categorykeys):
                raise DropPacket("Invalid categorykey type")
                
            if not isinstance(creation_date, long):
                raise DropPacket("Invalid creation_date type")
            
            if not isinstance(seeders, int):
                raise DropPacket("Invalid seeders type '%s'"%type(seeders))
                
            if not isinstance(leechers, int):
                raise DropPacket("Invalid leechers type '%s'"%type(leechers))
                
            if swift_hash:
                if not isinstance(swift_hash, str):
                    raise DropPacket("Invalid swift_hash type '%s'"%type(swift_hash))
                
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
    
    def _encode_ping(self, message):
        hashpack = '20s20sHHH' * len(message.payload.torrents)
        torrents = [item for sublist in message.payload.torrents for item in sublist]
        return pack('!H'+hashpack, message.payload.identifier, *torrents),
    
    def _decode_ping(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size")
        
        identifier, = unpack_from('!H', data, offset)
        offset += 2
        
        length = len(data) - offset
        if length % 46 != 0:
            raise DropPacket("Invalid number of bytes available")
        
        if length:
            hashpack = '20s20sHHH' * (length/46)
            hashes = unpack_from('!'+hashpack, data, offset)
            offset += length
            
            torrents = []
            for i in range(0, len(hashes), 5):
                torrents.append([hashes[i], hashes[i+1], hashes[i+2], hashes[i+3], hashes[i+4]])
        else:
            torrents = []
        
        return offset, placeholder.meta.payload.implement(identifier, torrents)
    
    def _encode_pong(self, message):
        return self._encode_ping(message)
    def _decode_pong(self, placeholder, offset, data):
        return self._decode_ping(placeholder, offset, data)
    
    def _encode_torrent_request(self, message):
        max_len = self._community.dispersy_sync_bloom_filter_bits/8
        
        def create_msg():
            return encode(message.payload.torrents) 
        
        packet = create_msg()
        while len(packet) > max_len:
            community = choice(message.payload.torrents.keys())
            nrTorrents = len(message.payload.torrents[community])
            if nrTorrents == 1:
                del message.payload.torrents[community]
            else:
                message.payload.torrents[community] = set(sample(message.payload.torrents[community], nrTorrents-1))
            
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
    
    def _encode_encr_key(self, message):
        str_n = long_to_bytes(message.payload.key_n, 128)
        str_e = long_to_bytes(message.payload.key_e, 128)
            
        packet = pack('!128s128s', str_n, str_e)
        return packet,
        
    def _decode_encr_key(self, placeholder, offset, data):
        length = len(data) - offset
        if length != 256:
            raise DropPacket("Invalid number of bytes available (ecnr_key)")
        
        str_n, str_e = unpack_from('!128s128s', data, offset)
                
        key_n = bytes_to_long(str_n)
        key_e = bytes_to_long(str_e)
    
        offset += length
        return offset, placeholder.meta.payload.implement(key_n, key_e)
    
    def _encode_request_key(self, message):
        return tuple()
    
    def _decode_request_key(self, placeholder, offset, data):
        return offset, placeholder.meta.payload.implement()
    
    def _encode_decode(self, encode, decode, message):
        result = encode(message)
        try:
            decode(None, 0, result[0])
            
        except DropPacket:
            raise
        except:
            pass
        return result