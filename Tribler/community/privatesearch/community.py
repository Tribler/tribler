#Written by Niels Zeilemaker
import sys
from os import path
from time import time
from random import random, sample, randint, shuffle, choice
from traceback import print_exc
from Crypto.Util.number import GCD, bytes_to_long, long_to_bytes, inverse
from hashlib import sha1

from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination,\
    CommunityDestination
from Tribler.dispersy.dispersydatabase import DispersyDatabase
from Tribler.dispersy.distribution import DirectDistribution,\
    FullSyncDistribution
from Tribler.dispersy.member import DummyMember, Member
from Tribler.dispersy.message import Message, DelayMessageByProof, DropMessage
from Tribler.dispersy.resolution import PublicResolution

from conversion import SearchConversion, HSearchConversion
from payload import SearchRequestPayload,\
    SearchResponsePayload, TorrentRequestPayload, \
    PingPayload, PongPayload,\
    EncryptedHashResponsePayload, EncryptedResponsePayload,\
    EncryptedIntroPayload, KeyPayload, TorrentPayload, RequestKeyPayload
    
from Tribler.community.channel.preview import PreviewChannelCommunity

from Tribler.dispersy.requestcache import Cache
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME,\
    WalkCandidate, BootstrapCandidate, Candidate
from Tribler.dispersy.dispersy import IntroductionRequestCache
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Crypto.PublicKey import RSA
from Crypto.Random.random import StrongRandom
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.tool.lencoder import log
from Tribler.community.privatesearch.payload import GlobalVectorPayload, EncryptedVectorPayload, EncryptedSumPayload,\
    ExtendedIntroPayload, EncryptedSumsPayload
from Tribler.community.privatesearch.conversion import PSearchConversion
from Tribler.dispersy.script import assert_
from Tribler.community.privatesearch.pallier import pallier_add, pallier_init, pallier_encrypt, pallier_decrypt

if __debug__:
    from Tribler.dispersy.dprint import dprint

DEBUG = False
DEBUG_VERBOSE = False
TTL = 4
NEIGHBORS = 5
ENCRYPTION = True
TASTE_NEIGHBOR = 3
PING_INTERVAL = CANDIDATE_WALK_LIFETIME - 5.0

class SearchCommunity(Community):
    """
    A single community that all Tribler members join and use to disseminate .torrent files.
    """
    @classmethod
    def get_master_members(cls):
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000404a041c3a8415021f193ef0614360b4d99ac8f985eff2259f88f1f64070ae2bcc21c473c9c0b958b39da9ae58d6d0aec316341f65bd7daa42ffd73f5eeee53aa6199793f98afc47f008a601cd659479f801157e7dd69525649d8eec7885bd0d832746c46d067c60341a6d84b12a6e5d3ce25e20352ed8e0ff311e74b801c06286a852976bdba67dfe62dfb75a5b9c0d2".decode("HEX")
        master = Member(master_key)
        return [master]

    @classmethod
    def load_community(cls, master, my_member, integrate_with_tribler = True, ttl = TTL, neighbors = NEIGHBORS, encryption = ENCRYPTION, taste_neighbor = TASTE_NEIGHBOR, max_prefs = None):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler = integrate_with_tribler, ttl = ttl, neighbors = neighbors, encryption = encryption, taste_neighbor=taste_neighbor, max_prefs=max_prefs)
        else:
            return super(SearchCommunity, cls).load_community(master, integrate_with_tribler = integrate_with_tribler, ttl = ttl, neighbors = neighbors, encryption = encryption, taste_neighbor=taste_neighbor, max_prefs=max_prefs)

    def __init__(self, master, integrate_with_tribler = True, ttl = TTL, neighbors = NEIGHBORS, encryption = ENCRYPTION, taste_neighbor = TASTE_NEIGHBOR, max_prefs = None):
        super(SearchCommunity, self).__init__(master)
        
        self.integrate_with_tribler = integrate_with_tribler
        self.ttl = int(ttl)
        self.neighbors = int(neighbors)
        self.encryption = bool(encryption)
        self.taste_neighbor = int(taste_neighbor)
        
        self.taste_buddies = []
        
        #To always perform searches using a peer uncomment/modify the following line
        #self.taste_buddies.append([1, time(), Candidate(("127.0.0.1", 1234), False))
        
        self.key = RSA.generate(1024)
        self.key_n = self.key.key.n
        self.key_e = self.key.key.e
        
        if not max_prefs:
            max_len = self.dispersy_sync_bloom_filter_bits
            max_prefs = max_len/self.key.size()
            max_hprefs = max_len/20
        else:
            max_hprefs = max_prefs 
            
        self.max_prefs = max_prefs
        self.max_h_prefs = max_hprefs
        
        self.search_forward = 0
        self.search_forward_success = 0
        self.search_forward_timeout = 0
        self.search_endpoint = 0
        self.search_cycle_detected = 0
        self.search_megacachesize = 0
        
        self.create_time_encryption = 0.0
        self.receive_time_encryption = 0.0
        self.create_time_decryption = 0.0
        
        if self.integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, TorrentDBHandler, MyPreferenceDBHandler
            from Tribler.Core.CacheDB.Notifier import Notifier
            from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
        
            # tribler channelcast database
            self._channelcast_db = ChannelCastDBHandler.getInstance()
            self._torrent_db = TorrentDBHandler.getInstance()
            self._mypref_db = MyPreferenceDBHandler.getInstance()
            self._notifier = Notifier.getInstance()
            
            # torrent collecting
            self._rtorrent_handler = RemoteTorrentHandler.getInstance()
            
            # fast connecting
            self.dispersy.callback.register(self.fast_walker)
            
        else:
            self._mypref_db = self._torrent_db = self._channelcast_db = Das4DBStub(self._dispersy)
            self._notifier = None
            self._rtorrent_handler = None

    def fast_walker(self):
        for cycle in xrange(10):
            if cycle < 2:
                # poke bootstrap peers
                for candidate in self._dispersy._bootstrap_candidates.itervalues():
                    if __debug__: dprint("extra walk to ", candidate)
                    self.create_introduction_request(candidate, allow_sync=False)

            # request -everyone- that is eligible
            candidates = [candidate for candidate in self._iter_categories([u'walk', u'stumble', u'intro'], once = True) if candidate]
            for candidate in candidates:
                if __debug__: dprint("extra walk to ", candidate)
                self.create_introduction_request(candidate, allow_sync=False)

            # wait for NAT hole punching
            yield 1.0

        if __debug__: dprint("finished")

    def initiate_meta_messages(self):
        return [Message(self, u"search-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SearchRequestPayload(), self._dispersy._generic_timeline_check, self.on_search),
                Message(self, u"search-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SearchResponsePayload(), self._dispersy._generic_timeline_check, self.on_search_response),
                Message(self, u"torrent-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), TorrentRequestPayload(), self._dispersy._generic_timeline_check, self.on_torrent_request),
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=0), TorrentPayload(), self._dispersy._generic_timeline_check, self.on_torrent),
                Message(self, u"ping", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PingPayload(), self._dispersy._generic_timeline_check, self.on_ping),
                Message(self, u"pong", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PongPayload(), self.check_pong, self.on_pong),
                Message(self, u"encrypted-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedResponsePayload(), self.check_ecnr_response, self.on_encr_response),
                Message(self, u"encrypted-hashes", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedHashResponsePayload(), self.check_ecnr_response, self.on_encr_hash_response)
                ]
        
    def _initialize_meta_messages(self):
        Community._initialize_meta_messages(self)

        ori = self._meta_messages[u"dispersy-introduction-request"]
        self._disp_intro_handler = ori.handle_callback
        
        new = Message(self, ori.name, ori.authentication, ori.resolution, ori.distribution, ori.destination, EncryptedIntroPayload(), ori.check_callback, self.on_intro_request)
        self._meta_messages[u"dispersy-introduction-request"] = new
        
    def initiate_conversions(self):
        return [DefaultConversion(self), SearchConversion(self)]

    @property
    def dispersy_auto_download_master_member(self):
        # there is no dispersy-identity for the master member, so don't try to download
        return False
    
    @property
    def dispersy_sync_bloom_filter_strategy(self):
        # disable sync bloom filter
        return lambda: None
    
#    #used by dispersy to choose a peer to introduce
#    def dispersy_yield_random_candidates(self, candidate = None):
#        for random_candidate in Community.dispersy_yield_random_candidates(self, candidate):
#            if not self.is_taste_buddy(random_candidate):
#                yield random_candidate
    
    #used by dispersy to choose a peer to connect to
#    def dispersy_yield_walk_candidates(self):
#        for candidate in Community.dispersy_yield_walk_candidates(self):
#            yield candidate
    
    def add_taste_buddies(self, new_taste_buddies):
        for new_tb_tuple in new_taste_buddies[:]:
            for tb_tuple in self.taste_buddies:
                if tb_tuple[-1].sock_addr == new_tb_tuple[-1].sock_addr:
                    
                    #update similarity
                    tb_tuple[0] = max(new_tb_tuple[0], tb_tuple[0])
                    new_taste_buddies.remove(new_tb_tuple)
                    break
            else:
                if len(self.taste_buddies) < self.taste_neighbor or new_tb_tuple[0] > self.taste_buddies[-1][0]:
                    self.taste_buddies.append(new_tb_tuple)
                    self.dispersy.callback.register(self.create_ping_request, args = (new_tb_tuple[-1],), delay = PING_INTERVAL)
                    
        #self._create_pingpong("ping", [tb_tuple[-1] for tb_tuple in new_taste_buddies])
                    
        self.taste_buddies.sort(reverse = True)
        self.taste_buddies = self.taste_buddies[:10]
        
        if DEBUG:
            print >> sys.stderr, "SearchCommunity: current tastebuddy list", self.taste_buddies
    
    def yield_taste_buddies(self, ignore_candidate = None):
        taste_buddies = self.taste_buddies[:]
        shuffle(taste_buddies)
        
        ignore_sock_addr = ignore_candidate.sock_addr if ignore_candidate else None
        
        for tb_tuple in taste_buddies:
            if tb_tuple[0] and tb_tuple[-1].sock_addr != ignore_sock_addr:
                yield tb_tuple[-1]
    
    def has_taste_buddies(self):
        tbuddies = list(self.yield_taste_buddies())
        return len(tbuddies) > 0
        
    def is_taste_buddy(self, candidate):
        return self.is_taste_buddy_sock(candidate.sock_addr)
            
    def is_taste_buddy_sock(self, sock_addr):
        for tb in self.yield_taste_buddies():
            #TODO: change this for deployment
            if tb.sock_addr[1] == sock_addr[1]:
                return True
            
    def is_taste_buddy_mid(self, mid):
        for tb in self.yield_taste_buddies():
            if mid in [member.mid for member in tb.get_members(self)]:
                return True
            
    class SimilarityRequest(IntroductionRequestCache):
        def __init__(self, key, community, helper_candidate):
            IntroductionRequestCache.__init__(self, community, helper_candidate)
            self.key = key
            self.myList = self.hisList = None
            self.hisListLen = None
            self.isProcessed = False
        
        def is_complete(self):
            return self.myList != None and self.hisList != None and not self.isProcessed
        
        def get_overlap(self):
            myList = [long_to_bytes(infohash) for infohash in self.myList]
            
            if self.community.encryption:
                t1 = time()
                myList = [self.key.decrypt(infohash) for infohash in myList]
                myList = [sha1(infohash).digest() for infohash in myList]
                
                self.community.create_time_decryption += time() - t1
            
            assert all(len(infohash) == 20 for infohash in myList) 
            
            overlap = 0
            for pref in myList:
                if pref in self.hisList:
                    overlap += 1
                    
            return len(self.myList), self.hisListLen, overlap
        
        def on_cleanup(self):
            if not self.isProcessed and not self.community.integrate_with_tribler:
                log('barter.log', "Not processed", candidate = str(self.helper_candidate), mylist = self.myList != None, hislist = self.hisList != None)
            
    def _process(self, candidate, similarity_request):
        myPrefs, hisPrefs, overlap = similarity_request.get_overlap()
        similarity_request.isProcessed = True
        
        if myPrefs > 0 and hisPrefs > 0:
            myRoot = 1.0/(myPrefs ** .5)
            sim = overlap * (myRoot * (1.0/(hisPrefs ** .5)))
            
            if hisPrefs < 40:
                sim = (hisPrefs/40.0) * sim
            
            self.add_taste_buddies([[sim, time(), candidate]])
        else:
            self.add_taste_buddies([[0, time(), candidate]])
    
    def create_introduction_request(self, destination, allow_sync):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        self._dispersy.statistics.walk_attempt += 1
        destination.walk(self, time(), IntroductionRequestCache.timeout_delay)

        advice = True
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash() if preference]
        if not isinstance(destination, BootstrapCandidate) and not self.is_taste_buddy(destination) and len(myPreferences):
            if len(myPreferences) > self.max_prefs:
                myPreferences = sample(myPreferences, self.max_prefs)
            shuffle(myPreferences)
                
            if self.encryption:
                t1 = time()
                myPreferences = [self.key.encrypt(infohash,1)[0] for infohash in myPreferences]
                self.create_time_encryption += time() - t1
                
            myPreferences = [bytes_to_long(infohash) for infohash in myPreferences]
            
            if DEBUG_VERBOSE:
                print >> sys.stderr, "SearchCommunity: sending introduction request to",destination,"containing", len(myPreferences),"hashes", self._mypref_db.getMyPrefListInfohash()
            
            identifier = self._dispersy.request_cache.claim(SearchCommunity.SimilarityRequest(self.key, self, destination))
            payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, myPreferences, self.key_n)

        else:
            if DEBUG_VERBOSE:
                reason = ''
                if isinstance(destination, BootstrapCandidate):
                    reason = 'being bootstrapserver'
                elif self.is_taste_buddy(destination):
                    reason = 'is taste buddy'
                else:
                    reason = 'having no preferences'
                print >> sys.stderr, "SearchCommunity: sending empty-introduction request to",destination,"due to",reason
            
            identifier = self._dispersy.request_cache.claim(IntroductionRequestCache(self, destination))
            payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, None)
                
        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=payload)

        self._dispersy.store_update_forward([request], False, False, True)
        return request
    
    def on_intro_request(self, orig_messages):
        if DEBUG_VERBOSE:
            print >> sys.stderr, "SearchCommunity: got %d introduction requests"%len(orig_messages)
        
        messages = [message for message in orig_messages if not isinstance(self._dispersy.get_candidate(message.candidate.sock_addr), BootstrapCandidate) and message.payload.preference_list]
                    
        #1. fetch my preferences
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash(local = False) if preference]
        myListLen = len(myPreferences)
        
        #2. use subset if we have to many preferences
        if len(myPreferences) > self.max_h_prefs:
            myPreferences = sample(myPreferences, self.max_h_prefs)
    
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, "SearchCommunity: got introduction request from", message.candidate
           
            if self.encryption:
                t1 = time()
                
                #3. construct a rsa key to encrypt my preferences
                his_n = message.payload.key_n
                fake_phi = his_n/2
                while True:
                    e = StrongRandom().randint(1, fake_phi-1)
                    if GCD(e, fake_phi) == 1: break
                
                compatible_key = RSA.construct((his_n, e))
                
                #4. encrypt hislist and mylist + hash mylist
                hisList = [compatible_key.encrypt(infohash,1)[0] for infohash in message.payload.preference_list]
                myList = [compatible_key.encrypt(infohash,1)[0] for infohash in myPreferences]
                myList = [sha1(infohash).digest() for infohash in myList]
                
                self.receive_time_encryption += time() - t1
            else:
                hisList = message.payload.preference_list
                myList = myPreferences
            
            shuffle(hisList)
            shuffle(myList)
            
            #5. create two messages, one containing hislist encrypted with my compatible key, the other mylist only encrypted by the compatible key + hashed
            meta = self.get_meta_message(u"encrypted-response")
            resp_message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(message.payload.identifier, hisList))
            
            meta = self.get_meta_message(u"encrypted-hashes")
            requ_message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(message.payload.identifier, myList, myListLen))
            
            self._dispersy._send([message.candidate], [resp_message, requ_message])
            
            if DEBUG_VERBOSE:
                print >> sys.stderr, "SearchCommunity: sending two messages too", message.candidate
            
        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d"%message.candidate.sock_addr)
                
        self._disp_intro_handler(orig_messages)
    
    def check_ecnr_response(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            
            if not self._dispersy.request_cache.has(message.payload.identifier, SearchCommunity.SimilarityRequest):
                yield DropMessage(message, "invalid response identifier")
                continue
            
            yield message
    
    def on_encr_response(self, messages):
        for message in messages:
            my_request = self._dispersy.request_cache.get(message.payload.identifier, SearchCommunity.SimilarityRequest)
            if my_request:
                my_request.myList = message.payload.preference_list
                if my_request.is_complete():
                    self._process(message.candidate, my_request)
            elif not self.integrate_with_tribler:
                log('barter.log', 'identifier not found!')
                    
    def on_encr_hash_response(self, messages):
        for message in messages:
            my_request = self._dispersy.request_cache.get(message.payload.identifier, SearchCommunity.SimilarityRequest)
            if my_request:
                my_request.hisList = message.payload.preference_list
                my_request.hisListLen = message.payload.len_preference_list
                if my_request.is_complete():
                    self._process(message.candidate, my_request)
            elif not self.integrate_with_tribler:
                log('barter.log', 'identifier not found!')
            
    class SearchRequest(Cache):
        timeout_delay = 30.0
        cleanup_delay = 0.0

        def __init__(self, community, keywords, ttl, callback, results = [], candidate = None):
            self.community = community
            self.keywords = keywords
            self.callback = callback
            self.results = results
            self.candidate = candidate
            
            if self.candidate:
                self.timeout_delay = 5.0
                
            self.timeout_delay += (ttl * 2)
            self.processed = False
        
        def on_success(self, keywords, results, candidate):
            shouldPop = True
            if not self.processed:
                if self.candidate:
                    results.extend(self.results)
                    shuffle(results)
                    
                    self.callback(keywords, results, self.candidate)
                    self.community.search_forward_success += 1
                    self.processed = True
                else:
                    self.callback(keywords, results, candidate)
                    shouldPop = False
                
            return shouldPop
        
        def on_timeout(self):
            # timeout, message was probably lost return our local results
            if not self.processed:
                self.processed = True
                if self.candidate:
                    self.callback(self.keywords, self.results, self.candidate)
                    self.community.search_forward_timeout += 1
                    
                    if DEBUG:
                        print >> sys.stderr, "SearchCommunity: timeout for searchrequest, returning my local results waited for %.1f seconds"%self.timeout_delay
                
    def create_search(self, keywords, callback, identifier = None, ttl = None, nrcandidates = None, bloomfilter = None):
        if identifier == None:
            identifier = self._dispersy.request_cache.claim(SearchCommunity.SearchRequest(self, keywords, self.ttl, callback))
            
        if nrcandidates == None:
            nrcandidates = self.neighbors
        
        if bloomfilter == None:
            bloomfilter = BloomFilter(0.01, 100)
        
        #put local results in bloomfilter
        local_results = self._get_results(keywords, bloomfilter, True)
        
        random_peers, taste_buddies = self.get_randompeers_tastebuddies()
        shuffle(taste_buddies)
        shuffle(random_peers)
        
        candidates = []
        for _ in xrange(nrcandidates):
            if ttl == None:
                _ttl = randint(1, self.ttl)
            else:
                _ttl = ttl
                
            if (_ttl < self.taste_neighbor and taste_buddies) or (taste_buddies and not random_peers):
                candidate = taste_buddies.pop()
            elif random_peers:
                candidate = random_peers.pop()
            else:
                break
            
            #create channelcast request message
            meta = self.get_meta_message(u"search-request")
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(identifier, _ttl, keywords, bloomfilter))
            self._dispersy._send([candidate], [message])
            candidates.append(candidate)
            
        if DEBUG:
            print >> sys.stderr, "SearchCommunity: sending search request for", keywords, "to", map(str, candidates)
        
        return candidates, local_results
    
    def on_search(self, messages):
        for message in messages:
            #detect cycle
            if not self._dispersy.request_cache.has(message.payload.identifier, SearchCommunity.SearchRequest):
                keywords = message.payload.keywords
                bloomfilter = message.payload.bloom_filter
                
                if DEBUG:
                    print >> sys.stderr, "SearchCommunity: got search request for",keywords
                
                results = self._get_results(keywords, bloomfilter, False)
                if not results and DEBUG:
                    print >> sys.stderr, "SearchCommunity: no results"
            
                ttl = message.payload.ttl
                ttl -= randint(0, 1)
                
                if ttl:
                    if DEBUG:
                        print >> sys.stderr, "SearchCommunity: ttl == %d forwarding"%ttl
                    
                    callback = lambda keywords, newresults, candidate, myidentifier = message.payload.identifier: self._create_search_response(myidentifier, newresults, candidate)
                    self._dispersy.request_cache.set(message.payload.identifier, SearchCommunity.SearchRequest(self, keywords, ttl, callback, results, message.candidate))
                    self.create_search(message.payload.keywords, callback, message.payload.identifier, ttl, 1, bloomfilter)
                    
                    self.search_forward += 1
                else:
                    if DEBUG:
                        print >> sys.stderr, "SearchCommunity: ttl == 0 returning"
                    self._create_search_response(message.payload.identifier, results, message.candidate)
                    self.search_endpoint += 1
            else:
                if DEBUG:
                    print >> sys.stderr, "SearchCommunity: cycle detected returning"
                
                self.search_cycle_detected += 1
                self._create_search_response(message.payload.identifier, [], message.candidate)
                
    def _get_results(self, keywords, bloomfilter, local):
        results = []
        dbresults = self._torrent_db.searchNames(keywords, local = local, keys = ['infohash', 'T.name', 'T.length', 'T.num_files', 'T.category_id', 'T.creation_date', 'T.num_seeders', 'T.num_leechers', 'swift_hash', 'swift_torrent_hash'])
        if len(dbresults) > 0:
            for dbresult in dbresults:
                if not (bloomfilter and dbresult[0] in bloomfilter):
                    channel_details = dbresult[-10:]
                    
                    dbresult = list(dbresult[:10])
                    dbresult[1] = unicode(dbresult[1]) + (u"_bf" if bloomfilter else u"_nobf")
                    dbresult[2] = long(dbresult[2])
                    dbresult[3] = int(dbresult[3])
                    dbresult[4] = [self._torrent_db.id2category[dbresult[4]],]
                    dbresult[5] = long(dbresult[5])
                    dbresult[6] = int(dbresult[6] or 0)
                    dbresult[7] = int(dbresult[7] or 0)
                    if dbresult[8]:
                        dbresult[8] = str(dbresult[8])
                    if dbresult[9]:
                        dbresult[9] = str(dbresult[9])
                    
                    if channel_details[1]:
                        channel_details[1] = str(channel_details[1])
                    dbresult.append(channel_details[1])
                    
                    results.append(tuple(dbresult))
                    
                    if bloomfilter:
                        bloomfilter.add(dbresult[0])
                        
                    if len(results) == 25:
                        break
        return results
    
    def _create_search_response(self, identifier, results, candidate):
        #create search-response message
        meta = self.get_meta_message(u"search-response")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(identifier, results))
        self._dispersy._send([candidate], [message])
        
        if DEBUG:
            print >> sys.stderr, "SearchCommunity: returning",len(results),"results to",candidate
    
    def on_search_response(self, messages):
        for message in messages:
            #fetch callback using identifier
            search_request = self._dispersy.request_cache.get(message.payload.identifier, SearchCommunity.SearchRequest)
            if search_request:
                if DEBUG:
                    print >> sys.stderr, "SearchCommunity: got search response for",search_request.keywords, len(message.payload.results), message.candidate
                
                if len(message.payload.results)> 0:
                    self.search_megacachesize = self._torrent_db.on_search_response(message.payload.results)
                    
                removeCache = search_request.on_success(search_request.keywords, message.payload.results, message.candidate)
                if removeCache:
                    self._dispersy.request_cache.pop(message.payload.identifier, SearchCommunity.SearchRequest)
                
                #see if we need to join some channels
                channels = set([result[10] for result in message.payload.results if result[10]])
                if channels:
                    channels = self._get_unknown_channels(channels)
                
                    if DEBUG:
                        print >> sys.stderr, "SearchCommunity: joining %d preview communities"%len(channels)
                    
                    for cid in channels:
                        community = self._get_channel_community(cid)
                        community.disp_create_missing_channel(message.candidate, includeSnapshot = False)
            else:
                if DEBUG:
                    print >> sys.stderr, "SearchCommunity: got search response identifier not found", message.payload.identifier

    class PingRequestCache(IntroductionRequestCache):
        def __init__(self, community, candidate):
            IntroductionRequestCache.__init__(self, community, None)
            self.candidate = candidate
            self.processed = False
        
        def on_success(self):
            self.processed = True
        
        def on_timeout(self):
            if not self.processed:
                if DEBUG:
                    print >> sys.stderr, "SearchCommunity: no response on ping, removing from taste_buddies", self.candidate
                self.community.removeTastebuddy(self.candidate)
    
    def removeTastebuddy(self, candidate):
        remove = None

        removeIf = time() - CANDIDATE_WALK_LIFETIME
        for taste_buddy in self.taste_buddies:
            if taste_buddy[-1] == candidate:
                if taste_buddy[1] < removeIf:
                    remove = taste_buddy
                break
    
        if remove:
            self.taste_buddies.remove(remove)
        
    def resetTastebuddy(self, candidate):
        for taste_buddy in self.taste_buddies:
            if taste_buddy[2].sock_addr in candidate.sock_addr:
                taste_buddy[1] = time()
    
    def create_ping_request(self, candidate):
        while self.is_taste_buddy(candidate):
            self._create_pingpong(u"ping", [candidate])
            
            yield PING_INTERVAL
    
    def on_ping(self, messages):
        candidates = [message.candidate for message in messages]
        identifiers = [message.payload.identifier for message in messages]
        
        self._create_pingpong(u"pong", candidates, identifiers)
        
        for message in messages:
            if len(message.payload.torrents)> 0:
                self.search_megacachesize = self._torrent_db.on_pingpong(message.payload.torrents)
        
            self.resetTastebuddy(message.candidate)
                
    def check_pong(self, messages):
        for message in messages:
            accepted, _ = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            
            if not self._dispersy.request_cache.has(message.payload.identifier, SearchCommunity.PingRequestCache):
                yield DropMessage(message, "invalid response identifier")
                continue
            
            yield message
    
    def on_pong(self, messages):
        for message in messages:
            request = self._dispersy.request_cache.pop(message.payload.identifier, SearchCommunity.PingRequestCache)
            request.on_success()
            
            if len(message.payload.torrents)> 0:
                self.search_megacachesize = self._torrent_db.on_pingpong(message.payload.torrents)
            
            self.resetTastebuddy(message.candidate)
    
    def _create_pingpong(self, meta_name, candidates, identifiers = None):
#        max_len = self.dispersy_sync_bloom_filter_bits/8
#        limit = int(max_len/44)
#        
#        #we want roughly 1/3 random, 2/3 recent
#        limitRecent = int(limit * 0.66)
#        limitRandom = limit - limitRecent
#        
#        torrents = self._torrent_db.getRecentlyCollectedSwiftHashes(limit = limitRecent) or []
#        if len(torrents) == limitRecent:
#            leastRecent = torrents[-1][5]
#            randomTorrents = self._torrent_db.getRandomlyCollectedSwiftHashes(leastRecent, limit = limitRandom) or []
#        else:
#            randomTorrents = []
#        
#        #combine random and recent + shuffle to obscure categories
#        torrents += randomTorrents
#        torrents = [tor[:5] for tor in torrents] 
#        shuffle(torrents)
        
        torrents = []
        
        for index, candidate in enumerate(candidates):
            if identifiers:
                identifier = identifiers[index]
            else:
                identifier = self._dispersy.request_cache.claim(SearchCommunity.PingRequestCache(self, candidate))
            
            #create torrent-collect-request/response message
            meta = self.get_meta_message(meta_name)
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(identifier, torrents))
            self._dispersy._send([candidate], [message])
    
            if DEBUG:
                print >> sys.stderr, "SearchCommunity: send", meta_name, "to", candidate
                
    def create_torrent_request(self, torrents, candidate):
        torrentdict = {}
        for torrent in torrents:
            if isinstance(torrent, list):
                cid, infohash = torrent
            else:
                cid = self._master_member.mid
                infohash = torrent
            torrentdict.setdefault(cid, set()).add(infohash)
        
        #create torrent-request message
        meta = self.get_meta_message(u"torrent-request")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(torrentdict,))
        self._dispersy._send([candidate], [message])
        
        if DEBUG:
            nr_requests = sum([len(cid_torrents) for cid_torrents in torrentdict.values()])
            print >> sys.stderr, "SearchCommunity: requesting",nr_requests,"TorrentMessages from",candidate
    
    def on_torrent_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                requested_packets.extend(self._get_packets_from_infohashes(cid, torrents))
                
            if requested_packets:
                self._dispersy.statistics.dict_inc(self._dispersy.statistics.outgoing, u"torrent-response", len(requested_packets))
                self._dispersy.endpoint.send([message.candidate], requested_packets)
            
            if DEBUG:
                print >> sys.stderr, "SearchCommunity: got request for ",len(requested_packets),"torrents from",message.candidate
                
    def on_torrent(self, messages):
        for message in messages:
            self._torrent_db.addExternalTorrentNoDef(message.payload.infohash, message.payload.name, message.payload.files, message.payload.trackers, message.payload.timestamp, "DISP_SC", {'dispersy_id':message.packet_id})
    
    def _get_channel_id(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20
        
        return self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(cid),))
    
    def _get_unknown_channels(self, cids):
        assert all(isinstance(cid, str) for cid in cids)
        assert all(len(cid) == 20 for cid in cids)

        parameters = u",".join(["?"] * len(cids))
        known_cids = self._channelcast_db._db.fetchall(u"SELECT dispersy_cid FROM Channels WHERE dispersy_cid in ("+parameters+")", map(buffer, cids))
        known_cids = map(str, known_cids)
        return [cid for cid in cids if cid not in known_cids]
        
    def _get_channel_community(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20
        
        try:
            return self._dispersy.get_community(cid, True)
        except KeyError:
            if __debug__: dprint("join preview community ", cid.encode("HEX"))
            return PreviewChannelCommunity.join_community(DummyMember(cid), self._my_member, self.integrate_with_tribler) 

    def _get_packets_from_infohashes(self, cid, infohashes):
        packets = []
        
        def add_packet(dispersy_id):
            if dispersy_id and dispersy_id > 0:
                try:
                    packet = self._get_packet_from_dispersy_id(dispersy_id, "torrent")
                    if packet:
                        packets.append(packet)
                except RuntimeError:
                    pass
        
        if cid == self._master_member.mid:
            channel_id = None
        else:
            channel_id = self._get_channel_id(cid)
        
        for infohash in infohashes:
            dispersy_id = None
            
            #1. try to find the torrentmessage for this cid, infohash combination
            if channel_id:
                dispersy_id = self._channelcast_db.getTorrentFromChannelId(channel_id, infohash, ['ChannelTorrents.dispersy_id'])
            else:
                torrent = self._torrent_db.getTorrent(infohash, ['dispersy_id', 'torrent_file_name'], include_mypref = False)
                if torrent:
                    dispersy_id = torrent['dispersy_id'] 

                    #2. if still not found, create a new torrentmessage and return this one
                    if not dispersy_id and torrent['torrent_file_name'] and path.isfile(torrent['torrent_file_name']):
                        message = self.create_torrent(torrent['torrent_file_name'], store = True, update = False, forward = False)
                        if message:
                            packets.append(message.packet)
            add_packet(dispersy_id)
        return packets

    def _get_packet_from_dispersy_id(self, dispersy_id, messagename):
        # 1. get the packet
        try:
            packet, packet_id = self._dispersy.database.execute(u"SELECT sync.packet, sync.id FROM community JOIN sync ON sync.community = community.id WHERE sync.id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError("Unknown dispersy_id")
    
        return str(packet)
    
    def get_nr_connections(self):
        return len(self.get_connections())
    
    def get_connections(self, nr = 10, ignore_candidate = None):
        #use taste buddies and fill with random candidates
        candidates = set(self.yield_taste_buddies(ignore_candidate))
        if len(candidates) < nr:
            sock_addresses = set(candidate.sock_addr for candidate in candidates)
            if ignore_candidate:
                sock_addresses.add(ignore_candidate.sock_addr)
            
            for candidate in self.dispersy_yield_candidates():
                if candidate.sock_addr not in sock_addresses:
                    candidates.add(candidate)
                    sock_addresses.add(candidate.sock_addr)
                    
                if len(candidates) == nr:
                    break
                
        elif len(candidates) > nr:
            candidates = sample(candidates, nr)
            
        return candidates
    
    def get_randompeers_tastebuddies(self):
        random_peers = []
        taste_buddies = list(self.yield_taste_buddies())
        
        sock_addresses = set(candidate.sock_addr for candidate in taste_buddies)
        for candidate in self.dispersy_yield_candidates():
            if candidate.sock_addr not in sock_addresses:
                random_peers.append(candidate)
                sock_addresses.add(candidate.sock_addr)
        
        return random_peers, taste_buddies

class HSearchCommunity(SearchCommunity):
    
    def __init__(self, master, integrate_with_tribler = True, ttl = TTL, neighbors = NEIGHBORS, encryption = ENCRYPTION, taste_neighbor = TASTE_NEIGHBOR, max_prefs = None):
        SearchCommunity.__init__(self, master, integrate_with_tribler, ttl, neighbors, encryption, taste_neighbor, max_prefs=max_prefs)
        self.preference_cache = []
    
    def initiate_meta_messages(self):
        messages = SearchCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"request-key", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), RequestKeyPayload(), self._dispersy._generic_timeline_check, self.on_keyrequest))
        messages.append(Message(self, u"encryption-key", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), KeyPayload(), self._dispersy._generic_timeline_check, self.on_key))
        return messages
    
    def initiate_conversions(self):
        return [DefaultConversion(self), SearchConversion(self), HSearchConversion(self)]
        
    def create_introduction_request(self, destination, allow_sync):
        if not isinstance(destination, BootstrapCandidate) and not self.is_taste_buddy(destination):
            self.send_keyrequest(destination)
        else:
            self.send_introduction_request(destination)
    
    def send_introduction_request(self, destination, preference_list = None):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        self._dispersy.statistics.walk_attempt += 1
        destination.walk(self, time(), IntroductionRequestCache.timeout_delay)
        
        advice = True
        identifier = self._dispersy.request_cache.claim(IntroductionRequestCache(self, destination))
        
        if preference_list:
            preference_list = [bytes_to_long(infohash) for infohash in preference_list]
        
        payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, preference_list)
        
        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=payload)

        self._dispersy.store_update_forward([request], False, False, True)
        return request

    def on_intro_request(self, messages):
        for message in messages:
            candidate = self._dispersy.get_walkcandidate(message, self)
            if candidate and message.payload.preference_list:
                self.preference_cache.append([time(), set(message.payload.preference_list), candidate])
        
        self._disp_intro_handler(messages)
        
        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d"%message.candidate.sock_addr)
    
    def send_keyrequest(self, destination):
        identifier = self._dispersy.request_cache.claim(HSearchCommunity.HSimilarityRequest(self.key, self, destination))
        
        meta_request = self.get_meta_message(u"request-key")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, self.key_n, self.key_e))

        self._dispersy.store_update_forward([request], False, False, True)
        return request
    
    def on_keyrequest(self, messages):
        for message in messages:
            meta_request = self.get_meta_message(u"encryption-key")
            response = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    destination=(message.candidate,),
                                    payload=(self.key_n, self.key_e))
            
            self._dispersy.store_update_forward([response], False, False, True)
        self.__encrypt_myprefs(messages, self.send_encrypted_hashes)
    
    def on_key(self, messages):
        self.__encrypt_myprefs(messages, lambda message, preference_list: self.send_introduction_request(message.candidate, preference_list))
    
    class HSimilarityRequest(SearchCommunity.SimilarityRequest):
        def __init__(self, key, community, helper_candidate):
            SearchCommunity.SimilarityRequest.__init__(self, key, community, helper_candidate)
            self.myList = [preference for preference in community._mypref_db.getMyPrefListInfohash() if preference] 
        
        def get_overlap(self):
            if self.community.encryption:
                t1 = time()
                self.myList = [self.key.encrypt(infohash,1)[0] for infohash in self.myList]
                self.myList = [sha1(infohash).digest() for infohash in self.myList]
                self.community.create_time_encryption += time() - t1
    
            overlap = 0
            for myPref in self.myList:
                if myPref in self.hisList:
                    overlap += 1
            
            return len(self.myList), self.hisListLen, overlap
        
    def send_encrypted_hashes(self, message, preferences):
        meta = self.get_meta_message(u"encrypted-hashes")
        request = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), 
                            destination=(message.candidate,),
                            payload=(message.payload.identifier, preferences, len(preferences)))
        
        self._dispersy.store_update_forward([request], False, False, True)
        return request
    
    def __encrypt_myprefs(self, messages, callback):
        #1. fetch my preferences
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash(local = False) if preference]
        if len(myPreferences) > self.max_h_prefs:
            myPreferences = sample(myPreferences, self.max_h_prefs)
        
        for message in messages:
            shuffle(myPreferences)
            
            if self.encryption:
                t1 = time()
                
                #2. construct a rsa key to encrypt my preferences
                his_n = message.payload.key_n
                his_e = message.payload.key_e
                compatible_key = RSA.construct((his_n, his_e))
                
                #3. encrypt and hash my preferences
                encMyPreferences = [compatible_key.encrypt(infohash,1)[0] for infohash in myPreferences]
                encMyPreferences = [sha1(infohash).digest() for infohash in encMyPreferences]
                self.receive_time_encryption += time() - t1
            else:
                encMyPreferences = myPreferences
            
            callback(message, encMyPreferences)
            
            if DEBUG:
                print >> sys.stderr, "SearchCommunity: sending one message too", message.candidate
    
    def get_preferences(self, candidate):
        for time, preferenceset, pref_candidate in self.preference_cache:
            if pref_candidate.sock_addr == candidate.sock_addr:
                return preferenceset
            
    def match_preferences(self, preference_set):
        #cleanup of invalid candidates
        timeout = time() - CANDIDATE_WALK_LIFETIME
        for i in range(len(self.preference_cache), 0, -1):
            if self.preference_cache[i-1][0] < timeout and not self.is_taste_buddy(self.preference_cache[i-1][2]):
                del self.preference_cache[i-1]
                
        matches = []
        for _, other_preference_set, candidate in self.preference_cache:
            overlap = len(other_preference_set & preference_set)
            if overlap > 0:
                matches.append((overlap, candidate))
                
        matches.sort(reverse = True)
        return [candidate for _,candidate in matches]
            
    def dispersy_yield_random_candidates(self, candidate = None):
        if candidate:
            preferences = self.get_preferences(candidate)
            if preferences:
                for matching_candidate in self.match_preferences(preferences):
                    if matching_candidate.sock_addr != candidate.sock_addr:
                        yield matching_candidate
        
        for random_candidate in SearchCommunity.dispersy_yield_random_candidates(self, candidate):
            yield random_candidate
            
class PSearchCommunity(SearchCommunity):
    
    def __init__(self, master, integrate_with_tribler = True, ttl = TTL, neighbors = NEIGHBORS, encryption = ENCRYPTION, taste_neighbor = TASTE_NEIGHBOR, max_prefs = None):
        SearchCommunity.__init__(self, master, integrate_with_tribler, ttl, neighbors, encryption, taste_neighbor, max_prefs)
        self.key_n, self.key_n2, self.key_g, self.key_lambda, self.key_decryption = pallier_init(self.key)
        
        self.possible_taste_buddies = []
        self.requested_introductions = {}
        
        self.my_vector_cache = [None, None]
    
    def initiate_meta_messages(self):
        messages = SearchCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"sum-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self._dispersy._generic_timeline_check, self.on_sum_request))
        messages.append(Message(self, u"sums-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self._dispersy._generic_timeline_check, self.on_sums_request))
        messages.append(Message(self, u"global-vector", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), GlobalVectorPayload(), self._dispersy._generic_timeline_check, self.on_global_vector))
        messages.append(Message(self, u"encrypted-sum", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumPayload(), self.check_encr_sum, self.on_encr_sum))
        messages.append(Message(self, u"encrypted-sums", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumsPayload(), self._dispersy._generic_timeline_check, self.on_encr_sums))
        return messages

    def _initialize_meta_messages(self):
        Community._initialize_meta_messages(self)

        ori = self._meta_messages[u"dispersy-introduction-request"]
        self._disp_intro_handler = ori.handle_callback
        
        new = Message(self, ori.name, ori.authentication, ori.resolution, ori.distribution, ori.destination, ExtendedIntroPayload(), ori.check_callback, self.on_intro_request)
        self._meta_messages[u"dispersy-introduction-request"] = new
    
    def initiate_conversions(self):
        return [DefaultConversion(self), SearchConversion(self), PSearchConversion(self)]
    
    def add_possible_taste_buddies(self, possibles):
        possible_mids = {}
        for i,possible in enumerate(self.possible_taste_buddies):
            possible_mids[possible[2]] = i

        #add all possibles and sort descending by sum, time received
        for possible in possibles:
            if possible[2] in possible_mids:
                self.possible_taste_buddies[possible_mids[possible[2]]] = possible
            else:
                self.possible_taste_buddies.append(possible)
        
        self.possible_taste_buddies.sort(reverse = True)
        
        if DEBUG and possibles:
            print >> sys.stderr, "PSearchCommunity: got possible taste buddies, current list", len(self.possible_taste_buddies), [possible[0] for possible in self.possible_taste_buddies]
    
    def has_possible_taste_buddies(self, candidate):
        for _,_,_,from_candidate in self.possible_taste_buddies:
            if from_candidate.sock_addr == candidate.sock_addr:
                return True
        return False
    
    def get_low_sum(self):
        if len(self.taste_buddies) == 10:
            return self.taste_buddies[-1][0]
        return 0
        
    def get_most_similar(self, candidate):
        #clean possible taste buddies, remove all entries older than 60s
        to_be_removed = time() - 60
        low_sum = self.get_low_sum()
        
        for i in range(len(self.possible_taste_buddies)- 1, -1, -1):
            if self.possible_taste_buddies[i][0] <= low_sum or self.possible_taste_buddies[i][1] < to_be_removed or self.is_taste_buddy_mid(self.possible_taste_buddies[i][2]):
                self.possible_taste_buddies.pop(i)
                    
        if self.possible_taste_buddies:                
            most_similar = self.possible_taste_buddies.pop(0)
            return most_similar[3], most_similar[2]
        
        return candidate, None
    
    def create_introduction_request(self, destination, allow_sync):
        if not isinstance(destination, BootstrapCandidate) and not self.is_taste_buddy(destination) and not self.has_possible_taste_buddies(destination) and allow_sync:
            self.send_sums_request(destination)
        else:
            self.send_introduction_request(destination)
            
    def send_introduction_request(self, destination, introduce_me_to = None):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        self._dispersy.statistics.walk_attempt += 1
        destination.walk(self, time(), IntroductionRequestCache.timeout_delay)
        
        advice = True
        identifier = self._dispersy.request_cache.claim(IntroductionRequestCache(self, destination))
        payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, introduce_me_to)
        
        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=payload)

        self._dispersy._forward([request])
    
    def on_intro_request(self, messages):
        for message in messages:
            if message.payload.introduce_me_to:
                candidate = self._dispersy.get_walkcandidate(message, self)
                self.requested_introductions[candidate] = self.get_candidate_mid(message.payload.introduce_me_to)
        
        self._disp_intro_handler(messages)
        
        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d"%message.candidate.sock_addr)
                
    def dispersy_yield_random_candidates(self, candidate = None):
        if candidate:
            if candidate in self.requested_introductions:
                intro_me_candidate = self.requested_introductions[candidate]
                del self.requested_introductions[candidate]
                yield intro_me_candidate
        
        for random_candidate in SearchCommunity.dispersy_yield_random_candidates(self, candidate):
            yield random_candidate
    
    def send_sums_request(self, destination):
        identifier = self._dispersy.request_cache.claim(IntroductionRequestCache(self, destination))
        
        global_vector_request, global_vector = self.create_global_vector(destination, identifier)
        
        str_global_vector = str(global_vector)
        if self.my_vector_cache[0] == str_global_vector: 
            encrypted_vector = self.my_vector_cache[1]
        else:
            my_vector = self.get_my_vector(global_vector)
            if self.encryption:
                
                t1 = time()
                encrypted_vector = []
                for element in my_vector:
                    cipher = pallier_encrypt(element, self.key_g, self.key_n, self.key_n2)
                    encrypted_vector.append(cipher)

                self.create_time_encryption += time() - t1
            else:
                encrypted_vector = my_vector
        
            self.my_vector_cache = [str_global_vector, encrypted_vector]
        
        meta_request = self.get_meta_message(u"sums-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, self.key_n, encrypted_vector))

        self._dispersy._forward([request])
        self._dispersy._forward([global_vector_request])
    
    def create_global_vector(self, destination, identifier):
        #1. fetch my preferences
        global_vector = [long(preference) for preference in self._mypref_db.getMyPrefListInfohash(local = False) if preference]
        
        #2. reduce/extend the vector in size
        if len(global_vector) > self.max_prefs:
            global_vector = sample(global_vector, self.max_prefs)
        
        elif len(global_vector) < self.max_prefs:
            global_vector += [0l] * (self.max_prefs - len(global_vector))
            
        assert_(len(global_vector) == self.max_prefs, 'vector sizes not equal')
        
        meta_request = self.get_meta_message(u"global-vector")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, global_vector))

        return request, global_vector
    
    def get_my_vector(self, global_vector):
        my_preferences = set([long(preference) for preference in self._mypref_db.getMyPrefListInfohash(local = False) if preference])
        my_vector = [0l] * len(global_vector)
        for i, element in enumerate(global_vector):
            if element in my_preferences:
                my_vector[i] = 1l 
        return my_vector
    
    def on_sums_request(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, "PSearchCommunity: got sums request"
            
            #get candidates to forward requests to, excluding the requesting peer
            candidates = self.get_connections(10, message.candidate)
            
            #create RPSimilarityRequest to use as object to collect all sums
            self._dispersy.request_cache.set(message.payload.identifier, PSearchCommunity.RPSimilarityRequest(self, message.candidate, candidates))
            
            #process this request as a normal sum request
            self.on_sum_request([message])
            
            #forward it to others
            meta_request = self.get_meta_message(u"sum-request")
            request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                payload=(message.payload.identifier, message.payload.key_n, message.payload.preference_list))
            
            self._dispersy._send(candidates, [request])
            
    def on_sum_request(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, "PSearchCommunity: got sum request"
            
            #create a PSimilarityRequest to store this request for sum
            if not self._dispersy.request_cache.has(message.payload.identifier, PSearchCommunity.PSimilarityRequest):
                self._dispersy.request_cache.set(message.payload.identifier, PSearchCommunity.PSimilarityRequest(self, message.candidate))

            #fetch request object, and store user_n and user_vector            
            request = self._dispersy.request_cache.get(message.payload.identifier, PSearchCommunity.PSimilarityRequest)
            request.user_n = message.payload.key_n
            request.user_vector = message.payload.preference_list
            
            #if request is complete, process it
            if request.is_complete():
                request.process()
                
    def on_global_vector(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, "PSearchCommunity: got global vector"
            
            if not self._dispersy.request_cache.has(message.payload.identifier, PSearchCommunity.PSimilarityRequest):
                self._dispersy.request_cache.set(message.payload.identifier, PSearchCommunity.PSimilarityRequest(self, message.candidate))
            
            request = self._dispersy.request_cache.get(message.payload.identifier, PSearchCommunity.PSimilarityRequest)
            request.global_vector = message.payload.preference_list
            
            if isinstance(request, PSearchCommunity.RPSimilarityRequest):
                if request.requested_candidates:
                    if DEBUG_VERBOSE:
                        print >> sys.stderr, "PSearchCommunity: forwarding global vector", request.requested_candidates
                    self._dispersy._send(request.requested_candidates, [message])
            
            if request.is_complete():
                request.process()
    
    class PSimilarityRequest(Cache):
        timeout_delay = 3.5
        
        def __init__(self, community, requesting_candidate):
            self.community = community
            self.requesting_candidate = requesting_candidate
            
            self.user_n = None
            self.user_vector = None
            self.global_vector = None
            self.isProcessed = False
        
        def is_complete(self):
            return self.global_vector != None and self.user_vector != None and self.user_n != None and not self.isProcessed
        
        def get_sum(self):
            if not self.isProcessed:
                my_vector = self.community.get_my_vector(self.global_vector)
                assert_(len(self.global_vector) == len(self.user_vector) and len(self.global_vector) == len(my_vector), "vector sizes not equal %d vs %d vs %d" % (len(self.global_vector), len(self.user_vector), len(my_vector)))
    
                if self.community.encryption:
                    _sum = 1l
                    
                    t1 = time()
                    user_n2 = pow(self.user_n, 2)
                    
                    for i, element in enumerate(self.user_vector):
                        if my_vector[i]:
                            _sum = pallier_add(_sum, element, user_n2)
                            
                    self.community.receive_time_encryption += time() - t1
                else:
                    _sum = 0l
                    for i, element in enumerate(self.user_vector):
                        if my_vector[i] and element:
                            _sum += 1
                
                if DEBUG_VERBOSE:
                    print >> sys.stderr, "PSearchCommunity: calculated sum", _sum
                        
                return _sum
            
        def process(self):
            if not self.isProcessed:
                _sum = self.get_sum()
            
                meta_request = self.community.get_meta_message(u"encrypted-sum")
                response = meta_request.impl(authentication=(self.community.my_member,),
                                        distribution=(self.community.global_time,),
                                        destination=(self.requesting_candidate,),
                                        payload=(self.identifier, _sum))
        
                self.community._dispersy._forward([response])
                self.isProcessed = True
                
                if DEBUG_VERBOSE:
                    print >> sys.stderr, "PSearchCommunity: processed PSimilarityRequest"
                    
                self.community._dispersy.request_cache.pop(self.identifier, PSearchCommunity.PSimilarityRequest)
    
        def on_timeout(self):
            if DEBUG:
                print >> sys.stderr, "PSearchCommunity: timeout PSimilarityRequest", self.global_vector != None, self.user_vector != None
    
    class RPSimilarityRequest(PSimilarityRequest):
        timeout_delay = 7.0
        def __init__(self, community, requesting_candidate, requested_candidates):
            PSearchCommunity.PSimilarityRequest.__init__(self, community, requesting_candidate)
            
            self.requested_candidates = requested_candidates
            self.requested_mids = set()
            for candidate in self.requested_candidates:
                for member in candidate.get_members(community):
                    self.requested_mids.add(member.mid)
                
            self.received_candidates = []
            self.received_sums = []
        
        def add_sum(self, candidate_mid, _sum):
            if DEBUG_VERBOSE:
                print >> sys.stderr, "PSearchCommunity: got sum in RPSimilarityRequest"
            
            if candidate_mid in self.requested_mids:
                if DEBUG_VERBOSE:
                    print >> sys.stderr, "PSearchCommunity: added sum in RPSimilarityRequest"
                
                self.received_candidates.append(candidate_mid)
                self.received_sums.append((candidate_mid, _sum))
        
        def is_complete(self):
            return PSearchCommunity.PSimilarityRequest.is_complete(self) and len(self.received_sums) == len(self.requested_candidates)
        
        def process(self):
            if not self.isProcessed:
                _sum = self.get_sum()
                
                #TODO: instead of sock_addr, we should reply with the identifier of a peer
                meta_request = self.community.get_meta_message(u"encrypted-sums")
                response = meta_request.impl(authentication=(self.community.my_member,),
                                        distribution=(self.community.global_time,),
                                        destination=(self.requesting_candidate,),
                                        payload=(self.identifier, _sum, self.received_sums))
        
                self.community._dispersy._forward([response])
                self.isProcessed = True
                
                if DEBUG_VERBOSE:
                    print >> sys.stderr, "PSearchCommunity: processed RPSimilarityRequest"
                    
                self.community._dispersy.request_cache.pop(self.identifier, PSearchCommunity.RPSimilarityRequest)
                
        def on_timeout(self):
            if PSearchCommunity.PSimilarityRequest.is_complete(self):
                self.process()

    def check_encr_sum(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            
            if not self._dispersy.request_cache.has(message.payload.identifier, PSearchCommunity.RPSimilarityRequest):
                yield DropMessage(message, "invalid response identifier")
                continue
            
            yield message
    
    def on_encr_sum(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, "PSearchCommunity: received sum", message.payload._sum
            
            request = self._dispersy.request_cache.get(message.payload.identifier, PSearchCommunity.RPSimilarityRequest)
            request.add_sum(message.authentication.member.mid, message.payload._sum)
            
            if request.is_complete():
                request.process()
    
    def on_encr_sums(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, "PSearchCommunity: received sums", message.payload._sum
            
            if self.encryption:
                t1 = time()
                
                _sums = [[pallier_decrypt(_sum, self.key_n, self.key_n2, self.key_lambda, self.key_decryption), time(), candidate_mid, message.candidate] for candidate_mid, _sum in message.payload.sums]
                _sum = pallier_decrypt(message.payload._sum, self.key_n, self.key_n2, self.key_lambda, self.key_decryption)
                
                self.create_time_decryption += time() - t1
            else:
                _sums = [[_sum, time(), candidate_mid, message.candidate] for candidate_mid, _sum in message.payload.sums]
                _sum = message.payload._sum
                
            self.add_taste_buddies([[_sum, time(), message.candidate]])
            
            _sums = [possible for possible in _sums if possible[0]]
            if _sums:
                self.add_possible_taste_buddies(_sums)

            destination, introduce_me_to = self.get_most_similar(message.candidate)
            self.send_introduction_request(destination, introduce_me_to)
            
            if DEBUG and introduce_me_to:
                print >> sys.stderr, "PSearchCommunity: asking candidate %s to introduce me to %s after receiving sums from %s"%(destination, introduce_me_to.encode("HEX"), message.candidate)
        
class Das4DBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy
        
        self.myPreferences = set()
        self.myTestPreferences = set()
        
        self.myMegaCache = []
        self.myMegaSet = set()
        self.id2category = {1:u''}

    def addMyPreference(self, torrent_id, data):
        infohash = str(torrent_id)
        self.myPreferences.add(infohash)
    
    def addTestPreference(self, torrent_id):
        infohash = str(torrent_id)
        self.myTestPreferences.add(infohash)

    def getMyPrefListInfohash(self, limit = None, local = True):
        preferences = self.myPreferences
        if not local:
            preferences  = preferences | self.myTestPreferences
        preferences = list(preferences)
        
        if limit:
            return preferences[:limit]
        return preferences
    
    def searchNames(self, keywords, local = True, keys = []):
        my_preferences = set(self.getMyPrefListInfohash(local = local)) | self.myMegaSet

        results = []
        for keyword in keywords:
            infohash = str(keyword)
            if infohash in my_preferences:
                results.append((infohash, unicode(self._dispersy._lan_address), 1L, 1, 1, 0L, 0, 0, None, None, None, None, '', '', 0, 0, 0, 0, 0, False))
        return results
    
    def on_search_response(self, results):
        for result in results:
            if result[0] not in self.myMegaSet:
                self.myMegaCache.append((result[0], result[0], 0, 0, 0, time()))
                self.myMegaSet.add(result[0])
        return len(self.myMegaSet)

    def on_pingpong(self, torrents):
        unknown_torrents = [[infohash,] for infohash,_,_,_,_ in torrents if infohash not in self.myMegaSet]
        if len(unknown_torrents) > 5:
            unknown_torrents = sample(unknown_torrents, 5)
        return self.on_search_response(unknown_torrents)
    
    def getRecentlyCollectedSwiftHashes(self, limit = None):
        if limit:
            return self.myMegaCache[-limit:]
        return self.myMegaCache
        
    def getRandomlyCollectedSwiftHashes(self, leastRecent = 0, limit = None):
        megaCache = self.myMegaCache[:]
        shuffle(megaCache)
        
        if limit:
            return megaCache[:limit]
        return megaCache
        