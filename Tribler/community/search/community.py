# Written by Niels Zeilemaker
import logging
from os import path
from random import shuffle
from time import time
from traceback import print_exc

from twisted.internet.task import LoopingCall

from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.community.channel.payload import TorrentPayload
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.community.search.conversion import SearchConversion
from Tribler.community.search.payload import (SearchRequestPayload, SearchResponsePayload, TorrentRequestPayload,
                                              TorrentCollectRequestPayload, TorrentCollectResponsePayload,
                                              TasteIntroPayload)
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME, WalkCandidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.database import IgnoreCommits
from Tribler.dispersy.destination import CandidateDestination, CommunityDestination
from Tribler.dispersy.distribution import DirectDistribution, FullSyncDistribution
from Tribler.dispersy.exception import CommunityNotFoundException
from Tribler.dispersy.message import Message
from Tribler.dispersy.requestcache import RandomNumberCache, IntroductionRequestCache
from Tribler.dispersy.resolution import PublicResolution


logger = logging.getLogger(__name__)


DEBUG = False
SWIFT_INFOHASHES = 0
CREATE_TORRENT_COLLECT_INTERVAL = 5

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
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def initialize(self, integrate_with_tribler=True, log_incomming_searches=False):
        super(SearchCommunity, self).initialize()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.integrate_with_tribler = integrate_with_tribler
        self.log_incomming_searches = log_incomming_searches
        self.taste_buddies = []
        # To always connect to a peer uncomment/modify the following line
        # self.taste_buddies.append([1, time(), Candidate(("127.0.0.1", 1234), False))

        if self.integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, TorrentDBHandler, MyPreferenceDBHandler, MiscDBHandler
            from Tribler.Core.CacheDB.Notifier import Notifier

            # tribler channelcast database
            self._channelcast_db = ChannelCastDBHandler.getInstance()
            self._misc_db = MiscDBHandler.getInstance()
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

        self._pending_tasks["create torrent collect requests"] = lc = LoopingCall(self.create_torrent_collect_requests)
        lc.start(CREATE_TORRENT_COLLECT_INTERVAL, now=True)

    @property
    def dispersy_enable_fast_candidate_walker(self):
        return True

    def initiate_meta_messages(self):
        return super(SearchCommunity, self).initiate_meta_messages() + [
            Message(self, u"search-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    SearchRequestPayload(),
                    self.check_search,
                    self.on_search),
            Message(self, u"search-response",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    SearchResponsePayload(),
                    self.check_search_response,
                    self.on_search_response),
            Message(self, u"torrent-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TorrentRequestPayload(),
                    self.check_torrent_request,
                    self.on_torrent_request),
            Message(self, u"torrent-collect-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TorrentCollectRequestPayload(),
                    self.check_torrent_collect_request,
                    self.on_torrent_collect_request),
            Message(self, u"torrent-collect-response",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TorrentCollectResponsePayload(),
                    self.check_torrent_collect_response,
                    self.on_torrent_collect_response),
            Message(self, u"torrent",
                    MemberAuthentication(),
                    PublicResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=128),
                    CommunityDestination(node_count=0),
                    TorrentPayload(),
                    self.check_torrent,
                    self.on_torrent),
        ]

    def _initialize_meta_messages(self):
        Community._initialize_meta_messages(self)

        ori = self._meta_messages[u"dispersy-introduction-request"]
        new = Message(self, ori.name, ori.authentication, ori.resolution, ori.distribution, ori.destination, TasteIntroPayload(), ori.check_callback, ori.handle_callback)
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
            self._logger.debug("SearchCommunity: sending introduction request to %s", destination)

        advice = True
        if not is_fast_walker:
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

            cache = self._request_cache.add(IntroductionRequestCache(self, destination))
            payload = (destination.sock_addr, self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, cache.number, num_preferences, taste_bloom_filter)
        else:
            cache = self._request_cache.add(IntroductionRequestCache(self, destination))
            payload = (destination.sock_addr, self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, cache.number, 0, None)

        destination.walk(time())
        self.add_candidate(destination)

        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                   distribution=(self.global_time,),
                                destination=(destination,),
                                payload=payload)

        logger.debug("%s %s sending introduction request to %s", self.cid.encode("HEX"), type(self), destination)

        self._dispersy._forward([request])
        return request

    def on_introduction_request(self, messages):
        super(SearchCommunity, self).on_introduction_request(messages)

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

    class SearchRequest(RandomNumberCache):

        def __init__(self, request_cache, keywords, callback):
            super(SearchCommunity.SearchRequest, self).__init__(request_cache, u"search")
            self.keywords = keywords
            self.callback = callback

        @property
        def timeout_delay(self):
            return 30.0

        def on_timeout(self):
            pass

    def create_search(self, keywords, callback):
        candidates = self.get_connections()
        if len(candidates) > 0:
            if DEBUG:
                self._logger.debug("SearchCommunity: sending search request for %s to %s", keywords, map(str, candidates))

            # register callback/fetch identifier
            cache = self._request_cache.add(SearchCommunity.SearchRequest(self._request_cache, keywords, callback))

            # create search request message
            meta = self.get_meta_message(u"search-request")
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(cache.number, keywords))

            self._dispersy._send(candidates, [message])

        return len(candidates)

    def check_search(self, messages):
        return messages

    def on_search(self, messages):
        for message in messages:
            keywords = message.payload.keywords

            if DEBUG:
                self._logger.debug("SearchCommunity: got search request for %s", keywords)

            if self.log_incomming_searches:
                self.log_incomming_searches(message.candidate.sock_addr, keywords)

            results = []
            dbresults = self._torrent_db.searchNames(keywords, local=False, keys=['infohash', 'T.name', 'T.length', 'T.num_files', 'T.category_id', 'T.creation_date', 'T.num_seeders', 'T.num_leechers', 'swift_hash', 'swift_torrent_hash'])
            if len(dbresults) > 0:
                for dbresult in dbresults:
                    channel_details = dbresult[-10:]

                    dbresult = list(dbresult[:10])
                    dbresult[2] = long(dbresult[2])
                    dbresult[3] = int(dbresult[3])
                    dbresult[4] = [self._misc_db.categoryId2Name(dbresult[4]), ]
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
                self._logger.debug("SearchCommunity: no results")

            self._create_search_response(message.payload.identifier, results, message.candidate)

    def _create_search_response(self, identifier, results, candidate):
        # create search-response message
        meta = self.get_meta_message(u"search-response")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), destination=(candidate,), payload=(identifier, results))
        self._dispersy._forward([message])

        if DEBUG:
            self._logger.debug("SearchCommunity: returning %s results to %s", len(results), candidate)

    def check_search_response(self, messages):
        return messages

    def on_search_response(self, messages):
        # _get_channel_community could cause multiple commits, using this with clause this is reduced to only one.
        with self._dispersy.database:
            for message in messages:
                # fetch callback using identifier
                search_request = self._request_cache.get(u"search", message.payload.identifier)
                if search_request:
                    if DEBUG:
                        self._logger.debug("SearchCommunity: got search response for %s %s %s", search_request.keywords, len(message.payload.results), message.candidate)

                    if len(message.payload.results) > 0:
                        self._torrent_db.on_search_response(message.payload.results)

                    search_request.callback(search_request.keywords, message.payload.results, message.candidate)

                    # see if we need to join some channels
                    channels = set([result[10] for result in message.payload.results if result[10]])
                    if channels:
                        channels = self._get_unknown_channels(channels)

                        if DEBUG:
                            self._logger.debug("SearchCommunity: joining %d preview communities" % len(channels))

                        for cid in channels:
                            community = self._get_channel_community(cid)
                            community.disp_create_missing_channel(message.candidate, includeSnapshot=False)
                else:
                    if DEBUG:
                        self._logger.debug("SearchCommunity: got search response identifier not found %s", message.payload.identifier)

            # ensure that no commits occur
            raise IgnoreCommits()

    def create_torrent_request(self, infohash, candidate):
        torrentdict = {}
        torrentdict[self._master_member.mid] = set([infohash, ])

        # create torrent-request message
        meta = self.get_meta_message(u"torrent-request")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), destination=(candidate,), payload=(torrentdict,))
        self._dispersy._forward([message])

        if DEBUG:
            nr_requests = sum([len(cid_torrents) for cid_torrents in torrentdict.values()])
            self._logger.debug("SearchCommunity: requesting %s TorrentMessages from %s", nr_requests, candidate)

    def check_torrent_request(self, messages):
        return messages

    def on_torrent_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                requested_packets.extend(self._get_packets_from_infohashes(cid, torrents))

            if requested_packets:
                self._dispersy._send_packets([message.candidate], requested_packets,
                    self, "-caused by on-torrent-request-")

            if DEBUG:
                self._logger.debug("SearchCommunity: got request for %s torrents from %s", len(requested_packets), message.candidate)

    class PingRequestCache(RandomNumberCache):

        def __init__(self, community, candidate):
            super(SearchCommunity.PingRequestCache, self).__init__(community._request_cache, u"ping")

            self._logger = logging.getLogger(self.__class__.__name__)
            self.community = community
            self.candidate = candidate

        @property
        def timeout_delay(self):
            # we will accept the response at most 10.5 seconds after our request
            return 10.5

        def on_timeout(self):
            refreshIf = time() - CANDIDATE_WALK_LIFETIME
            remove = None
            for taste_buddy in self.community.taste_buddies:
                if taste_buddy[2] == self.candidate:
                    if taste_buddy[1] < refreshIf:
                        remove = taste_buddy
                    break

            if remove:
                self._logger.debug("SearchCommunity: no response on ping, removing from taste_buddies %s", self.candidate)
                self.community.taste_buddies.remove(remove)

    def create_torrent_collect_requests(self):
        refreshIf = time() - CANDIDATE_WALK_LIFETIME
        # determine to which peers we need to send a ping
        candidates = [candidate for _, prev, candidate in self.taste_buddies if prev < refreshIf]
        self._create_torrent_collect_requests(candidates)




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
                pong_request = self._request_cache.pop(u"ping", message.payload.identifier)
                logger.debug("pop %s", pong_request.candidate if pong_request else "unknown")
            else:
                logger.debug("no-pop")
                pong_request = True

            if pong_request and message.payload.hashtype == SWIFT_INFOHASHES:
                for swift_torrent_hash, infohash, seeders, leechers, ago in message.payload.torrents:
                    toInsert[infohash] = [infohash, swift_torrent_hash]
                    toPopularity[infohash] = [seeders, leechers, time() - (ago * 60)]
                    toCollect.setdefault(infohash, []).append(message.candidate)

        if len(toInsert) > 0:
            toInsert = toInsert.values()
            while toInsert:
                self._torrent_db.on_torrent_collect_response(toInsert[:50])
                toInsert = toInsert[50:]

        hashes = [hash_ for hash_ in toCollect.keys() if hash_]
        if hashes:
            hashesToCollect = self._torrent_db.selectSwiftTorrentsToCollect(hashes)
            for infohash, roothash in hashesToCollect[:5]:
                for candidate in toCollect[infohash]:
                    if DEBUG:
                        from Tribler.Core.CacheDB.sqlitecachedb import bin2str
                        self._logger.debug("SearchCommunity: requesting .torrent after receiving ping/pong %s %s %s", candidate, bin2str(infohash), bin2str(roothash))

                    # low_prio changes, hence we need to import it here
                    from Tribler.Core.RemoteTorrentHandler import LOW_PRIO_COLLECTING
                    self._rtorrent_handler.download_torrent(candidate, infohash, roothash, prio=LOW_PRIO_COLLECTING, timeout=CANDIDATE_WALK_LIFETIME)

    def _create_pingpong(self, meta_name, candidates, identifiers=None):
        max_len = self.dispersy_sync_bloom_filter_bits / 8
        limit = int(max_len / 44)

        torrents = self.__get_torrents(limit)
        for index, candidate in enumerate(candidates):
            if identifiers:
                identifier = identifiers[index]
            else:
                cache = self._request_cache.add(SearchCommunity.PingRequestCache(self, candidate))
                identifier = cache.number

            # create torrent-collect-request/response message
            meta = self.get_meta_message(meta_name)
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), destination=(candidate,), payload=(identifier, SWIFT_INFOHASHES, torrents))

            self._dispersy._forward([message])
            self._logger.debug("SearchCommunity: send %s to %s", meta_name, candidate)

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
        self._torrent_db.updateTorrent(infohash, notify=False, dispersy_id=message.packet_id)
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
        known_cids = self._channelcast_db._db.fetchall(u"SELECT dispersy_cid FROM Channels WHERE dispersy_cid in (" + parameters + ")", map(buffer, cids))
        known_cids = map(str, known_cids)
        return [cid for cid in cids if cid not in known_cids]

    def _get_channel_community(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        try:
            return self._dispersy.get_community(cid, True)
        except CommunityNotFoundException:
            logger.debug("join preview community %s", cid.encode("HEX"))
            return PreviewChannelCommunity.init_community(self._dispersy, self._dispersy.get_member(mid=cid), self._my_member, self.integrate_with_tribler)

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
