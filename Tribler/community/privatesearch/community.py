# Written by Niels Zeilemaker
import sys
from os import path
from time import time
from random import sample, randint, shuffle, random
from Crypto.Util.number import bytes_to_long, long_to_bytes

from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination, \
    CommunityDestination
from Tribler.dispersy.dispersydatabase import DispersyDatabase
from Tribler.dispersy.distribution import DirectDistribution, \
    FullSyncDistribution
from Tribler.dispersy.member import DummyMember, Member
from Tribler.dispersy.message import Message, DelayMessageByProof, DropMessage
from Tribler.dispersy.resolution import PublicResolution

from conversion import SearchConversion
from payload import *
from Tribler.community.channel.preview import PreviewChannelCommunity

from Tribler.dispersy.requestcache import Cache
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME, \
    WalkCandidate, BootstrapCandidate, Candidate
from Tribler.dispersy.dispersy import IntroductionRequestCache
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.tool.lencoder import log
from Tribler.community.privatesearch.conversion import PSearchConversion, \
    HSearchConversion
from Tribler.dispersy.script import assert_

from Tribler.community.privatesearch.pallier import pallier_add, pallier_init, pallier_encrypt, pallier_decrypt
from Tribler.community.privatesearch.rsa import rsa_init, rsa_encrypt, rsa_decrypt, rsa_compatible, hash_element

if __debug__:
    from Tribler.dispersy.dprint import dprint

DEBUG = False
DEBUG_VERBOSE = False
TTL = 4
NEIGHBORS = 5
FNEIGHBORS = 1
ENCRYPTION = True
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
    def load_community(cls, master, my_member, integrate_with_tribler=True, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, encryption=ENCRYPTION, max_prefs=None, log_searches=False, use_megacache=True):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, encryption=encryption, max_prefs=max_prefs, log_searches=log_searches, use_megacache=use_megacache)
        else:
            return super(SearchCommunity, cls).load_community(master, integrate_with_tribler=integrate_with_tribler, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, encryption=encryption, max_prefs=max_prefs, log_searches=log_searches, use_megacache=use_megacache)

    def __init__(self, master, integrate_with_tribler=True, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, encryption=ENCRYPTION, max_prefs=None, log_searches=False, use_megacache=True):
        super(SearchCommunity, self).__init__(master)

        self.integrate_with_tribler = bool(integrate_with_tribler)

        self.ttl = ttl
        self.neighbors = int(neighbors)
        self.fneighbors = int(fneighbors)
        self.encryption = bool(encryption)
        self.log_searches = bool(log_searches)
        self.use_megacache = bool(use_megacache)

        self.taste_buddies = []
        self.my_preference_cache = [None, None]

        # To always perform searches using a peer uncomment/modify the following line
        # self.taste_buddies.append([1, time(), Candidate(("127.0.0.1", 1234), False))
        self.key = rsa_init()

        if not max_prefs:
            max_len = self.dispersy_sync_bloom_filter_bits
            max_prefs = max_len / self.key.size
            max_hprefs = max_len / 20
        else:
            max_hprefs = max_prefs

        self.max_prefs = max_prefs
        self.max_h_prefs = max_hprefs

        self.search_timeout = 0
        self.search_forward = 0
        self.search_forward_success = 0
        self.search_forward_timeout = 0
        self.search_endpoint = 0
        self.search_cycle_detected = 0
        self.search_megacachesize = 0
        self.search_no_candidates_remain = 0

        self.create_time_encryption = 0.0
        self.create_time_decryption = 0.0
        self.receive_time_encryption = 0.0

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
            candidates = [candidate for candidate in self._iter_categories([u'walk', u'stumble', u'intro'], once=True) if candidate]
            for candidate in candidates:
                if __debug__: dprint("extra walk to ", candidate)
                self.create_introduction_request(candidate, allow_sync=False)

            # wait for NAT hole punching
            yield 1.0

        if __debug__: dprint("finished")

    def initiate_meta_messages(self):
        return [Message(self, u"search-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SearchRequestPayload(), self._dispersy._generic_timeline_check, self.on_search),
                Message(self, u"search-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SearchResponsePayload(), self.check_search_response, self.on_search_response),
                Message(self, u"torrent-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), TorrentRequestPayload(), self._dispersy._generic_timeline_check, self.on_torrent_request),
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=0), TorrentPayload(), self._dispersy._generic_timeline_check, self.on_torrent),
                Message(self, u"ping", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PingPayload(), self._dispersy._generic_timeline_check, self.on_ping),
                Message(self, u"pong", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PongPayload(), self.check_pong, self.on_pong),
                Message(self, u"encrypted-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedResponsePayload(), self._dispersy._generic_timeline_check, self.on_encr_response),
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
#    def dispersy_yield_introduce_candidates(self, candidate = None):
#        for random_candidate in Community.dispersy_yield_introduce_candidates(self, candidate):
#            if not self.is_taste_buddy(random_candidate):
#                yield random_candidate

    # used by dispersy to choose a peer to connect to
#    def dispersy_yield_walk_candidates(self):
#        for candidate in Community.dispersy_yield_walk_candidates(self):
#            yield candidate

    def add_taste_buddies(self, new_taste_buddies):
        for new_tb_tuple in new_taste_buddies[:]:
            for tb_tuple in self.taste_buddies:
                if tb_tuple[-1].sock_addr == new_tb_tuple[-1].sock_addr:

                    # update similarity
                    tb_tuple[0] = max(new_tb_tuple[0], tb_tuple[0])
                    new_taste_buddies.remove(new_tb_tuple)
                    break

            # new peer
            else:
                if len(self.taste_buddies) < 10 or new_tb_tuple[0] > self.taste_buddies[-1][0]:
                    self.taste_buddies.append(new_tb_tuple)
                    self.dispersy.callback.register(self.create_ping_request, args=(new_tb_tuple[-1],), delay=PING_INTERVAL)

        # self._create_pingpong("ping", [tb_tuple[-1] for tb_tuple in new_taste_buddies])

        self.taste_buddies.sort(reverse=True)
        self.taste_buddies = self.taste_buddies[:10]

        if DEBUG:
            print >> sys.stderr, long(time()), "SearchCommunity: current tastebuddy list", len(self.taste_buddies), self.taste_buddies

    def yield_taste_buddies(self, ignore_candidate=None):
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
            # TODO: change this for deployment
            if tb.sock_addr[1] == sock_addr[1]:
                return True

    def is_taste_buddy_mid(self, mid):
        for tb in self.yield_taste_buddies():
            if mid in [member.mid for member in tb.get_members(self)]:
                return True

    def create_introduction_request(self, destination, allow_sync):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        self._dispersy.statistics.walk_attempt += 1
        destination.walk(self, time(), IntroductionRequestCache.timeout_delay)
        identifier = self._dispersy.request_cache.claim(IntroductionRequestCache(self, destination))

        advice = True
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash() if preference]
        if not isinstance(destination, BootstrapCandidate) and not self.is_taste_buddy(destination) and len(myPreferences):
            str_myPreferences = str(myPreferences)
            if self.my_preference_cache[0] == str_myPreferences:
                myPreferences = self.my_preference_cache[1]
            else:
                if len(myPreferences) > self.max_prefs:
                    myPreferences = sample(myPreferences, self.max_prefs)
                shuffle(myPreferences)

                myPreferences = [bytes_to_long(infohash) for infohash in myPreferences]
                if self.encryption:
                    t1 = time()
                    myPreferences = [rsa_encrypt(self.key, infohash) for infohash in myPreferences]
                    self.create_time_encryption += time() - t1

                self.my_vector_cache = [str_myPreferences, myPreferences]

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "SearchCommunity: sending introduction request to", destination, "containing", len(myPreferences), "hashes", self._mypref_db.getMyPrefListInfohash()

            payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, myPreferences, self.key.n)

        else:
            if DEBUG_VERBOSE:
                reason = ''
                if isinstance(destination, BootstrapCandidate):
                    reason = 'being bootstrapserver'
                elif self.is_taste_buddy(destination):
                    reason = 'is taste buddy'
                else:
                    reason = 'having no preferences'
                print >> sys.stderr, long(time()), "SearchCommunity: sending empty-introduction request to", destination, "due to", reason

            payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, None)

        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=payload)

        self._dispersy._forward([request])
        return request

    def on_intro_request(self, orig_messages):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "SearchCommunity: got %d introduction requests" % len(orig_messages)

        messages = [message for message in orig_messages if not isinstance(self._dispersy.get_candidate(message.candidate.sock_addr), BootstrapCandidate) and message.payload.preference_list]
        self.process_rsa_simirequest(messages)

        self._disp_intro_handler(orig_messages)
        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in orig_messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d" % message.candidate.sock_addr)

    def process_rsa_simirequest(self, messages, send_messages=True):
        # 1. fetch my preferences
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash(local=False) if preference]
        myListLen = len(myPreferences)

        # 2. use subset if we have to many preferences
        if myListLen > self.max_h_prefs:
            myPreferences = sample(myPreferences, self.max_h_prefs)

        if self.encryption:
            myPreferences = [bytes_to_long(preference) for preference in myPreferences]

        for message in messages:
            if self.encryption:
                t1 = time()

                # 3. construct a rsa key to encrypt my preferences
                his_n = message.payload.key_n
                fake_phi = his_n / 2
                compatible_key = rsa_compatible(his_n, fake_phi)

                # 4. encrypt hislist and mylist + hash mylist
                hisList = [rsa_encrypt(compatible_key, infohash) for infohash in message.payload.preference_list]
                myList = [hash_element(rsa_encrypt(compatible_key, infohash)) for infohash in myPreferences]

                self.receive_time_encryption += time() - t1
            else:
                hisList = message.payload.preference_list
                myList = myPreferences

            shuffle(hisList)
            shuffle(myList)
            if send_messages:
                # 5. create a messages, containing hislist encrypted with my compatible key and mylist only encrypted by the compatible key + hashed
                meta = self.get_meta_message(u"encrypted-response")
                resp_message = meta.impl(authentication=(self._my_member,),
                                    distribution=(self.global_time,),
                                    destination=(message.candidate,),
                                    payload=(message.payload.identifier, hisList, myList))

                self._dispersy._forward([resp_message])

                if DEBUG_VERBOSE:
                    print >> sys.stderr, long(time()), "SearchCommunity: sending encrypted-response to", message.payload.identifier, message.candidate
            else:
                return hisList, myList

    def on_encr_response(self, messages):
        # TODO: we should check if this is our request, ie use the requestcache however the requestcache is completely broken...
        for message in messages:
            overlap = self.compute_rsa_overlap(message.payload.preference_list, message.payload.his_preference_list)

#            for now only use overlap
#            myRoot = 1.0/(myPrefs ** .5)
#            sim = overlap * (myRoot * (1.0/(hisPrefs ** .5)))
#
#            if hisPrefs < 40:
#                sim = (hisPrefs/40.0) * sim

            self.add_taste_buddies([[overlap, time(), message.candidate]])

    def compute_rsa_overlap(self, preference_list, his_preference_list):
        if self.encryption:
            t1 = time()
            myList = [hash_element(rsa_decrypt(self.key, infohash)) for infohash in preference_list]

            self.create_time_decryption += time() - t1
        else:
            myList = [long_to_bytes(infohash) for infohash in preference_list]

        assert all(len(infohash) == 20 for infohash in myList)

        overlap = 0
        for pref in myList:
            if pref in his_preference_list:
                overlap += 1
        return overlap

    class SearchRequest(Cache):
        timeout_delay = 30.0
        cleanup_delay = 0.0

        def __init__(self, community, keywords, ttl, callback, results=[], return_candidate=None, requested_candidates=[]):
            self.community = community
            self.keywords = keywords
            self.callback = callback
            self.results = results
            self.return_candidate = return_candidate

            self.requested_candidates = requested_candidates
            self.requested_mids = set()
            for candidate in self.requested_candidates:
                for member in candidate.get_members(community):
                    self.requested_mids.add(member.mid)
            self.received_candidates = []

            # setting timeout
            if self.return_candidate:
                self.timeout_delay = 5.0

            self.timeout_delay += (ttl * 2)
            self.processed = False

        def did_request(self, candidate_mid):
            return candidate_mid in self.requested_mids

        def on_success(self, candidate_mid, keywords, results, candidate):
            if not self.processed:
                if self.did_request(candidate_mid):
                    self.received_candidates.append(candidate_mid)
                    self.results.extend(results)
                    shuffle(self.results)

                self.processed = len(self.received_candidates) == len(self.requested_candidates)
                if self.return_candidate and self.processed:
                    self.callback(keywords, self.results, self.return_candidate)  # send message containing all results
                    self.community.search_forward_success += 1

                if not self.return_candidate:
                    self.callback(keywords, results, candidate)  # local query, update immediately do not pass self.results as it contains all results

            return self.processed

        def on_timeout(self):
            # timeout, message was probably lost return our local results
            if not self.processed:
                self.processed = True
                if self.return_candidate:
                    self.callback(self.keywords, self.results, self.return_candidate)
                    self.community.search_forward_timeout += 1

                    if DEBUG:
                        print >> sys.stderr, long(time()), "SearchCommunity: timeout for searchrequest, returning my local results waited for %.1f seconds" % self.timeout_delay
                else:
                    self.community.search_timeout += (len(self.requested_candidates) - len(self.received_candidates))

    class MSearchRequest(SearchRequest):

        def __init__(self, search_request):
            self.timeout_delay = search_request.timeout_delay
            self.cleanup_delay = search_request.cleanup_delay

            self.search_requests = []
            self.search_requests.append(search_request)

        def add_request(self, search_request):
            if __debug__:
                requested_candidates = self.get_requested_candidates()
                assert all(mid not in requested_candidates for mid in search_request.requested_mids), "requested candidates cannot overlap"
                assert search_request.identifier == self.identifier
                assert search_request.keywords == self.keywords

            self.search_requests.append(search_request)

        def get_requested_candidates(self):
            requested_candidates = set()
            for search_request in self.search_requests:
                requested_candidates.update(search_request.requested_mids)
            return requested_candidates

        def on_success(self, candidate_mid, keywords, results, candidate):
            for i in range(len(self.search_requests) - 1, -1, -1):
                search_request = self.search_requests[i]
                if search_request.did_request(candidate_mid):
                    if search_request.on_success(candidate_mid, keywords, results, candidate):
                        self.search_requests.pop(i)
                    break

            return len(self.search_requests) == 0

        def on_timeout(self):
            for search_request in self.search_requests:
                search_request.on_timeout()

        @property
        def keywords(self):
            return self.search_requests[0].keywords

    def create_search(self, keywords, callback, identifier=None, ttl=None, nrcandidates=None, bloomfilter=None, results=None, return_candidate=None):
        if identifier == None:
            identifier = self._dispersy.request_cache.generate_identifier()
            if self.log_searches:
                log("dispersy.log", "search-statistics", identifier=identifier, keywords=keywords, created_by_me=True)

        if nrcandidates == None:
            nrcandidates = self.neighbors

        if bloomfilter == None:
            bloomfilter = BloomFilter(0.01, 100)

        # put local results in bloomfilter
        if results == None:
            results = self._get_results(keywords, bloomfilter, True)

        # fetch requested candidates from previous forward
        prev_request = self._dispersy.request_cache.get(identifier, SearchCommunity.MSearchRequest)
        if prev_request:
            ignore_candidates = prev_request.get_requested_candidates()
        else:
            ignore_candidates = set()

        if return_candidate:
            for member in return_candidate.get_members(self):
                ignore_candidates.add(member.mid)

        # impose upper limit for forwarding
        candidates = []

        if len(ignore_candidates) < self.neighbors:
            random_peers, taste_buddies = self.get_randompeers_tastebuddies(ignore_candidates)
            shuffle(taste_buddies)
            shuffle(random_peers)

            for _ in xrange(nrcandidates):
                if ttl == None:
                    if isinstance(self.ttl, tuple):
                        _ttl = randint(self.ttl[0], self.ttl[1])
                    elif isinstance(self.ttl, int):
                        _ttl = self.ttl
                    else:
                        _ttl = 1
                else:
                    _ttl = ttl

                # prefer taste buddies, fallback to random peers
                if taste_buddies:
                    candidate = taste_buddies.pop()
                elif random_peers:
                    candidate = random_peers.pop()
                else:
                    break

                # create request message
                meta = self.get_meta_message(u"search-request")
                message = meta.impl(authentication=(self._my_member,),
                                    distribution=(self.global_time,), payload=(identifier, _ttl, keywords, bloomfilter))
                self._dispersy._send([candidate], [message])
                candidates.append(candidate)

        if candidates:
            this_request = SearchCommunity.SearchRequest(self, keywords, ttl or 7, callback, results, return_candidate, requested_candidates=candidates)
            this_request.identifier = identifier

            if prev_request:
                assert prev_request.keywords == keywords
                prev_request.add_request(this_request)
            else:
                self._dispersy.request_cache.set(identifier, SearchCommunity.MSearchRequest(this_request))

            if DEBUG:
                print >> sys.stderr, long(time()), "SearchCommunity: sending search request for", keywords, "to", map(str, candidates)
        else:
            self.search_no_candidates_remain += 1

        return candidates, results, identifier

    def on_search(self, messages):
        for message in messages:
            if self.log_searches:
                log("dispersy.log", "search-statistics", identifier=message.payload.identifier, cycle=self._dispersy.request_cache.has(message.payload.identifier, SearchCommunity.SearchRequest))

            identifier = message.payload.identifier
            keywords = message.payload.keywords
            bloomfilter = message.payload.bloom_filter

            if DEBUG:
                print >> sys.stderr, long(time()), "SearchCommunity: got search request for", keywords

            # compute new ttl
            if isinstance(self.ttl, int):
                ttl = message.payload.ttl - 1

            elif isinstance(self.ttl, tuple):
                ttl = message.payload.ttl
                if ttl > 1:
                    ttl -= 1
                else:
                    ttl = 0 if random() < 0.5 else 1
            else:
                ttl = 7 if random() < self.ttl else 0

            forward_message = ttl > 0

            # detect cycle
            results = []
            if not self._dispersy.request_cache.has(identifier, SearchCommunity.MSearchRequest):
                results = self._get_results(keywords, bloomfilter, False)
                if not results and DEBUG:
                    print >> sys.stderr, long(time()), "SearchCommunity: no results"
            else:
                self.search_cycle_detected += 1

                cache = self._dispersy.request_cache.get(identifier, SearchCommunity.MSearchRequest)
                if cache.keywords != keywords:  # abort, return
                    forward_message = False

            if forward_message:
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchCommunity: ttl == %d forwarding" % ttl

                callback = lambda keywords, newresults, candidate, myidentifier = identifier: self._create_search_response(myidentifier, newresults, candidate)
                candidates, _, _ = self.create_search(keywords, callback, identifier, ttl, self.fneighbors, bloomfilter, results, message.candidate)

                if len(candidates):
                    self.search_forward += 1
                else:
                    forward_message = False

            if not forward_message:
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchCommunity: returning"
                self._create_search_response(identifier, results, message.candidate)
                self.search_endpoint += 1

    def _get_results(self, keywords, bloomfilter, local):
        results = []
        dbresults = self._torrent_db.searchNames(keywords, local=local, keys=['infohash', 'T.name', 'T.length', 'T.num_files', 'T.category_id', 'T.creation_date', 'T.num_seeders', 'T.num_leechers', 'swift_hash', 'swift_torrent_hash'])
        if len(dbresults) > 0:
            for dbresult in dbresults:
                if not (bloomfilter and dbresult[0] in bloomfilter):
                    channel_details = dbresult[-10:]

                    dbresult = list(dbresult[:10])
                    dbresult[1] = unicode(dbresult[1])
                    dbresult[2] = long(dbresult[2])
                    dbresult[3] = int(dbresult[3])
                    dbresult[4] = [self._torrent_db.id2category[dbresult[4]], ]
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
        # create search-response message
        meta = self.get_meta_message(u"search-response")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(identifier, results))
        self._dispersy._send([candidate], [message])

        if DEBUG:
            print >> sys.stderr, long(time()), "SearchCommunity: returning", len(results), "results to", candidate

    def check_search_response(self, messages):
        for message in messages:
            accepted, _ = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            if not self._dispersy.request_cache.has(message.payload.identifier, SearchCommunity.MSearchRequest):
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchCommunity: got search response identifier not found", message.payload.identifier

                yield DropMessage(message, "invalid response identifier")
                continue

            yield message

    def on_search_response(self, messages):
        for message in messages:
            # fetch callback using identifier
            search_request = self._dispersy.request_cache.get(message.payload.identifier, SearchCommunity.MSearchRequest)
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchCommunity: got search response for", search_request.keywords, len(message.payload.results), message.candidate

            if len(message.payload.results) > 0 and self.use_megacache:
                self.search_megacachesize = self._torrent_db.on_search_response(message.payload.results)

            removeCache = search_request.on_success(message.authentication.member.mid, search_request.keywords, message.payload.results, message.candidate)
            if removeCache:
                self._dispersy.request_cache.pop(message.payload.identifier, SearchCommunity.SearchRequest)

            # see if we need to join some channels
            channels = set([result[10] for result in message.payload.results if result[10]])
            if channels:
                channels = self._get_unknown_channels(channels)

                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchCommunity: joining %d preview communities" % len(channels)

                for cid in channels:
                    community = self._get_channel_community(cid)
                    community.disp_create_missing_channel(message.candidate, includeSnapshot=False)

    class PingRequestCache(IntroductionRequestCache):
        cleanup_delay = 0.0

        def __init__(self, community, candidate):
            IntroductionRequestCache.__init__(self, community, None)
            self.candidate = candidate
            self.processed = False

        def on_success(self):
            self.processed = True

        def on_timeout(self):
            if not self.processed:
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchCommunity: no response on ping, removing from taste_buddies", self.candidate
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
            # TODO: change for deployment
            if taste_buddy[2].sock_addr[1] == candidate.sock_addr[1]:
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
            if len(message.payload.torrents) > 0:
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

            if len(message.payload.torrents) > 0:
                self.search_megacachesize = self._torrent_db.on_pingpong(message.payload.torrents)

            self.resetTastebuddy(message.candidate)

    def _create_pingpong(self, meta_name, candidates, identifiers=None):
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

            # create torrent-collect-request/response message
            meta = self.get_meta_message(meta_name)
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(identifier, torrents))
            self._dispersy._send([candidate], [message])

            if DEBUG:
                print >> sys.stderr, long(time()), "SearchCommunity: send", meta_name, "to", candidate

    def create_torrent_request(self, torrents, candidate):
        torrentdict = {}
        for torrent in torrents:
            if isinstance(torrent, list):
                cid, infohash = torrent
            else:
                cid = self._master_member.mid
                infohash = torrent
            torrentdict.setdefault(cid, set()).add(infohash)

        # create torrent-request message
        meta = self.get_meta_message(u"torrent-request")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(torrentdict,))
        self._dispersy._send([candidate], [message])

        if DEBUG:
            nr_requests = sum([len(cid_torrents) for cid_torrents in torrentdict.values()])
            print >> sys.stderr, long(time()), long(time()), "SearchCommunity: requesting", nr_requests, "TorrentMessages from", candidate

    def on_torrent_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                requested_packets.extend(self._get_packets_from_infohashes(cid, torrents))

            if requested_packets:
                self._dispersy.statistics.dict_inc(self._dispersy.statistics.outgoing, u"torrent-response", len(requested_packets))
                self._dispersy.endpoint.send([message.candidate], requested_packets)

            if DEBUG:
                print >> sys.stderr, long(time()), long(time()), "SearchCommunity: got request for ", len(requested_packets), "torrents from", message.candidate

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
        known_cids = self._channelcast_db._db.fetchall(u"SELECT dispersy_cid FROM Channels WHERE dispersy_cid in (" + parameters + ")", map(buffer, cids))
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

            # 1. try to find the torrentmessage for this cid, infohash combination
            if channel_id:
                dispersy_id = self._channelcast_db.getTorrentFromChannelId(channel_id, infohash, ['ChannelTorrents.dispersy_id'])
            else:
                torrent = self._torrent_db.getTorrent(infohash, ['dispersy_id', 'torrent_file_name'], include_mypref=False)
                if torrent:
                    dispersy_id = torrent['dispersy_id']

                    # 2. if still not found, create a new torrentmessage and return this one
                    if not dispersy_id and torrent['torrent_file_name'] and path.isfile(torrent['torrent_file_name']):
                        message = self.create_torrent(torrent['torrent_file_name'], store=True, update=False, forward=False)
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

    def get_connections(self, nr=10, ignore_candidate=None):
        # use taste buddies and fill with random candidates
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

    def get_randompeers_tastebuddies(self, ignore_candidates=set()):
        taste_buddies = list(self.yield_taste_buddies())

        random_peers = []
        sock_addresses = set(candidate.sock_addr for candidate in taste_buddies)
        for candidate in self.dispersy_yield_candidates():
            if candidate.sock_addr not in sock_addresses:
                random_peers.append(candidate)
                sock_addresses.add(candidate.sock_addr)

        if ignore_candidates:
            _random_peers = []
            _taste_buddies = []
            for candidate in random_peers:
                add = True
                for member in candidate.get_members(self):
                    if member.mid in ignore_candidates:
                        add = False
                        break

                if add:
                    _random_peers.append(candidate)

            for candidate in taste_buddies:
                add = True
                for member in candidate.get_members(self):
                    if member.mid in ignore_candidates:
                        add = False
                        break

                if add:
                    _taste_buddies.append(candidate)

            return _random_peers, _taste_buddies
        return random_peers, taste_buddies

class ForwardCommunity(SearchCommunity):

    def __init__(self, master, integrate_with_tribler=True, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, encryption=ENCRYPTION, max_prefs=None, log_searches=False, use_megacache=True):
        SearchCommunity.__init__(self, master, integrate_with_tribler, ttl, neighbors, fneighbors, encryption, max_prefs, log_searches, use_megacache)

        self.possible_taste_buddies = []
        self.requested_introductions = {}

    def _initialize_meta_messages(self):
        Community._initialize_meta_messages(self)

        ori = self._meta_messages[u"dispersy-introduction-request"]
        self._disp_intro_handler = ori.handle_callback

        new = Message(self, ori.name, ori.authentication, ori.resolution, ori.distribution, ori.destination, ExtendedIntroPayload(), ori.check_callback, self.on_intro_request)
        self._meta_messages[u"dispersy-introduction-request"] = new

    def add_possible_taste_buddies(self, possibles):
        if __debug__:
            for possible in possibles:
                assert isinstance(possible[0], (float, int, long)), type(possible[0])
                assert isinstance(possible[1], (float, long)), type(possible[1])
                assert isinstance(possible[2], str), type(possible[2])
                assert isinstance(possible[3], Candidate), type(possible[3])

        low_sim = self.get_low_sim()
        for new_pos_tuple in possibles:
            if new_pos_tuple[0] <= low_sim:
                continue

            for i, pos_tuple in enumerate(self.possible_taste_buddies):
                if new_pos_tuple[2] == pos_tuple[2]:
                    # max similarity
                    new_pos_tuple[0] = max(pos_tuple[0], new_pos_tuple[0])
                    # replace in list
                    self.possible_taste_buddies[i] = new_pos_tuple
                    break

            # new peer
            else:
                self.possible_taste_buddies.append(new_pos_tuple)

        self.possible_taste_buddies.sort(reverse=True)

        if DEBUG and possibles:
            print >> sys.stderr, long(time()), "ForwardCommunity: got possible taste buddies, current list", len(self.possible_taste_buddies), [possible[0] for possible in self.possible_taste_buddies]

    def has_possible_taste_buddies(self, candidate):
        for _, _, _, from_candidate in self.possible_taste_buddies:
            if from_candidate.sock_addr == candidate.sock_addr:
                return True
        return False

    def get_low_sim(self):
        if len(self.taste_buddies) == 10:
            return self.taste_buddies[-1][0]
        return 0

    def get_most_similar(self, candidate):
        # clean possible taste buddies, remove all entries older than 60s
        to_be_removed = time() - 60
        low_sim = self.get_low_sim()

        for i in range(len(self.possible_taste_buddies) - 1, -1, -1):
            to_low_sim = self.possible_taste_buddies[i][0] <= low_sim
            to_old = self.possible_taste_buddies[i][1] < to_be_removed
            is_tb = self.is_taste_buddy_mid(self.possible_taste_buddies[i][2])
            if to_low_sim or to_old or is_tb:
                if DEBUG:
                    print >> sys.stderr, long(time()), long(time()), "ForwardCommunity: removing possible tastebuddy", long(time()), to_low_sim, to_old, is_tb, self.possible_taste_buddies[i]
                self.possible_taste_buddies.pop(i)

        if self.possible_taste_buddies:
            most_similar = self.possible_taste_buddies.pop(0)
            return most_similar[3], most_similar[2]

        return candidate, None

    def dispersy_yield_introduce_candidates(self, candidate=None):
        if candidate:
            if candidate in self.requested_introductions:
                intro_me_candidate = self.requested_introductions[candidate]
                del self.requested_introductions[candidate]
                yield intro_me_candidate

        for random_candidate in SearchCommunity.dispersy_yield_introduce_candidates(self, candidate):
            yield random_candidate

    class ForwardAttempt(Cache):
        timeout_delay = 10.5
        cleanup_delay = 0.0

        def __init__(self, community, requested_candidate):
            self.community = community
            self.requested_candidate = requested_candidate

        def on_timeout(self):
            self.community.send_introduction_request(self.requested_candidate)

    def create_introduction_request(self, destination, allow_sync):
        send = False
        if not isinstance(destination, BootstrapCandidate) and not self.is_taste_buddy(destination) and not self.has_possible_taste_buddies(destination) and allow_sync:
            identifier = self._dispersy.request_cache.claim(ForwardCommunity.ForwardAttempt(self, destination))
            send = self.send_similarity_request(destination, identifier)

            if not send:
                self._dispersy.request_cache.pop(identifier, ForwardCommunity.ForwardAttempt)

        if not send:
            self.send_introduction_request(destination)

    def send_introduction_request(self, destination, introduce_me_to=None):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]
        assert not introduce_me_to or isinstance(introduce_me_to, str), type(introduce_me_to)

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
                self.requested_introductions[candidate] = introduce_me_to = self.get_candidate_mid(message.payload.introduce_me_to)

                if not introduce_me_to and DEBUG:
                    print >> sys.stderr, long(time()), long(time()), "Cannot create candidate for mid", message.payload.introduce_me_to

        self._disp_intro_handler(messages)

        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d" % message.candidate.sock_addr)

class PSearchCommunity(ForwardCommunity):

    def __init__(self, master, integrate_with_tribler=True, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, encryption=ENCRYPTION, max_prefs=None, log_searches=False, use_megacache=True):
        ForwardCommunity.__init__(self, master, integrate_with_tribler, ttl, neighbors, fneighbors, encryption, max_prefs, log_searches, use_megacache)

        self.key = pallier_init(self.key)
        self.my_vector_cache = [None, None]

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"sum-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self._dispersy._generic_timeline_check, self.on_sum_request))
        messages.append(Message(self, u"sums-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self._dispersy._generic_timeline_check, self.on_sums_request))
        messages.append(Message(self, u"global-vector", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), GlobalVectorPayload(), self._dispersy._generic_timeline_check, self.on_global_vector))
        messages.append(Message(self, u"encrypted-sum", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumPayload(), self.check_encr_sum, self.on_encr_sum))
        messages.append(Message(self, u"encrypted-sums", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumsPayload(), self._dispersy._generic_timeline_check, self.on_encr_sums))
        return messages

    def initiate_conversions(self):
        return [DefaultConversion(self), PSearchConversion(self)]

    def send_similarity_request(self, destination, identifier):
        global_vector_request, global_vector = self.create_global_vector(destination, identifier)

        str_global_vector = str(global_vector)
        if self.my_vector_cache[0] == str_global_vector:
            encrypted_vector = self.my_vector_cache[1]
        else:
            my_vector = self.get_my_vector(global_vector, local=True)
            if self.encryption:

                t1 = time()
                encrypted_vector = []
                for element in my_vector:
                    cipher = pallier_encrypt(self.key, element)
                    encrypted_vector.append(cipher)

                self.create_time_encryption += time() - t1
            else:
                encrypted_vector = my_vector

            self.my_vector_cache = [str_global_vector, encrypted_vector]

        meta_request = self.get_meta_message(u"sums-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, self.key.n, encrypted_vector))

        self._dispersy._forward([request])
        self._dispersy._forward([global_vector_request])
        return True

    def on_sums_request(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), long(time()), "PSearchCommunity: got sums request"

            # get candidates to forward requests to, excluding the requesting peer
            candidates = self.get_connections(10, message.candidate)

            # create RPSimilarityRequest to use as object to collect all sums
            if self._dispersy.request_cache.has(message.payload.identifier, PSearchCommunity.PSimilarityRequest):
                prev_request = self._dispersy.request_cache.get(message.payload.identifier, PSearchCommunity.PSimilarityRequest)

                request = PSearchCommunity.RPSimilarityRequest(self, message.candidate, candidates)
                request.global_vector = prev_request.global_vector
                self._dispersy.request_cache.replace(message.payload.identifier, request)
            else:
                self._dispersy.request_cache.set(message.payload.identifier, PSearchCommunity.RPSimilarityRequest(self, message.candidate, candidates))

            # process this request as a normal sum request
            self.on_sum_request([message])

            # forward it to others
            meta_request = self.get_meta_message(u"sum-request")
            request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                payload=(message.payload.identifier, long(message.payload.key_n), message.payload.preference_list))

            self._dispersy._send(candidates, [request])

    def on_sum_request(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PSearchCommunity: got sum request"

            # create a PSimilarityRequest to store this request for sum
            if not self._dispersy.request_cache.has(message.payload.identifier, PSearchCommunity.PSimilarityRequest):
                self._dispersy.request_cache.set(message.payload.identifier, PSearchCommunity.PSimilarityRequest(self, message.candidate))

            # fetch request object, and store user_n and user_vector
            request = self._dispersy.request_cache.get(message.payload.identifier, PSearchCommunity.PSimilarityRequest)
            request.user_n = message.payload.key_n
            request.user_vector = message.payload.preference_list

            # if request is complete, process it
            if request.is_complete():
                request.process()

    def create_global_vector(self, destination, identifier):
        # 1. fetch my preferences
        global_vector = [long(preference) for preference in self._mypref_db.getMyPrefListInfohash(local=True) if preference]

        # 2. reduce/extend the vector in size
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

    def on_global_vector(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PSearchCommunity: got global vector"

            if not self._dispersy.request_cache.has(message.payload.identifier, PSearchCommunity.PSimilarityRequest):
                self._dispersy.request_cache.set(message.payload.identifier, PSearchCommunity.PSimilarityRequest(self, message.candidate))

            request = self._dispersy.request_cache.get(message.payload.identifier, PSearchCommunity.PSimilarityRequest)
            request.global_vector = message.payload.preference_list

            if isinstance(request, PSearchCommunity.RPSimilarityRequest):
                if request.requested_candidates:
                    if DEBUG_VERBOSE:
                        print >> sys.stderr, long(time()), "PSearchCommunity: forwarding global vector", request.requested_candidates
                    self._dispersy._send(request.requested_candidates, [message])

            if request.is_complete():
                request.process()

    def get_my_vector(self, global_vector, local=False):
        my_preferences = set([long(preference) for preference in self._mypref_db.getMyPrefListInfohash(local=local) if preference])
        my_vector = [0l] * len(global_vector)
        for i, element in enumerate(global_vector):
            if element in my_preferences:
                my_vector[i] = 1l
        return my_vector

    class PSimilarityRequest(Cache):
        timeout_delay = 3.5
        cleanup_delay = 0.0

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
                    print >> sys.stderr, long(time()), "PSearchCommunity: calculated sum", _sum

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
                    print >> sys.stderr, long(time()), "PSearchCommunity: processed PSimilarityRequest"

                self.community._dispersy.request_cache.pop(self.identifier, PSearchCommunity.PSimilarityRequest)

        def on_timeout(self):
            if DEBUG:
                print >> sys.stderr, long(time()), "PSearchCommunity: timeout PSimilarityRequest", self.global_vector != None, self.user_vector != None

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
                print >> sys.stderr, long(time()), "PSearchCommunity: got sum in RPSimilarityRequest"

            if candidate_mid in self.requested_mids:
                if DEBUG_VERBOSE:
                    print >> sys.stderr, long(time()), "PSearchCommunity: added sum in RPSimilarityRequest"

                self.received_candidates.append(candidate_mid)
                self.received_sums.append((candidate_mid, _sum))

        def is_complete(self):
            return PSearchCommunity.PSimilarityRequest.is_complete(self) and len(self.received_sums) == len(self.requested_candidates)

        def process(self):
            if not self.isProcessed:
                _sum = self.get_sum()

                # TODO: instead of sock_addr, we should reply with the identifier of a peer
                meta_request = self.community.get_meta_message(u"encrypted-sums")
                response = meta_request.impl(authentication=(self.community.my_member,),
                                        distribution=(self.community.global_time,),
                                        destination=(self.requesting_candidate,),
                                        payload=(self.identifier, _sum, self.received_sums))

                self.community._dispersy._forward([response])
                self.isProcessed = True

                if DEBUG_VERBOSE:
                    print >> sys.stderr, long(time()), "PSearchCommunity: processed RPSimilarityRequest"

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
                print >> sys.stderr, long(time()), "PSearchCommunity: received sum", message.payload._sum

            request = self._dispersy.request_cache.get(message.payload.identifier, PSearchCommunity.RPSimilarityRequest)
            request.add_sum(message.authentication.member.mid, message.payload._sum)

            if request.is_complete():
                request.process()

    def on_encr_sums(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PSearchCommunity: received sums", message.payload._sum

            if self.encryption:
                t1 = time()

                _sums = [[pallier_decrypt(self.key, _sum), time(), candidate_mid, message.candidate] for candidate_mid, _sum in message.payload.sums]
                _sum = pallier_decrypt(self.key, message.payload._sum)

                self.create_time_decryption += time() - t1
            else:
                _sums = [[_sum, time(), candidate_mid, message.candidate] for candidate_mid, _sum in message.payload.sums]
                _sum = message.payload._sum

            self.add_taste_buddies([[_sum, time(), message.candidate]])

            _sums = [possible for possible in _sums if possible[0]]
            if _sums:
                self.add_possible_taste_buddies(_sums)

            request = self._dispersy.request_cache.pop(message.payload.identifier, ForwardCommunity.ForwardAttempt)
            if request:
                destination, introduce_me_to = self.get_most_similar(message.candidate)
                self.send_introduction_request(destination, introduce_me_to)

                if DEBUG and introduce_me_to:
                    print >> sys.stderr, long(time()), "PSearchCommunity: asking candidate %s to introduce me to %s after receiving sums from %s" % (destination, introduce_me_to.encode("HEX"), message.candidate)

class HSearchCommunity(ForwardCommunity):

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"similarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SimilarityRequest(), self._dispersy._generic_timeline_check, self.process_rsa_simirequest))
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SimilarityRequest(), self.check_msimi_request, self.on_msimi_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), BundledEncryptedResponsePayload(), self._dispersy._generic_timeline_check, self.on_msimi_response))
        return messages

    def initiate_conversions(self):
        return [DefaultConversion(self), HSearchConversion(self)]

    def send_similarity_request(self, destination, identifier):
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash() if preference]
        str_myPreferences = str(myPreferences)

        if self.my_preference_cache[0] == str_myPreferences:
            myPreferences = self.my_preference_cache[1]
        else:
            if len(myPreferences) > self.max_prefs:
                myPreferences = sample(myPreferences, self.max_prefs)
            shuffle(myPreferences)

            myPreferences = [bytes_to_long(infohash) for infohash in myPreferences]
            if self.encryption:
                t1 = time()
                myPreferences = [rsa_encrypt(self.key, infohash) for infohash in myPreferences]
                self.create_time_encryption += time() - t1

            self.my_vector_cache = [str_myPreferences, myPreferences]

        if myPreferences:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "HSearchCommunity: sending similarity request to", destination, "containing", len(myPreferences), "hashes"

            meta_request = self.get_meta_message(u"msimilarity-request")
            request = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    destination=(destination,),
                                    payload=(identifier, long(self.key.n), myPreferences))

            self._dispersy._forward([request])
            return True

        return False

    def check_msimi_request(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            if self._dispersy.request_cache.has(message.payload.identifier, HSearchCommunity.MSimilarityRequest):
                yield DropMessage(message, "invalid response identifier")
                continue

            yield message

    def on_msimi_request(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "HSearchCommunity: got msimi request from", message.candidate

            # get candidates to forward requests to, excluding the requesting peer
            candidates = self.get_connections(10, message.candidate)

            request_cache = HSearchCommunity.MSimilarityRequest(self, message, candidates)
            if candidates:
                # create MSimilarityRequest to use as object to collect all sums
                self._dispersy.request_cache.set(message.payload.identifier, request_cache)

                # forward it to others
                meta_request = self.get_meta_message(u"similarity-request")
                request = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    payload=(message.payload.identifier, message.payload.key_n, message.payload.preference_list[:20]))

                self._dispersy._send(candidates, [request])

            else:
                request_cache.identifier = message.payload.identifier
                request_cache.process()

    class MSimilarityRequest(Cache):
        timeout_delay = 7.0
        cleanup_delay = 0.0

        def __init__(self, community, message, requested_candidates):
            self.community = community
            self.hisList, self.myList = self.community.process_rsa_simirequest([message], send_messages=False)

            self.requesting_candidate = message.candidate
            self.requested_candidates = requested_candidates
            self.requested_mids = set()
            for candidate in self.requested_candidates:
                for member in candidate.get_members(community):
                    self.requested_mids.add(member.mid)

            self.received_candidates = set()
            self.received_lists = []
            self.isProcessed = False

        def add_response(self, candidate_mid, response):
            if candidate_mid in self.requested_mids:
                if candidate_mid not in self.received_candidates:
                    self.received_candidates.add(candidate_mid)
                    self.received_lists.append((candidate_mid, response))

        def is_complete(self):
            return len(self.received_lists) == len(self.requested_candidates)

        def process(self):
            if not self.isProcessed:
                meta_request = self.community.get_meta_message(u"msimilarity-response")
                response = meta_request.impl(authentication=(self.community._my_member,),
                                        distribution=(self.community.global_time,),
                                        destination=(self.requesting_candidate,),
                                        payload=(self.identifier, self.hisList, self.myList, self.received_lists))

                self.community._dispersy._forward([response])
                self.isProcessed = True

                if DEBUG_VERBOSE:
                    print >> sys.stderr, long(time()), "HSearchCommunity: processed MSimilarityRequest send msimilarity-response to", self.requesting_candidate

                self.community._dispersy.request_cache.pop(self.identifier, HSearchCommunity.MSimilarityRequest)

        def on_timeout(self):
            if not self.isProcessed:
                if DEBUG:
                    print >> sys.stderr, long(time()), "HSearchCommunity: timeout MSimilarityRequest", self.identifier, len(self.received_lists), len(self.requested_candidates)

                self.process()

    def on_encr_response(self, messages):
        for message in messages:
            request = self._dispersy.request_cache.get(message.payload.identifier, HSearchCommunity.MSimilarityRequest)
            if request:
                request.add_response(message.authentication.member.mid, (message.payload.preference_list, message.payload.his_preference_list))
                if request.is_complete():
                    request.process()

    def on_msimi_response(self, messages):
        # process as normal encr_response message
        SearchCommunity.on_encr_response(self, messages)

        # process possible taste buddies
        for message in messages:
#            candidate = self._dispersy.get_walkcandidate(message, self)
#            candidate.walk_response(self)
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "HSearchCommunity: got msimi response from", message.candidate, len(message.payload.bundled_responses)

            possibles = []
            for candidate_mid, remote_response in message.payload.bundled_responses:
                overlap = self.compute_rsa_overlap(remote_response[0], remote_response[1])
                possibles.append([overlap, time(), candidate_mid, message.candidate])

            self.add_possible_taste_buddies(possibles)

            request = self._dispersy.request_cache.pop(message.payload.identifier, ForwardCommunity.ForwardAttempt)
            if request:
                destination, introduce_me_to = self.get_most_similar(message.candidate)
                self.send_introduction_request(destination, introduce_me_to)

                if DEBUG and introduce_me_to:
                    print >> sys.stderr, long(time()), "HSearchCommunity: asking candidate %s to introduce me to %s after receiving similarities from %s" % (destination, introduce_me_to.encode("HEX"), message.candidate)

class Das4DBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy

        self.myPreferences = set()
        self.myTestPreferences = set()
        
        try:
            # python 2.7 only...
            from collections import OrderedDict
        except ImportError:
            from python27_ordereddict import OrderedDict
        
        self.myMegaCache = OrderedDict()
        self.id2category = {1:u''}

    def addMyPreference(self, torrent_id, data):
        infohash = str(torrent_id)
        self.myPreferences.add(infohash)

    def addTestPreference(self, torrent_id):
        infohash = str(torrent_id)
        self.myTestPreferences.add(infohash)

    def getMyPrefListInfohash(self, limit=None, local=True):
        preferences = self.myPreferences
        if not local:
            preferences = preferences | self.myTestPreferences
        preferences = list(preferences)

        if limit:
            return preferences[:limit]
        return preferences

    def searchNames(self, keywords, local=True, keys=[]):
        my_preferences = {}
        for infohash in self.getMyPrefListInfohash(local=local):
            my_preferences[infohash] = unicode(self._dispersy._lan_address)
        for infohash, results in self.myMegaCache.iteritems():
            if infohash not in my_preferences:
                my_preferences[infohash] = results[1]
            
        results = []
        for keyword in keywords:
            infohash = str(keyword)
            if infohash in my_preferences:
                results.append((infohash, unicode(self._dispersy._lan_address), 1L, 1, 1, 0L, 0, 0, None, None, None, None, '', '', 0, 0, 0, 0, 0, False))
        return results

    def on_search_response(self, results):
        for result in results:
            if result[0] not in self.myMegaCache:
                self.myMegaCache[result[0]] = (result[0], result[1], 0, 0, 0, time())
        return len(self.myMegaCache)

    def deleteTorrent(self, infohash, delete_file=False, commit=True):
        if infohash in self.myMegaCache:
            del self.myMegaCache[infohash]

    def on_pingpong(self, torrents):
        unknown_torrents = [[infohash, ] for infohash, _, _, _, _ in torrents if infohash not in self.myMegaCache]
        if len(unknown_torrents) > 5:
            unknown_torrents = sample(unknown_torrents, 5)
        return self.on_search_response(unknown_torrents)

    def getRecentlyCollectedSwiftHashes(self, limit=None):
        megaCache = self.myMegaCache.values()
        if limit:
            return megaCache[-limit:]
        return megaCache

    def getRandomlyCollectedSwiftHashes(self, leastRecent=0, limit=None):
        megaCache = self.myMegaCache.values()
        shuffle(megaCache)

        if limit:
            return megaCache[:limit]
        return megaCache
