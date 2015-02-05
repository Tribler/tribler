# Written by Niels Zeilemaker
from random import shuffle
from time import time
from binascii import hexlify
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


DEBUG = False
CREATE_TORRENT_COLLECT_INTERVAL = 5


class SearchCommunity(Community):

    """
    A single community that all Tribler members join and use to disseminate .torrent files.
    """
    @classmethod
    def get_master_members(cls, dispersy):
# generated: Mon Nov 24 10:37:11 2014
# curve: NID_sect571r1
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b810400270381920004034a9031d07ed6d5d98b0a98cacd4bef2e19125ea7635927708babefa8e66deeb6cb4e78cc0efda39a581a679032a95ebc4a0fbdf913aa08af31f14753839b620cb5547c6e6cf42f03629b1b3dc199a3b1a262401c7ae615e87a1cf13109c7fb532f45c492ba927787257bf994e989a15fb16f20751649515fc58d87e0c861ca5b467a5c450bf57f145743d794057e75
# pub-sha1 fb04df93369587ec8fd9b74559186fa356cffda8
# -----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQDSpAx0H7W1dmLCpjKzUvvLhkSXqdj
# WSdwi6vvqOZt7rbLTnjMDv2jmlgaZ5AyqV68Sg+9+ROqCK8x8UdTg5tiDLVUfG5s
# 9C8DYpsbPcGZo7GiYkAceuYV6Hoc8TEJx/tTL0XEkrqSd4cle/mU6YmhX7FvIHUW
# SVFfxY2H4MhhyltGelxFC/V/FFdD15QFfnU=
# -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b810400270381920004034a9031d07ed6d5d98b0a98cacd4bef2e19125ea7635927708babefa8e66deeb6cb4e78cc0efda39a581a679032a95ebc4a0fbdf913aa08af31f14753839b620cb5547c6e6cf42f03629b1b3dc199a3b1a262401c7ae615e87a1cf13109c7fb532f45c492ba927787257bf994e989a15fb16f20751649515fc58d87e0c861ca5b467a5c450bf57f145743d794057e75".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def __init__(self, *args, **kwargs):
        super(SearchCommunity, self).__init__(*args, **kwargs)
        self.tribler_session = None
        self.integrate_with_tribler = None
        self.log_incomming_searches = None
        self.taste_buddies = []

        self._channelcast_db = None
        self._misc_db = None
        self._torrent_db = None
        self._mypref_db = None
        self._notifier = None

        self._rtorrent_handler = None

        self.taste_bloom_filter = None
        self.taste_bloom_filter_key = None

        self.torrent_cache = None

    def initialize(self, tribler_session=None, log_incomming_searches=False):
        self.tribler_session = tribler_session
        self.integrate_with_tribler = tribler_session is not None
        self.log_incomming_searches = log_incomming_searches

        super(SearchCommunity, self).initialize()
        # To always connect to a peer uncomment/modify the following line
        # self.taste_buddies.append([1, time(), Candidate(("127.0.0.1", 1234), False))

        if self.integrate_with_tribler:
            from Tribler.Core.simpledefs import NTFY_MISC, NTFY_CHANNELCAST, NTFY_TORRENTS, NTFY_MYPREFERENCES
            from Tribler.Core.CacheDB.Notifier import Notifier

            # tribler channelcast database
            self._channelcast_db = tribler_session.open_dbhandler(NTFY_CHANNELCAST)
            self._misc_db = tribler_session.open_dbhandler(NTFY_MISC)
            self._torrent_db = tribler_session.open_dbhandler(NTFY_TORRENTS)
            self._mypref_db = tribler_session.open_dbhandler(NTFY_MYPREFERENCES)
            self._notifier = Notifier.getInstance()

            # torrent collecting
            self._rtorrent_handler = RemoteTorrentHandler.getInstance()
        else:
            self._channelcast_db = ChannelCastDBStub(self._dispersy)
            self._torrent_db = None
            self._mypref_db = None
            self._notifier = None

        self.register_task(u"create torrent collect requests",
                           LoopingCall(self.create_torrent_collect_requests)).start(CREATE_TORRENT_COLLECT_INTERVAL,
                                                                                    now=True)

    def initiate_meta_messages(self):
        return super(SearchCommunity, self).initiate_meta_messages() + [
            Message(self, u"search-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    SearchRequestPayload(),
                    self._generic_timeline_check,
                    self.on_search),
            Message(self, u"search-response",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    SearchResponsePayload(),
                    self._generic_timeline_check,
                    self.on_search_response),
            Message(self, u"torrent-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TorrentRequestPayload(),
                    self._generic_timeline_check,
                    self.on_torrent_request),
            Message(self, u"torrent-collect-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TorrentCollectRequestPayload(),
                    self._generic_timeline_check,
                    self.on_torrent_collect_request),
            Message(self, u"torrent-collect-response",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TorrentCollectResponsePayload(),
                    self._generic_timeline_check,
                    self.on_torrent_collect_response),
            Message(self, u"torrent",
                    MemberAuthentication(),
                    PublicResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=128),
                    CommunityDestination(node_count=0),
                    TorrentPayload(),
                    self._generic_timeline_check,
                    self.on_torrent),
        ]

    def _initialize_meta_messages(self):
        super(SearchCommunity, self)._initialize_meta_messages()

        ori = self._meta_messages[u"dispersy-introduction-request"]
        new = Message(self, ori.name, ori.authentication, ori.resolution, ori.distribution, ori.destination, TasteIntroPayload(), ori.check_callback, ori.handle_callback)
        self._meta_messages[u"dispersy-introduction-request"] = new

    def initiate_conversions(self):
        return [DefaultConversion(self), SearchConversion(self)]

    @property
    def dispersy_enable_fast_candidate_walker(self):
        return self.integrate_with_tribler

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
            self.create_torrent_collect_requests([tb_tuple[-1] for tb_tuple in new_taste_buddies])

    def get_nr_connections(self):
        return len(self.get_connections())

    def get_connections(self):
        # add 10 taste buddies and 20 - len(taste_buddies) to candidates
        candidates = set(candidate for _, _, candidate in self.taste_buddies)
        sock_addresses = set(candidate.sock_addr for _, _, candidate in self.taste_buddies)

        for candidate in self.dispersy_yield_verified_candidates():
            if candidate.sock_addr not in sock_addresses:
                candidates.add(candidate)
                sock_addresses.add(candidate.sock_addr)

            if len(candidates) == 20:
                break
        return candidates

    def __calc_similarity(self, candidate, myPrefs, hisPrefs, overlap):
        if myPrefs > 0 and hisPrefs > 0:
            my_root = 1.0 / (myPrefs ** .5)
            sim = overlap * (my_root * (1.0 / (hisPrefs ** .5)))
            return [sim, time(), candidate]

        return [0, time(), candidate]

    def create_introduction_request(self, destination, allow_sync, is_fast_walker=False):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        if DEBUG:
            self._logger.debug(u"SearchCommunity: sending introduction request to %s", destination)

        advice = True
        if not is_fast_walker:
            my_preferences = sorted(self._mypref_db.getMyPrefListInfohash(limit=500))
            num_preferences = len(my_preferences)

            my_pref_key = u",".join(map(bin2str, my_preferences))
            if my_pref_key != self.taste_bloom_filter_key:
                if num_preferences > 0:
                    # no prefix changing, we want false positives (make sure it is a single char)
                    self.taste_bloom_filter = BloomFilter(0.005, len(my_preferences), prefix=' ')
                    self.taste_bloom_filter.add_keys(my_preferences)
                else:
                    self.taste_bloom_filter = None

                self.taste_bloom_filter_key = my_pref_key

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

        self._logger.debug(u"%s %s sending introduction request to %s", self.cid.encode("HEX"), type(self), destination)

        self._dispersy._forward([request])
        return request

    def on_introduction_request(self, messages):
        super(SearchCommunity, self).on_introduction_request(messages)

        if any(message.payload.taste_bloom_filter for message in messages):
            my_preferences = self._mypref_db.getMyPrefListInfohash(limit=500)
        else:
            my_preferences = []

        new_taste_buddies = []
        for message in messages:
            taste_bloom_filter = message.payload.taste_bloom_filter
            num_preferences = message.payload.num_preferences
            if taste_bloom_filter:
                overlap = sum(infohash in taste_bloom_filter for infohash in my_preferences)
            else:
                overlap = 0

            new_taste_buddies.append(self.__calc_similarity(message.candidate, len(my_preferences), num_preferences, overlap))

        if len(new_taste_buddies) > 0:
            self.add_taste_buddies(new_taste_buddies)

        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET,
                                      "%s:%d" % message.candidate.sock_addr)

    class SearchRequest(RandomNumberCache):

        def __init__(self, request_cache, keywords):
            super(SearchCommunity.SearchRequest, self).__init__(request_cache, u"search")
            self.keywords = keywords

        @property
        def timeout_delay(self):
            return 30.0

        def on_timeout(self):
            pass

    def create_search(self, keywords):
        candidates = self.get_connections()
        if len(candidates) > 0:
            if DEBUG:
                self._logger.debug(u"sending search request for %s to %s", keywords, map(str, candidates))

            # register callback/fetch identifier
            cache = self._request_cache.add(SearchCommunity.SearchRequest(self._request_cache, keywords))

            # create search request message
            meta = self.get_meta_message(u"search-request")
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(cache.number, keywords))

            self._dispersy._send(candidates, [message])

        return len(candidates)

    def on_search(self, messages):
        for message in messages:
            keywords = message.payload.keywords

            if DEBUG:
                self._logger.debug(u"got search request for %s", keywords)

            if self.log_incomming_searches:
                self.log_incomming_searches(message.candidate.sock_addr, keywords)

            results = []
            dbresults = self._torrent_db.searchNames(keywords, local=False, keys=['infohash', 'T.name', 'T.length', 'T.num_files', 'T.category_id', 'T.creation_date', 'T.num_seeders', 'T.num_leechers'])
            if len(dbresults) > 0:
                for dbresult in dbresults:
                    channel_details = dbresult[-10:]

                    dbresult = list(dbresult[:8])
                    dbresult[2] = long(dbresult[2])  # length
                    dbresult[3] = int(dbresult[3])  # num_files
                    dbresult[4] = [self._misc_db.categoryId2Name(dbresult[4]), ]  # category_keys
                    dbresult[5] = long(dbresult[5])  # creation_date
                    dbresult[6] = int(dbresult[6] or 0)  # num_seeders
                    dbresult[7] = int(dbresult[7] or 0)  # num_leechers

                    # cid
                    if channel_details[1]:
                        channel_details[1] = str(channel_details[1])
                    dbresult.append(channel_details[1])

                    results.append(tuple(dbresult))
            elif DEBUG:
                self._logger.debug(u"no results")

            self._create_search_response(message.payload.identifier, results, message.candidate)

    def _create_search_response(self, identifier, results, candidate):
        # create search-response message
        meta = self.get_meta_message(u"search-response")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), destination=(candidate,), payload=(identifier, results))
        self._dispersy._forward([message])

        if DEBUG:
            self._logger.debug(u"returning %s results to %s", len(results), candidate)

    def on_search_response(self, messages):
        # _get_channel_community could cause multiple commits, using this with clause this is reduced to only one.
        with self._dispersy.database:
            for message in messages:
                # fetch callback using identifier
                search_request = self._request_cache.get(u"search", message.payload.identifier)
                if search_request:
                    if DEBUG:
                        self._logger.debug(u"SearchCommunity: got search response for %s %s %s",
                                           search_request.keywords, len(message.payload.results), message.candidate)

                    if len(message.payload.results) > 0:
                        self._torrent_db.on_search_response(message.payload.results)

                    # emit signal of search results
                    if self.tribler_session is not None:
                        from Tribler.Core.simpledefs import SIGNAL_SEARCH_COMMUNITY, SIGNAL_ONSEARCHRESULTS
                        search_results = {'keywords': search_request.keywords,
                                          'results': message.payload.results,
                                          'candidate': message.candidate}
                        self.tribler_session.uch.notify(SIGNAL_SEARCH_COMMUNITY, SIGNAL_ONSEARCHRESULTS, None,
                                                        search_results)

                    # see if we need to join some channels
                    channels = set([result[8] for result in message.payload.results if result[8]])
                    if channels:
                        channels = self._get_unknown_channels(channels)

                        if DEBUG:
                            self._logger.debug(u"SearchCommunity: joining %d preview communities", len(channels))

                        for cid in channels:
                            community = self._get_channel_community(cid)
                            community.disp_create_missing_channel(message.candidate, includeSnapshot=False)
                else:
                    if DEBUG:
                        self._logger.debug(u"SearchCommunity: got search response identifier not found %s",
                                           message.payload.identifier)

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
            self._logger.debug(u"requesting %s TorrentMessages from %s", nr_requests, candidate)

    def on_torrent_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                requested_packets.extend(self._get_packets_from_infohashes(cid, torrents))

            if requested_packets:
                self._dispersy._send_packets([message.candidate], requested_packets,
                                             self, u"-caused by on-torrent-request-")

            if DEBUG:
                self._logger.debug(u"got request for %s torrents from %s", len(requested_packets), message.candidate)

    class PingRequestCache(RandomNumberCache):

        def __init__(self, community, candidate):
            super(SearchCommunity.PingRequestCache, self).__init__(community._request_cache, u"ping")

            self.community = community
            self.candidate = candidate

        @property
        def timeout_delay(self):
            return 10.5

        def on_timeout(self):
            refresh_if = time() - CANDIDATE_WALK_LIFETIME
            remove = None
            for taste_buddy in self.community.taste_buddies:
                if taste_buddy[2] == self.candidate:
                    if taste_buddy[1] < refresh_if:
                        remove = taste_buddy
                    break

            if remove:
                self.community.taste_buddies.remove(remove)

    def create_torrent_collect_requests(self, candidates=None):
        if candidates is None:
            refresh_if = time() - CANDIDATE_WALK_LIFETIME
            # determine to which peers we need to send a ping
            candidates = [candidate for _, prev, candidate in self.taste_buddies if prev < refresh_if]

        if len(candidates) > 0:
            self._create_pingpong(u"torrent-collect-request", candidates)

    def on_torrent_collect_request(self, messages):
        candidates = [message.candidate for message in messages]
        identifiers = [message.payload.identifier for message in messages]

        self._create_pingpong(u"torrent-collect-response", candidates, identifiers)
        self._process_collect_request_response(messages)

    def on_torrent_collect_response(self, messages):
        self._process_collect_request_response(messages)

    def _process_collect_request_response(self, messages):
        to_insert_list = []
        to_collect_dict = {}
        to_popularity_dict = {}
        for message in messages:
            # check if the identifier is still in the request_cache because it could have timed out
            if not self.request_cache.has(u"ping", message.payload.identifier):
                self._logger.warn(u"message from %s cannot be found in the request cache, skipping it",
                                  message.candidate)
                continue
            self.request_cache.pop(u"ping", message.payload.identifier)

            for infohash, seeders, leechers, ago in message.payload.torrents:
                if not infohash:
                    continue
                elif infohash not in to_insert_list:
                    to_insert_list.append(infohash)
                to_popularity_dict[infohash] = [seeders, leechers, time() - (ago * 60)]
                to_collect_dict.setdefault(infohash, []).append(message.candidate)

        if len(to_insert_list) > 0:
            while to_insert_list:
                self._torrent_db.on_torrent_collect_response(to_insert_list[:50])
                to_insert_list = to_insert_list[50:]

        infohashes = [infohash_ for infohash_ in to_collect_dict if infohash_]
        if infohashes:
            infohashes_to_collect = self._torrent_db.select_torrents_to_collect(infohashes)
            for infohash in infohashes_to_collect[:5]:
                for candidate in to_collect_dict[infohash]:
                    self._logger.debug(u"requesting .torrent after receiving ping/pong %s %s",
                                       candidate, hexlify(infohash))

                    # low_prio changes, hence we need to import it here
                    from Tribler.Core.RemoteTorrentHandler import LOW_PRIO_COLLECTING
                    self._rtorrent_handler.download_torrent(candidate, infohash, priority=LOW_PRIO_COLLECTING,
                                                            timeout=CANDIDATE_WALK_LIFETIME)

        sock_addrs = [message.candidate.sock_addr for message in messages]
        for taste_buddy in self.taste_buddies:
            if taste_buddy[2].sock_addr in sock_addrs:
                taste_buddy[1] = time()

    def _create_pingpong(self, meta_name, candidates, identifiers=None):
        max_len = self.dispersy_sync_bloom_filter_bits / 8
        torrents = self.__get_torrents(int(max_len / 44))
        for index, candidate in enumerate(candidates):
            if identifiers:
                identifier = identifiers[index]
            else:
                cache = self._request_cache.add(SearchCommunity.PingRequestCache(self, candidate))
                identifier = cache.number

            # create torrent-collect-request/response message
            meta = self.get_meta_message(meta_name)
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), destination=(candidate,),
                                payload=(identifier, torrents))

            self._dispersy._forward([message])
            self._logger.debug(u"send %s to %s", meta_name, candidate)

    def __get_torrents(self, limit):
        cache_timeout = CANDIDATE_WALK_LIFETIME
        if self.torrent_cache and self.torrent_cache[0] > (time() - cache_timeout):
            return self.torrent_cache[1]

        # we want roughly 1/3 random, 2/3 recent
        limit_recent = int(limit * 0.66)
        limit_random = limit - limit_recent

        torrents = self._torrent_db.getRecentlyCollectedTorrents(limit=limit_recent) or []
        if len(torrents) == limit_recent:
            # index 4 is insert_time
            least_recent = torrents[-1][4]
            random_torrents = self._torrent_db.getRandomlyCollectedTorrents(least_recent, limit=limit_random) or []
        else:
            random_torrents = []

        torrents = [[tor[0], tor[1], tor[2], tor[3]] for tor in torrents]
        random_torrents = [[tor[0], tor[1], tor[2], tor[3]] for tor in random_torrents]

        # combine random and recent + shuffle to obscure categories
        torrents = torrents + random_torrents
        shuffle(torrents)

        # fix leechers, seeders to max 2**16 (shift values +2 to accomodate -2 and -1 values)
        max_value = (2 ** 16) - 1
        for torrent in torrents:
            # index 1 and 2 are num_seeders and num_leechers respectively
            torrent[1] = min(max_value, (torrent[1] or -1) + 2)
            torrent[2] = min(max_value, (torrent[2] or -1) + 2)

            # index 3 is last_tracker_check, convert to minutes
            torrent[3] /= 60
            if torrent[3] > max_value or torrent[3] < 0:
                torrent[3] = max_value

        self.torrent_cache = (time(), torrents)
        return torrents

    def create_torrent(self, infohash, store=True, update=True, forward=True):
        torrent_data = self.tribler_session.get_collected_torrent(infohash)
        if torrent_data is not None:
            try:
                torrentdef = TorrentDef.load_from_memory(torrent_data)
                files = torrentdef.get_files_as_unicode_with_length()

                meta = self.get_meta_message(u"torrent")
                message = meta.impl(authentication=(self._my_member,),
                                    distribution=(self.claim_global_time(),),
                                    payload=(torrentdef.get_infohash(), long(time()), torrentdef.get_name_as_unicode(),
                                             tuple(files), torrentdef.get_trackers_as_single_tuple()))

                self._dispersy.store_update_forward([message], store, update, forward)
                self._torrent_db.updateTorrent(torrentdef.get_infohash(), notify=False, dispersy_id=message.packet_id)

                return message
            except ValueError:
                pass
            except:
                print_exc()
        return False

    def on_torrent(self, messages):
        for message in messages:
            self._torrent_db.addExternalTorrentNoDef(message.payload.infohash, message.payload.name, message.payload.files, message.payload.trackers, message.payload.timestamp, {'dispersy_id': message.packet_id})

    def _get_channel_id(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        return self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(cid),))

    def _get_unknown_channels(self, cids):
        assert all(isinstance(cid, str) for cid in cids)
        assert all(len(cid) == 20 for cid in cids)

        parameters = u",".join(["?"] * len(cids))
        known_cids = self._channelcast_db._db.fetchall(u"SELECT dispersy_cid FROM Channels WHERE dispersy_cid in (" + parameters + u")", map(buffer, cids))
        known_cids = map(str, known_cids)
        return [cid for cid in cids if cid not in known_cids]

    def _get_channel_community(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        try:
            return self._dispersy.get_community(cid, True)
        except CommunityNotFoundException:
            self._logger.debug(u"join preview community %s", cid.encode("HEX"))
            return PreviewChannelCommunity.init_community(self._dispersy, self._dispersy.get_member(mid=cid),
                                                          self._my_member, tribler_session=self.tribler_session)

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
                torrent = self._torrent_db.getTorrent(infohash, ['dispersy_id'], include_mypref=False)
                if torrent:
                    dispersy_id = torrent['dispersy_id']

                    # 2. if still not found, create a new torrentmessage and return this one
                    if not dispersy_id:
                        message = self.create_torrent(infohash, store=True, update=False, forward=False)
                        if message:
                            packets.append(message.packet)
            add_packet(dispersy_id)
        return packets

    def _get_packet_from_dispersy_id(self, dispersy_id, messagename):
        # 1. get the packet
        try:
            packet, _ = self._dispersy.database.execute(u"SELECT sync.packet, sync.id FROM community JOIN sync ON sync.community = community.id WHERE sync.id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError(u"Unknown dispersy_id")

        return str(packet)


class ChannelCastDBStub(object):

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
