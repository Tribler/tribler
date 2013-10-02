# Written by Niels Zeilemaker

from Tribler.dispersy.logger import get_logger
logger = get_logger(__name__)

import sys
from time import time
from random import shuffle
from traceback import print_exc

from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination,\
    CommunityDestination
from Tribler.dispersy.distribution import DirectDistribution,\
    FullSyncDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.resolution import PublicResolution

from Tribler.community.search.conversion import SearchConversion
from Tribler.community.search.payload import SearchRequestPayload,\
    SearchResponsePayload, TorrentRequestPayload, TorrentCollectRequestPayload,\
    TorrentCollectResponsePayload, TasteIntroPayload
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.community.channel.payload import TorrentPayload
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.requestcache import Cache
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME,\
    WalkCandidate, BootstrapCandidate
from Tribler.dispersy.dispersy import IntroductionRequestCache
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler,\
    LOW_PRIO_COLLECTING
from Tribler.Core.TorrentDef import TorrentDef
from os import path
from Tribler.Core.CacheDB.sqlitecachedb import bin2str

DEBUG = False
SWIFT_INFOHASHES = 0


class SearchCommunity(Community):

    """
    A single community that all Tribler members join and use to disseminate .torrent files.
    """
    @classmethod
    def get_master_members(cls, dispersy):
# generated: Mon May  7 17:43:59 2012
# curve: high <<< NID_sect571r1 >>>
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000405c09348b2243e53fa190f17fc8c9843d61fc67e8ea22d7b031913ffc912897b57be780c06213dbf937d87e3ef1d48bf8f76e03d5ec40b1cdb877d9fa1ec1f133a412601c262d9ef01840ffc49d6131b1df9e1eac41a8ff6a1730d4541a64e733ed7cee415b220e4a0d2e8ace5099520bf8896e09cac3800a62974f5574910d75166d6529dbaf016e78090afbfaf8373
# pub-sha1 2782dc9253cef6cc9272ee8ed675c63743c4eb3a
#-----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQFwJNIsiQ+U/oZDxf8jJhD1h/Gfo6i
# LXsDGRP/yRKJe1e+eAwGIT2/k32H4+8dSL+PduA9XsQLHNuHfZ+h7B8TOkEmAcJi
# 2e8BhA/8SdYTGx354erEGo/2oXMNRUGmTnM+187kFbIg5KDS6KzlCZUgv4iW4Jys
# OACmKXT1V0kQ11Fm1lKduvAW54CQr7+vg3M=
#-----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000405c09348b2243e53fa190f17fc8c9843d61fc67e8ea22d7b031913ffc912897b57be780c06213dbf937d87e3ef1d48bf8f76e03d5ec40b1cdb877d9fa1ec1f133a412601c262d9ef01840ffc49d6131b1df9e1eac41a8ff6a1730d4541a64e733ed7cee415b220e4a0d2e8ace5099520bf8896e09cac3800a62974f5574910d75166d6529dbaf016e78090afbfaf8373".decode("HEX")
        master = dispersy.get_member(master_key)
        return [master]

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True):
        try:
            dispersy.database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler)
        else:
            return super(SearchCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler)

    def __init__(self, dispersy, master, integrate_with_tribler=True):
        super(SearchCommunity, self).__init__(dispersy, master)

        self.integrate_with_tribler = integrate_with_tribler
        self.taste_buddies = []
        # To always connect to a peer uncomment/modify the following line
        # self.taste_buddies.append([1, time(), Candidate(("127.0.0.1", 1234), False))

        if self.integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, TorrentDBHandler, MyPreferenceDBHandler
            from Tribler.Core.CacheDB.Notifier import Notifier

            # tribler channelcast database
            self._channelcast_db = ChannelCastDBHandler.getInstance()
            self._torrent_db = TorrentDBHandler.getInstance()
            self._mypref_db = MyPreferenceDBHandler.getInstance()
            self._notifier = Notifier.getInstance()

            # torrent collecting
            self._rtorrent_handler = RemoteTorrentHandler.getInstance()
        else:
            self._channelcast_db = ChannelCastDBStub(self._dispersy)
            self._torrent_db = None
            self._mypref_db = None
            self._notifier = None

        self.taste_bloom_filter = None
        self.taste_bloom_filter_key = None

        self.torrent_cache = None

        self.dispersy.callback.register(self.create_torrent_collect_requests, delay=CANDIDATE_WALK_LIFETIME)
        self.dispersy.callback.register(self.fast_walker)

    def fast_walker(self):
        for cycle in xrange(10):
            now = time()

            # count -everyone- that is active (i.e. walk or stumble)
            active_canidates = list(self.dispersy_yield_verified_candidates())
            if len(active_canidates) > 20:
                logger.debug("there are %d active non-bootstrap candidates available, prematurely quitting fast walker", len(active_canidates))
                break

            # request -everyone- that is eligible
            eligible_candidates = [candidate
                                   for candidate
                                   in self._candidates.itervalues()
                                   if candidate.is_eligible_for_walk(now)]
            for candidate in eligible_candidates:
                logger.debug("extra walk to %s", candidate)
                self.create_introduction_request(candidate, allow_sync=False, is_fast_walker=True)

            # poke bootstrap peers
            if cycle < 2:
                for candidate in self._dispersy.bootstrap_candidates:
                    logger.debug("extra walk to %s", candidate)
                    self.create_introduction_request(candidate, allow_sync=False, is_fast_walker=True)

            # wait for NAT hole punching
            yield 1.0

        logger.debug("finished")

    def initiate_meta_messages(self):
        return [Message(self, u"search-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SearchRequestPayload(), self.check_search, self.on_search),
                Message(self, u"search-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SearchResponsePayload(), self.check_search_response, self.on_search_response),
                Message(self, u"torrent-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), TorrentRequestPayload(), self.check_torrent_request, self.on_torrent_request),
                Message(self, u"torrent-collect-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), TorrentCollectRequestPayload(), self.check_torrent_collect_request, self.on_torrent_collect_request),
                Message(self, u"torrent-collect-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), TorrentCollectResponsePayload(), self.check_torrent_collect_response, self.on_torrent_collect_response),
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=0), TorrentPayload(), self.check_torrent, self.on_torrent),
                ]

    def _initialize_meta_messages(self):
        Community._initialize_meta_messages(self)

        ori = self._meta_messages[u"dispersy-introduction-request"]
        self._disp_intro_handler = ori.handle_callback

        new = Message(self, ori.name, ori.authentication, ori.resolution, ori.distribution, ori.destination, TasteIntroPayload(), ori.check_callback, self.on_taste_intro)
        self._meta_messages[u"dispersy-introduction-request"] = new

    def initiate_conversions(self):
        return [DefaultConversion(self), SearchConversion(self)]

    @property
    def dispersy_auto_download_master_member(self):
        # there is no dispersy-identity for the master member, so don't try to download
        return False

    @property
    def dispersy_enable_bloom_filter_sync(self):
        # 1. disable bloom filter sync in walker
        # 2. accept messages in any global time range
        return False

    def add_taste_buddies(self, new_taste_buddies):
        for new_tb_tuple in new_taste_buddies[:]:
            for tb_tuple in self.taste_buddies:
                if tb_tuple[-1].sock_addr == new_tb_tuple[-1].sock_addr:

                    # update similarity
                    tb_tuple[0] = max(new_tb_tuple[0], tb_tuple[0])
                    new_taste_buddies.remove(new_tb_tuple)
                    break
            else:
                self.taste_buddies.append(new_tb_tuple)

        self.taste_buddies.sort(reverse=True)
        self.taste_buddies = self.taste_buddies[:10]

        # Send ping to all new candidates
        if len(new_taste_buddies) > 0:
            self._create_torrent_collect_requests([tb_tuple[-1] for tb_tuple in new_taste_buddies])

    def get_nr_connections(self):
        return len(self.get_connections())

    def get_connections(self):
        # add 10 taste buddies and 20 - len(taste_buddies) to candidates
        candidates = set(candidate for _, _, candidate in self.taste_buddies)
        sock_addresses = set(candidate.sock_addr for _, _, candidate in self.taste_buddies)

        for candidate in self.dispersy_yield_candidates():
            if candidate.sock_addr not in sock_addresses:
                candidates.add(candidate)
                sock_addresses.add(candidate.sock_addr)

            if len(candidates) == 20:
                break
        return candidates

    def __calc_similarity(self, candidate, myPrefs, hisPrefs, overlap):
        if myPrefs > 0 and hisPrefs > 0:
            myRoot = 1.0 / (myPrefs ** .5)
            sim = overlap * (myRoot * (1.0 / (hisPrefs ** .5)))
            return [sim, time(), candidate]

        return [0, time(), candidate]

    def create_introduction_request(self, destination, allow_sync, is_fast_walker=False):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        if DEBUG:
            print >> sys.stderr, "SearchCommunity: sending introduction request to", destination

        destination.walk(time(), IntroductionRequestCache.timeout_delay)
        self.add_candidate(destination)

        advice = True
        if not (isinstance(destination, BootstrapCandidate) or is_fast_walker):
            myPreferences = sorted(self._mypref_db.getMyPrefListInfohash(limit=500))
            num_preferences = len(myPreferences)

            myPref_key = ",".join(map(bin2str, myPreferences))
            if myPref_key != self.taste_bloom_filter_key:
                if num_preferences > 0:
                    # no prefix changing, we want false positives (make sure it is a single char)
                    self.taste_bloom_filter = BloomFilter(0.005, len(myPreferences), prefix=' ')
                    self.taste_bloom_filter.add_keys(myPreferences)
                else:
                    self.taste_bloom_filter = None

                self.taste_bloom_filter_key = myPref_key

            taste_bloom_filter = self.taste_bloom_filter

            identifier = self._dispersy.request_cache.claim(IntroductionRequestCache(self, destination))
            payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, num_preferences, taste_bloom_filter)
        else:
            identifier = self._dispersy.request_cache.claim(IntroductionRequestCache(self, destination))
            payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, 0, None)

        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                   distribution=(self.global_time,),
                                destination=(destination,),
                                payload=payload)

        logger.debug("%s %s sending introduction request to %s", self.cid.encode("HEX"), type(self), destination)

        self._dispersy.statistics.walk_attempt += 1
        if isinstance(destination, BootstrapCandidate):
            self._dispersy.statistics.walk_bootstrap_attempt += 1
        if request.payload.advice:
            self._dispersy.statistics.walk_advice_outgoing_request += 1

        self._dispersy._forward([request])
        return request

    def on_taste_intro(self, messages):
        self._disp_intro_handler(messages)
        messages = [message for message in messages if not isinstance(self.get_candidate(message.candidate.sock_addr), BootstrapCandidate)]

        if any(message.payload.taste_bloom_filter for message in messages):
            myPreferences = self._mypref_db.getMyPrefListInfohash(limit=500)
        else:
            myPreferences = []

        newTasteBuddies = []
        for message in messages:
            taste_bloom_filter = message.payload.taste_bloom_filter
            num_preferences = message.payload.num_preferences
            if taste_bloom_filter:
                overlap = sum(infohash in taste_bloom_filter for infohash in myPreferences)
            else:
                overlap = 0

            newTasteBuddies.append(self.__calc_similarity(message.candidate, len(myPreferences), num_preferences, overlap))

        if len(newTasteBuddies) > 0:
            self.add_taste_buddies(newTasteBuddies)

        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d" % message.candidate.sock_addr)

    class SearchRequest(Cache):
        timeout_delay = 30.0
        cleanup_delay = 0.0

        def __init__(self, keywords, callback):
            self.keywords = keywords
            self.callback = callback

        def on_timeout(self):
            pass

    def create_search(self, keywords, callback):
        # register callback/fetch identifier
        identifier = self._dispersy.request_cache.claim(SearchCommunity.SearchRequest(keywords, callback))

        candidates = self.get_connections()
        if len(candidates) > 0:
            if DEBUG:
                print >> sys.stderr, "SearchCommunity: sending search request for", keywords, "to", map(str, candidates)

            # create channelcast request message
            meta = self.get_meta_message(u"search-request")
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(identifier, keywords))

            self._dispersy._send(candidates, [message])

        return len(candidates)

    def check_search(self, messages):
        return messages

    def on_search(self, messages):
        for message in messages:
            keywords = message.payload.keywords

            if DEBUG:
                print >> sys.stderr, "SearchCommunity: got search request for", keywords

            results = []
            dbresults = self._torrent_db.searchNames(keywords, local=False, keys= ['infohash', 'T.name', 'T.length', 'T.num_files', 'T.category_id', 'T.creation_date', 'T.num_seeders', 'T.num_leechers', 'swift_hash', 'swift_torrent_hash'])
            if len(dbresults) > 0:
                for dbresult in dbresults:
                    channel_details = dbresult[-10:]

                    dbresult = list(dbresult[:10])
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
            elif DEBUG:
                print >> sys.stderr, "SearchCommunity: no results"

            self._create_search_response(message.payload.identifier, results, message.candidate)

    def _create_search_response(self, identifier, results, candidate):
        # create search-response message
        meta = self.get_meta_message(u"search-response")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), destination=(candidate,), payload=(identifier, results))
        self._dispersy._forward([message])

        if DEBUG:
            print >> sys.stderr, "SearchCommunity: returning", len(results), "results to", candidate

    def check_search_response(self, messages):
        return messages

    def on_search_response(self, messages):
        # _get_channel_community could cause multiple commits, using this with clause this is reduced to only one.
        with self._dispersy.database:
            for message in messages:
                # fetch callback using identifier
                search_request = self._dispersy.request_cache.get(message.payload.identifier, SearchCommunity.SearchRequest)
                if search_request:
                    if DEBUG:
                        print >> sys.stderr, "SearchCommunity: got search response for", search_request.keywords, len(message.payload.results), message.candidate

                    if len(message.payload.results) > 0:
                        self._torrent_db.on_search_response(message.payload.results)

                    search_request.callback(search_request.keywords, message.payload.results, message.candidate)

                    # see if we need to join some channels
                    channels = set([result[10] for result in message.payload.results if result[10]])
                    if channels:
                        channels = self._get_unknown_channels(channels)

                        if DEBUG:
                            print >> sys.stderr, "SearchCommunity: joining %d preview communities" % len(channels)

                        for cid in channels:
                            community = self._get_channel_community(cid)
                            community.disp_create_missing_channel(message.candidate, includeSnapshot=False)
                else:
                    if DEBUG:
                        print >> sys.stderr, "SearchCommunity: got search response identifier not found", message.payload.identifier

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
                            distribution=(self.global_time,), destination=(candidate,), payload=(torrentdict,))
        self._dispersy._forward([message])

        if DEBUG:
            nr_requests = sum([len(cid_torrents) for cid_torrents in torrentdict.values()])
            print >> sys.stderr, "SearchCommunity: requesting", nr_requests, "TorrentMessages from", candidate

    def check_torrent_request(self, messages):
        return messages

    def on_torrent_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                requested_packets.extend(self._get_packets_from_infohashes(cid, torrents))

            if requested_packets:
                self._dispersy.statistics.dict_inc(self._dispersy.statistics.outgoing, u"torrent-response", len(requested_packets))
                self._dispersy.endpoint.send([message.candidate], requested_packets)

            if DEBUG:
                print >> sys.stderr, "SearchCommunity: got request for ", len(requested_packets), "torrents from", message.candidate

    class PingRequestCache(IntroductionRequestCache):

        def __init__(self, community, candidate):
            self.candidate = candidate
            IntroductionRequestCache.__init__(self, community, None)

        def on_timeout(self):
            refreshIf = time() - CANDIDATE_WALK_LIFETIME
            remove = None
            for taste_buddy in self.community.taste_buddies:
                if taste_buddy[2] == self.candidate:
                    if taste_buddy[1] < refreshIf:
                        remove = taste_buddy
                    break

            if remove:
                if DEBUG:
                    print >> sys.stderr, "SearchCommunity: no response on ping, removing from taste_buddies", self.candidate
                self.community.taste_buddies.remove(remove)

    def create_torrent_collect_requests(self):
        while True:
            refreshIf = time() - CANDIDATE_WALK_LIFETIME
            try:
                # determine to which peers we need to send a ping
                candidates = [candidate for _, prev, candidate in self.taste_buddies if prev < refreshIf]
                self._create_torrent_collect_requests(candidates)
            except:
                print_exc()

            yield 5.0

    def _create_torrent_collect_requests(self, candidates):
        if len(candidates) > 0:
            self._create_pingpong(u"torrent-collect-request", candidates)

    def check_torrent_collect_request(self, messages):
        logger.debug("%d messages received", len(messages))
        return messages

    def on_torrent_collect_request(self, messages):
        logger.debug("%d messages received", len(messages))
        candidates = [message.candidate for message in messages]
        identifiers = [message.payload.identifier for message in messages]

        self._create_pingpong(u"torrent-collect-response", candidates, identifiers)
        self.on_torrent_collect_response(messages, verifyRequest=False)

    def check_torrent_collect_response(self, messages):
        logger.debug("%d messages received", len(messages))
        return messages

    def on_torrent_collect_response(self, messages, verifyRequest=True):
        logger.debug("%d messages received", len(messages))
        toInsert = {}
        toCollect = {}
        toPopularity = {}
        for message in messages:
            if verifyRequest:
                pong_request = self._dispersy.request_cache.pop(message.payload.identifier, SearchCommunity.PingRequestCache)
                logger.debug("pop %s", pong_request.helper_candidate if pong_request else "unknown")
            else:
                logger.debug("no-pop")
                pong_request = True

            if pong_request and message.payload.hashtype == SWIFT_INFOHASHES:
                for roothash, infohash, seeders, leechers, ago in message.payload.torrents:
                    toInsert[infohash] = [infohash, roothash]
                    toPopularity[infohash] = [seeders, leechers, time() - (ago * 60)]
                    toCollect.setdefault(infohash, []).append(message.candidate)

        if len(toInsert) > 0:
            self._torrent_db.on_torrent_collect_response(toInsert.values())

        hashes = [hash_ for hash_ in toCollect.keys() if hash_]
        if hashes:
            hashesToCollect = self._torrent_db.selectSwiftTorrentsToCollect(hashes)
            for infohash, roothash in hashesToCollect[:5]:
                for candidate in toCollect[infohash]:
                    if DEBUG:
                        from Tribler.Core.CacheDB.sqlitecachedb import bin2str
                        print >> sys.stderr, "SearchCommunity: requesting .torrent after receiving ping/pong ", candidate, bin2str(infohash), bin2str(roothash)

                    self._rtorrent_handler.download_torrent(candidate, infohash, roothash, prio=LOW_PRIO_COLLECTING, timeout= CANDIDATE_WALK_LIFETIME)

    def _create_pingpong(self, meta_name, candidates, identifiers=None):
        max_len = self.dispersy_sync_bloom_filter_bits / 8
        limit = int(max_len / 44)

        torrents = self.__get_torrents(limit)
        for index, candidate in enumerate(candidates):
            if identifiers:
                identifier = identifiers[index]
            else:
                identifier = self._dispersy.request_cache.claim(SearchCommunity.PingRequestCache(self, candidate))

            # create torrent-collect-request/response message
            meta = self.get_meta_message(meta_name)
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), destination=(candidate,), payload=(identifier, SWIFT_INFOHASHES, torrents))

            self._dispersy._forward([message])

            if DEBUG:
                print >> sys.stderr, "SearchCommunity: send", meta_name, "to", candidate

        addresses = [candidate.sock_addr for candidate in candidates]
        for taste_buddy in self.taste_buddies:
            if taste_buddy[2].sock_addr in addresses:
                taste_buddy[1] = time()

    def __get_torrents(self, limit):
        cache_timeout = CANDIDATE_WALK_LIFETIME
        if self.torrent_cache and self.torrent_cache[0] > (time() - cache_timeout):
            return self.torrent_cache[1]

        # we want roughly 1/3 random, 2/3 recent
        limitRecent = int(limit * 0.66)
        limitRandom = limit - limitRecent

        torrents = self._torrent_db.getRecentlyCollectedSwiftHashes(limit=limitRecent) or []
        if len(torrents) == limitRecent:
            leastRecent = torrents[-1][5]
            randomTorrents = self._torrent_db.getRandomlyCollectedSwiftHashes(leastRecent, limit=limitRandom) or []
        else:
            randomTorrents = []

        # combine random and recent + shuffle to obscure categories
        torrents = [tor[:5] for tor in torrents] + randomTorrents
        shuffle(torrents)

        # fix leechers, seeders to max 2**16 (shift values +2 to accomodate -2 and -1 values)
        max_value = (2 ** 16) - 1
        for torrent in torrents:
            torrent[2] = min(max_value, (torrent[2] or -1) + 2)
            torrent[3] = min(max_value, (torrent[3] or -1) + 2)

            # convert to minutes
            torrent[4] /= 60
            if torrent[4] > max_value or torrent[4] < 0:
                torrent[4] = max_value

        self.torrent_cache = (time(), torrents)
        return torrents

    def create_torrent(self, filename, store=True, update=True, forward=True):
        if path.exists(filename):
            try:
                torrentdef = TorrentDef.load(filename)
                files = torrentdef.get_files_as_unicode_with_length()

                return self._disp_create_torrent(torrentdef.get_infohash(), long(time()), torrentdef.get_name_as_unicode(), tuple(files), torrentdef.get_trackers_as_single_tuple(), store, update, forward)
            except ValueError:
                pass
            except:
                print_exc()
        return False

    def _disp_create_torrent(self, infohash, timestamp, name, files, trackers, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"torrent")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(infohash, timestamp, name, files, trackers))

        self._dispersy.store_update_forward([message], store, update, forward)
        self._torrent_db.updateTorrent(infohash, notify=False, dispersy_id= message.packet_id)
        return message

    def check_torrent(self, messages):
        return messages

    def on_torrent(self, messages):
        for message in messages:
            self._torrent_db.addExternalTorrentNoDef(message.payload.infohash, message.payload.name, message.payload.files, message.payload.trackers, message.payload.timestamp, "DISP_SC", {'dispersy_id': message.packet_id})

    def _get_channel_id(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        return self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(cid),))

    def _get_unknown_channels(self, cids):
        assert all(isinstance(cid, str) for cid in cids)
        assert all(len(cid) == 20 for cid in cids)

        parameters = u",".join(["?"] * len(cids))
        known_cids = self._channelcast_db._db.fetchall(u"SELECT dispersy_cid FROM Channels WHERE dispersy_cid in (" + parameters +")", map(buffer, cids))
        known_cids = map(str, known_cids)
        return [cid for cid in cids if cid not in known_cids]

    def _get_channel_community(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        try:
            return self._dispersy.get_community(cid, True)
        except KeyError:
            logger.debug("join preview community %s", cid.encode("HEX"))
            return PreviewChannelCommunity.join_community(self._dispersy, self._dispersy.get_temporary_member_from_id(cid), self._my_member, self.integrate_with_tribler)

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
                        message = self.create_torrent(torrent['torrent_file_name'], store=True, update= False, forward = False)
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


class ChannelCastDBStub():

    def __init__(self, dispersy):
        self._dispersy = dispersy

        self.cachedTorrents = None

    def convert_to_messages(self, results):
        messages = self._dispersy.convert_packets_to_messages(str(packet) for packet, _ in results)
        for packet_id, message in zip((packet_id for _, packet_id in results), messages):
            if message:
                message.packet_id = packet_id
                yield message.community.cid, message

    def newTorrent(self, message):
        self._cachedTorrents[message.payload.infohash] = message

    def hasTorrents(self, channel_id, infohashes):
        returnAr = []
        for infohash in infohashes:
            if infohash in self._cachedTorrents:
                returnAr.append(True)
            else:
                returnAr.append(False)
        return returnAr

    def getTorrentFromChannelId(self, channel_id, infohash, keys):
        if infohash in self._cachedTorrents:
            return self._cachedTorrents[infohash].packet_id

    def on_dynamic_settings(self, channel_id):
        pass

    @property
    def _cachedTorrents(self):
        if self.cachedTorrents is None:
            self.cachedTorrents = {}
            self._cacheTorrents()

        return self.cachedTorrents

    def _cacheTorrents(self):
        sql = u"SELECT sync.packet, sync.id FROM sync JOIN meta_message ON sync.meta_message = meta_message.id JOIN community ON community.id = sync.community WHERE meta_message.name = 'torrent'"
        results = list(self._dispersy.database.execute(sql))
        messages = self.convert_to_messages(results)

        for _, message in messages:
            self._cachedTorrents[message.payload.infohash] = message
