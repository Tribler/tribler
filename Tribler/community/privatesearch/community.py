# Written by Niels Zeilemaker
import sys
from os import path
from time import time
from random import sample, randint, shuffle, random, choice
from Crypto.Util.number import bytes_to_long, long_to_bytes
from math import ceil
from hashlib import md5
from itertools import groupby

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
from Tribler.dispersy.script import assert_

from Tribler.community.privatesemantic.community import PForwardCommunity, \
    HForwardCommunity, PoliForwardCommunity

if __debug__:
    from Tribler.dispersy.dprint import dprint

DEBUG = False
DEBUG_VERBOSE = False
TTL = 4
NEIGHBORS = 5
FNEIGHBORS = 1
ENCRYPTION = True
PING_INTERVAL = CANDIDATE_WALK_LIFETIME - 5.0

class TTLSearchCommunity(Community):
    """
    A single community that all Tribler members join and use to disseminate .torrent files.
    """
    @classmethod
    def get_master_members(cls):
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000404a041c3a8415021f193ef0614360b4d99ac8f985eff2259f88f1f64070ae2bcc21c473c9c0b958b39da9ae58d6d0aec316341f65bd7daa42ffd73f5eeee53aa6199793f98afc47f008a601cd659479f801157e7dd69525649d8eec7885bd0d832746c46d067c60341a6d84b12a6e5d3ce25e20352ed8e0ff311e74b801c06286a852976bdba67dfe62dfb75a5b9c0d2".decode("HEX")
        master = Member(master_key)
        return [master]

    def __init__(self, master, integrate_with_tribler=True, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True):
        super(SearchCommunity).__init__(self, master, integrate_with_tribler)

        self.ttl = ttl
        self.neighbors = neighbors
        self.fneighbors = fneighbors
        self.log_searches = bool(log_searches)
        self.use_megacache = bool(use_megacache)

        self.search_timeout = 0
        self.search_forward = 0
        self.search_forward_success = 0
        self.search_forward_timeout = 0
        self.search_endpoint = 0
        self.search_cycle_detected = 0
        self.search_megacachesize = 0
        self.search_no_candidates_remain = 0

        if self.integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, TorrentDBHandler, MyPreferenceDBHandler
            from Tribler.Core.CacheDB.Notifier import Notifier

            # tribler channelcast database
            self._channelcast_db = ChannelCastDBHandler.getInstance()
            self._torrent_db = TorrentDBHandler.getInstance()
            self._mypref_db = MyPreferenceDBHandler.getInstance()
            self._notifier = Notifier.getInstance()

            # fast connecting
            self.dispersy.callback.register(self.fast_walker)

        else:
            self._mypref_db = self._torrent_db = self._channelcast_db = Das4DBStub(self._dispersy)
            self._notifier = None

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
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=0), TorrentPayload(), self._dispersy._generic_timeline_check, self.on_torrent)
                ]

    def initiate_conversions(self):
        return [DefaultConversion(self), SearchConversion(self)]

    @property
    def dispersy_auto_download_master_member(self):
        # there is no dispersy-identity for the master member, so don't try to download
        return False

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

        if ttl == None:
            if isinstance(self.ttl, tuple):
                _ttl = randint(self.ttl[0], self.ttl[1])
            elif isinstance(self.ttl, int):
                _ttl = self.ttl
            else:
                _ttl = 1
        else:
            _ttl = ttl

        if nrcandidates == None:
            nrcandidates = self.neighbors

        if isinstance(nrcandidates, tuple):
            nrcandidates = randint(nrcandidates[0], nrcandidates[1])
        elif isinstance(nrcandidates, float):
            nrcandidates = int(ceil(_ttl * nrcandidates))

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

        if len(ignore_candidates) < 10:
            random_peers, taste_buddies = self.get_randompeers_tastebuddies(ignore_candidates)
            shuffle(taste_buddies)
            shuffle(random_peers)

            for _ in xrange(nrcandidates):
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

class SearchCommunity(HForwardCommunity, TTLSearchCommunity):

    @classmethod
    def load_community(cls, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return Community.load_community(master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, master, integrate_with_tribler=True, encryption=ENCRYPTION, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        HForwardCommunity.__init__(master, integrate_with_tribler, encryption, 0, max_prefs, max_fprefs)
        TTLSearchCommunity.__init__(master, integrate_with_tribler, ttl, neighbors, fneighbors, log_searches, use_megacache)

class PSearchCommunity(PForwardCommunity, TTLSearchCommunity):

    @classmethod
    def load_community(cls, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return Community.load_community(master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, master, integrate_with_tribler=True, encryption=ENCRYPTION, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        PForwardCommunity.__init__(master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs)
        TTLSearchCommunity.__init__(master, integrate_with_tribler, ttl, neighbors, fneighbors, log_searches, use_megacache)

class HSearchCommunity(HForwardCommunity, TTLSearchCommunity):

    @classmethod
    def load_community(cls, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return Community.load_community(master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, master, integrate_with_tribler=True, encryption=ENCRYPTION, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        HForwardCommunity.__init__(master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs)
        TTLSearchCommunity.__init__(master, integrate_with_tribler, ttl, neighbors, fneighbors, log_searches, use_megacache)

class PoliSearchCommunity(PoliForwardCommunity, TTLSearchCommunity):

    @classmethod
    def load_community(cls, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return Community.load_community(master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, ttl=ttl, neighbors=neighbors, fneighbors=fneighbors, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, master, integrate_with_tribler=True, encryption=ENCRYPTION, ttl=TTL, neighbors=NEIGHBORS, fneighbors=FNEIGHBORS, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        PoliForwardCommunity.__init__(master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs)
        TTLSearchCommunity.__init__(master, integrate_with_tribler, ttl, neighbors, fneighbors, log_searches, use_megacache)

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
                results.append((infohash, my_preferences[infohash], 1L, 1, 1, 0L, 0, 0, None, None, None, None, '', '', 0, 0, 0, 0, 0, False))
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
