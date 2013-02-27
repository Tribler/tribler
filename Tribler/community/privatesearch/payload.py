from Tribler.dispersy.payload import Payload, IntroductionRequestPayload
from Tribler.dispersy.bloomfilter import BloomFilter

MAXLONG128 = (1 << 1024) - 1
MAXLONG256 = (1 << 2048) - 1

class EncryptedIntroPayload(IntroductionRequestPayload):
    class Implementation(IntroductionRequestPayload.Implementation):
        
        def __init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier, preference_list = None, key_n = None):
            IntroductionRequestPayload.Implementation.__init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier)
            assert not preference_list or isinstance(preference_list, list), 'preferencelist should be list'
            assert not key_n or isinstance(key_n, long), 'key_n should be long'
            
            if preference_list:
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)

            self._preference_list = preference_list
            self._key_n = key_n
        
        def set_preference_list(self, preference_list):
            self._preference_list = preference_list
            
        def set_key_n(self, key_n):
            self._key_n = key_n
            
        @property
        def preference_list(self):
            return self._preference_list
        
        @property
        def key_n(self):
            return self._key_n
        
class EncryptedResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, preference_list, his_preference_list):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(preference_list, list), 'preferencelist should be list not %s'%type(preference_list)
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)
                
                assert isinstance(his_preference_list, list), 'his_preference_list should be list not %s'%type(his_preference_list)
                for hpreference in his_preference_list:
                    assert isinstance(hpreference, str), type(hpreference)
                    assert len(hpreference) == 20, len(hpreference)
                    
            super(EncryptedResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._preference_list = preference_list
            self._his_preference_list = his_preference_list

        @property
        def identifier(self):
            return self._identifier

        @property
        def preference_list(self):
            return self._preference_list
        
        @property
        def his_preference_list(self):
            return self._his_preference_list
        
class BundledEncryptedResponsePayload(EncryptedResponsePayload):
    class Implementation(EncryptedResponsePayload.Implementation):
        def __init__(self, meta, identifier, preference_list, his_preference_list, bundled_responses):
            EncryptedResponsePayload.Implementation.__init__(self, meta, identifier, preference_list, his_preference_list)
            
            assert isinstance(bundled_responses, list), 'bundled_responses should be list not %s'%type(bundled_responses)
            for candidate_mid, response in bundled_responses:
                assert isinstance(candidate_mid, str), 'candidate_mid should be str'
                assert len(candidate_mid) == 20, len(candidate_mid)
                
                assert isinstance(response, tuple), type(response)
                assert len(response)==2, len(response)
                
                preference_list, his_preference_list = response
                assert isinstance(preference_list, list), 'preferencelist should be list not %s'%type(preference_list)
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)
                
                assert isinstance(his_preference_list, list), 'his_preference_list should be list not %s'%type(his_preference_list)
                for hpreference in his_preference_list:
                    assert isinstance(hpreference, str), type(hpreference)
                    assert len(hpreference) == 20, len(hpreference)
            
            self._bundled_responses = bundled_responses
        
        @property
        def bundled_responses(self):
            return self._bundled_responses
        
class GlobalVectorPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, preference_list):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(preference_list, list), 'preference_list should be list not %s'%type(preference_list)
                for item in preference_list:
                    assert isinstance(item, long), type(item)
                    assert item < MAXLONG256
                    
            super(GlobalVectorPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._preference_list = preference_list

        @property
        def identifier(self):
            return self._identifier

        @property
        def preference_list(self):
            return self._preference_list

class EncryptedVectorPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, key_n, preference_list):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(key_n, long), 'key_n should be long'
                assert key_n < MAXLONG128
                assert isinstance(preference_list, list), 'preferencelist should be list not %s'%type(preference_list)
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)
                    assert preference < MAXLONG256
                    
            super(EncryptedVectorPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._key_n = key_n
            self._preference_list = preference_list

        @property
        def identifier(self):
            return self._identifier
        
        @property
        def key_n(self):
            return self._key_n

        @property
        def preference_list(self):
            return self._preference_list
        
class EncryptedSumPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, _sum):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(_sum, long), 'sum should be long'
                assert _sum < MAXLONG256
                    
            super(EncryptedSumPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self.__sum = _sum

        @property
        def identifier(self):
            return self._identifier
        
        @property
        def _sum(self):
            return self.__sum
        
class EncryptedSumsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, _sum, sums):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(_sum, long), type(_sum)
                assert _sum < MAXLONG256
                
                assert isinstance(sums, list), type(sums)
                
                for candidate_mid, address_sum in sums:
                    assert isinstance(candidate_mid, str), 'candidate_mid should be str'
                    assert len(candidate_mid) == 20, len(candidate_mid)
                    assert isinstance(address_sum, long), 'address_sum should be long'
                    assert address_sum < MAXLONG256
                    
            super(EncryptedSumsPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self.__sum = _sum
            self._sums = sums

        @property
        def identifier(self):
            return self._identifier
        
        @property
        def _sum(self):
            return self.__sum
        
        @property
        def sums(self):
            return self._sums
        
class ExtendedIntroPayload(IntroductionRequestPayload):
    class Implementation(IntroductionRequestPayload.Implementation):
        
        def __init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier, introduce_me_to = None):
            IntroductionRequestPayload.Implementation.__init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier)
            if introduce_me_to:
                assert isinstance(introduce_me_to, str), 'introduce_me_to should be str'
                assert len(introduce_me_to) == 20, len(introduce_me_to)
            
            self._introduce_me_to = introduce_me_to
        
        def set_introduce_me_to(self, introduce_me_to):
            self._introduce_me_to = introduce_me_to
        
        @property
        def introduce_me_to(self):
            return self._introduce_me_to
        
class SimilarityRequest(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, key_n, preference_list):
            assert isinstance(identifier, int), type(identifier)
            assert not key_n or isinstance(key_n, long), 'key_n should be long'  
            assert not preference_list or isinstance(preference_list, list), 'preferencelist should be list'
            if preference_list:
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)
            
            self._identifier = identifier
            self._key_n = key_n
            self._preference_list = preference_list
        
        @property
        def identifier(self):
            return self._identifier
           
        @property
        def key_n(self):
            return self._key_n
        
        @property
        def preference_list(self):
            return self._preference_list
        
class SearchRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, ttl, keywords, bloom_filter = None):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(ttl, int), type(ttl)
                assert isinstance(keywords, list), 'keywords should be list'
                for keyword in keywords:
                    assert isinstance(keyword, unicode), '%s is type %s'%(keyword, type(keyword))
                    assert len(keyword) > 0
                    
                assert not bloom_filter or isinstance(bloom_filter, BloomFilter), type(bloom_filter)
                    
            super(SearchRequestPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._ttl = ttl
            self._keywords = keywords
            self._bloom_filter = bloom_filter

        @property
        def identifier(self):
            return self._identifier
        
        @property
        def ttl(self):
            return self._ttl
        
        @property
        def keywords(self):
            return self._keywords
        
        @property
        def bloom_filter(self):
            return self._bloom_filter

class SearchResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, results):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(results, list), type(results)
                for result in results: 
                    assert isinstance(result, tuple), type(result)
                    assert len(result) > 10
                    
                    infohash, swarmname, length, nrfiles, categorykeys, creation_date, seeders, leechers, swift_hash, swift_torrent_hash, cid = result[:11]
                    assert isinstance(infohash, str), type(infohash)
                    assert len(infohash) == 20
                    assert isinstance(swarmname, unicode), type(swarmname)
                    assert isinstance(length, long), type(length)
                    assert isinstance(nrfiles, int), type(nrfiles)
                    assert isinstance(categorykeys, list), type(categorykeys)
                    assert all(isinstance(key, unicode) for key in categorykeys), categorykeys
                    assert isinstance(creation_date, long), type(creation_date)
                    assert isinstance(seeders, int), type(seeders)
                    assert isinstance(leechers, int), type(leechers)
                    assert not swift_hash or isinstance(swift_hash, str), type(swift_hash)
                    assert not swift_hash or len(swift_hash) == 20, swift_hash
                    assert not swift_torrent_hash or isinstance(swift_torrent_hash, str), type(swift_torrent_hash)
                    assert not swift_torrent_hash or len(swift_torrent_hash) == 20, swift_torrent_hash
                    assert not cid or isinstance(cid, str), type(cid)
                    assert not cid or len(cid) == 20, cid
                    
            super(SearchResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._results = results

        @property
        def identifier(self):
            return self._identifier

        @property
        def results(self):
            return self._results

class TorrentRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, torrents):
            if __debug__:
                assert isinstance(torrents, dict), type(torrents)
                for cid, infohashes in torrents.iteritems():
                    assert isinstance(cid, str)
                    assert len(cid) == 20
                    assert isinstance(infohashes, set)
                    assert not filter(lambda x: not isinstance(x, str), infohashes)
                    assert not filter(lambda x: not len(x) == 20, infohashes)
                    assert len(infohashes) > 0
            
            super(TorrentRequestPayload.Implementation, self).__init__(meta)
            self._torrents = torrents

        @property
        def torrents(self):
            return self._torrents
        
class TorrentPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, infohash, timestamp, name, files, trackers):
            assert isinstance(infohash, str), 'infohash is a %s'%type(infohash)
            assert len(infohash) == 20, 'infohash has length %d'%len(infohash)
            assert isinstance(timestamp, (int, long))
            
            assert isinstance(name, unicode)
            assert isinstance(files, tuple)
            for path, length in files:
                assert isinstance(path, unicode)
                assert isinstance(length, (int, long))
                
            assert isinstance(trackers, tuple)
            for tracker in trackers:
                assert isinstance(tracker, str), 'tracker is a %s'%type(tracker)
            
            super(TorrentPayload.Implementation, self).__init__(meta)
            self._infohash = infohash
            self._timestamp = timestamp
            self._name = name
            self._files = files
            self._trackers = trackers

        @property
        def infohash(self):
            return self._infohash
        
        @property
        def timestamp(self):
            return self._timestamp
        
        @property
        def name(self):
            return self._name
        
        @property
        def files(self):
            return self._files
        
        @property
        def trackers(self):
            return self._trackers

class PingPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, torrents):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                
                assert isinstance(torrents, list), type(torrents)
                for hash, infohash, seeders, leechers, ago in torrents:
                    assert isinstance(hash, str)
                    assert len(hash) == 20, "%d, %s"%(len(hash), hash)
                    assert isinstance(infohash, str)
                    assert len(infohash) == 20, "%d, %s"%(len(infohash), infohash)
                    assert isinstance(seeders, int)
                    assert 0 <= seeders < 2 ** 16, seeders
                    assert isinstance(leechers, int)
                    assert 0 <= leechers < 2 ** 16, leechers
                    assert isinstance(ago, int)
                    assert 0 <= ago < 2 ** 16, ago
                    
            super(PingPayload.Implementation, self).__init__(meta)
            
            self._identifier = identifier
            self._torrents = torrents

        @property
        def identifier(self):
            return self._identifier
        
        @property
        def torrents(self):
            return self._torrents

class PongPayload(PingPayload):
    pass