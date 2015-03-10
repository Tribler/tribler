from random import sample
from time import time

from twisted.internet.task import LoopingCall
from twisted.python.threadable import isInIOThread

from .conversion import AllChannelConversion
from Tribler.community.allchannel.message import DelayMessageReqChannelMessage
from Tribler.community.allchannel.payload import (ChannelCastRequestPayload, ChannelCastPayload, VoteCastPayload,
                                                  ChannelSearchPayload, ChannelSearchResponsePayload)
from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.database import IgnoreCommits
from Tribler.dispersy.destination import CandidateDestination, CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.dispersy.exception import CommunityNotFoundException
from Tribler.dispersy.message import Message, BatchConfiguration
from Tribler.dispersy.resolution import PublicResolution


CHANNELCAST_FIRST_MESSAGE = 3.0
CHANNELCAST_INTERVAL = 15.0
CHANNELCAST_BLOCK_PERIOD = 10.0 * 60.0  # block for 10 minutes
UNLOAD_COMMUNITY_INTERVAL = 60.0

DEBUG = False


class AllChannelCommunity(Community):

    """
    A single community that all Tribler members join and use to disseminate .torrent files.

    The dissemination of .torrent files, using 'community-propagate' messages, is NOT done using a
    dispersy sync mechanism.  We prefer more specific dissemination mechanism than dispersy
    provides.  Dissemination occurs by periodically sending:

     - N most recently received .torrent files
     - M random .torrent files
     - O most recent .torrent files, created by ourselves
     - P randomly choosen .torrent files, created by ourselves
    """
    @classmethod
    def get_master_members(cls, dispersy):
# generated: Fri Nov 25 10:51:27 2011
# curve: high <<< NID_sect571r1 >>>
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000405548a13626683d4788ab19393fa15c9e9d6f5ce0ff47737747fa511af6c4e956f523dc3d1ae8d7b83b850f21ab157dd4320331e2f136aa01e70d8c96df665acd653725e767da9b5079f25cebea808832cd16015815797906e90753d135ed2d796b9dfbafaf1eae2ebea3b8846716c15814e96b93ae0f5ffaec44129688a38ea35f879205fdbe117323e73076561f112
# pub-sha1 8164f55c2f828738fa779570e4605a81fec95c9d
# -----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQFVIoTYmaD1HiKsZOT+hXJ6db1zg/0
# dzd0f6URr2xOlW9SPcPRro17g7hQ8hqxV91DIDMeLxNqoB5w2Mlt9mWs1lNyXnZ9
# qbUHnyXOvqgIgyzRYBWBV5eQbpB1PRNe0teWud+6+vHq4uvqO4hGcWwVgU6WuTrg
# 9f+uxEEpaIo46jX4eSBf2+EXMj5zB2Vh8RI=
# -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000405548a13626683d4788ab19393fa15c9e9d6f5ce0ff47737747fa511af6c4e956f523dc3d1ae8d7b83b850f21ab157dd4320331e2f136aa01e70d8c96df665acd653725e767da9b5079f25cebea808832cd16015815797906e90753d135ed2d796b9dfbafaf1eae2ebea3b8846716c15814e96b93ae0f5ffaec44129688a38ea35f879205fdbe117323e73076561f112".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    @property
    def dispersy_sync_bloom_filter_strategy(self):
        return self._dispersy_claim_sync_bloom_filter_modulo

    def initiate_meta_messages(self):
        batch_delay = 1.0

        return super(AllChannelCommunity, self).initiate_meta_messages() + [
            Message(self, u"channelcast",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    ChannelCastPayload(),
                    self.check_channelcast,
                    self.on_channelcast),
            Message(self, u"channelcast-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    ChannelCastRequestPayload(),
                    self.check_channelcast_request,
                    self.on_channelcast_request),
            Message(self, u"channelsearch",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    ChannelSearchPayload(),
                    self.check_channelsearch,
                    self.on_channelsearch),
            Message(self, u"channelsearch-response",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    ChannelSearchResponsePayload(),
                    self.check_channelsearch_response,
                    self.on_channelsearch_response),
            Message(self, u"votecast",
                    MemberAuthentication(),
                    PublicResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    VoteCastPayload(),
                    self.check_votecast,
                    self.on_votecast,
                    self.undo_votecast,
                    batch=BatchConfiguration(max_window=batch_delay))
        ]

    def __init__(self, *args, **kwargs):
        super(AllChannelCommunity, self).__init__(*args, **kwargs)

        self._blocklist = {}
        self._recentlyRequested = []

        self.tribler_session = None
        self.auto_join_channel = None

        self._channelcast_db = None
        self._votecast_db = None
        self._peer_db = None

    def initialize(self, tribler_session=None, auto_join_channel=False):
        super(AllChannelCommunity, self).initialize()

        self.tribler_session = tribler_session
        self.auto_join_channel = auto_join_channel

        if tribler_session is not None:
            from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_VOTECAST, NTFY_PEERS

            # tribler channelcast database
            self._channelcast_db = tribler_session.open_dbhandler(NTFY_CHANNELCAST)
            self._votecast_db = tribler_session.open_dbhandler(NTFY_VOTECAST)
            self._peer_db = tribler_session.open_dbhandler(NTFY_PEERS)

        else:
            self._channelcast_db = ChannelCastDBStub(self._dispersy)
            self._votecast_db = VoteCastDBStub(self._dispersy)
            self._peer_db = PeerDBStub(self._dispersy)

        self.register_task(u"channelcast",
                           LoopingCall(self.create_channelcast)).start(CHANNELCAST_FIRST_MESSAGE, now=True)

        self.register_task(u"unload preview",
                           LoopingCall(self.unload_preview)).start(UNLOAD_COMMUNITY_INTERVAL, now=False)

    def initiate_conversions(self):
        return [DefaultConversion(self), AllChannelConversion(self)]

    @property
    def dispersy_auto_download_master_member(self):
        # there is no dispersy-identity for the master member, so don't try to download
        return False

    @property
    def dispersy_sync_response_limit(self):
        return 25 * 1024

    def create_channelcast(self):
        assert isInIOThread()
        now = time()

        favoriteTorrents = None
        normalTorrents = None

        # cleanup blocklist
        for candidate in self._blocklist.keys():
            if self._blocklist[candidate] + CHANNELCAST_BLOCK_PERIOD < now:  # unblock address
                self._blocklist.pop(candidate)

        mychannel_id = self._channelcast_db.getMyChannelId()

        # loop through all candidates to see if we can find a non-blocked address
        for candidate in [candidate for candidate in self._iter_categories([u'walk', u'stumble'], once=True) if candidate not in self._blocklist]:
            if not candidate:
                continue

            didFavorite = False
            # only check if we actually have a channel
            if mychannel_id:
                peer_ids = set()
                key = candidate.get_member().public_key
                peer_ids.add(self._peer_db.addOrGetPeerID(key))

                # see if all members on this address are subscribed to my channel
                didFavorite = len(peer_ids) > 0
                for peer_id in peer_ids:
                    vote = self._votecast_db.getVoteForMyChannel(peer_id)
                    if vote != 2:
                        didFavorite = False
                        break

            # Modify type of message depending on if all peers have marked my channels as their favorite
            if didFavorite:
                if not favoriteTorrents:
                    favoriteTorrents = self._channelcast_db.getRecentAndRandomTorrents(0, 0, 25, 25, 5)
                torrents = favoriteTorrents
            else:
                if not normalTorrents:
                    normalTorrents = self._channelcast_db.getRecentAndRandomTorrents()
                torrents = normalTorrents

            if len(torrents) > 0:
                meta = self.get_meta_message(u"channelcast")
                message = meta.impl(authentication=(self._my_member,),
                                    distribution=(self.global_time,), destination=(candidate,), payload=(torrents,))

                self._dispersy._forward([message])

                # we've send something to this address, add to blocklist
                self._blocklist[candidate] = now

                nr_torrents = sum(len(torrent) for torrent in torrents.values())
                self._logger.debug("sending channelcast message containing %s torrents to %s didFavorite %s",
                                   nr_torrents, candidate.sock_addr, didFavorite)
                # we're done
                break

        else:
            self._logger.debug("Did not send channelcast messages, no candidates or torrents")

    def get_nr_connections(self):
        return len(list(self.dispersy_yield_candidates()))

    def check_channelcast(self, messages):
        with self._dispersy.database:
            for message in messages:
                for cid in message.payload.torrents.iterkeys():
                    channel_id = self._get_channel_id(cid)
                    if not channel_id:
                        community = self._get_channel_community(cid)
                        yield DelayMessageReqChannelMessage(message, community, includeSnapshot=True)
                        break
                else:
                    yield message

            # ensure that no commits occur
            raise IgnoreCommits()

    def on_channelcast(self, messages):
        for message in messages:
            toCollect = {}
            for cid, torrents in message.payload.torrents.iteritems():
                for infohash in self._selectTorrentsToCollect(cid, torrents):
                    toCollect.setdefault(cid, set()).add(infohash)

            nr_requests = sum([len(torrents) for torrents in toCollect.values()])
            if nr_requests > 0:
                self.create_channelcast_request(toCollect, message.candidate)

    def create_channelcast_request(self, toCollect, candidate):
        # create channelcast request message
        meta = self.get_meta_message(u"channelcast-request")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), destination=(candidate,), payload=(toCollect,))
        self._dispersy._forward([message])

        nr_requests = sum([len(torrents) for torrents in toCollect.values()])
        self._logger.debug("requesting %s torrents from %s", nr_requests, candidate)

    def check_channelcast_request(self, messages):
        # no timeline check because PublicResolution policy is used
        return messages

    def on_channelcast_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                requested_packets.extend(self._get_packets_from_infohashes(cid, torrents))

            if requested_packets:
                self._dispersy._send_packets([message.candidate], requested_packets,
                                             self, "-caused by channelcast-request-")

            self._logger.debug("got request for %s torrents from %s", len(requested_packets), message.candidate)

    def create_channelsearch(self, keywords):
        # clear searchcallbacks if new search
        query = " ".join(keywords)

        meta = self.get_meta_message(u"channelsearch")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,),
                            payload=(keywords,))

        self._logger.debug("searching for channel matching '%s'", query)

        return self._dispersy._forward([message])

    def check_channelsearch(self, messages):
        # no timeline check because PublicResolution policy is used
        return messages

    def on_channelsearch(self, messages):
        for message in messages:
            keywords = message.payload.keywords
            query = " ".join(keywords)

            self._logger.debug("got search request for '%s'", query)

            results = self._channelcast_db.searchChannelsTorrent(query, 7, 7, dispersyOnly=True)
            if len(results) > 0:
                responsedict = {}
                for channel_id, dispersy_cid, name, infohash, torname, time_stamp in results:
                    infohashes = responsedict.setdefault(dispersy_cid, set())
                    infohashes.add(infohash)

                    self._logger.debug("found cid: %s infohash: %s", dispersy_cid.encode("HEX"), infohash.encode("HEX"))

                self.create_channelsearch_response(keywords, responsedict, message.candidate)

            else:
                self._logger.debug("no results")

    def create_channelsearch_response(self, keywords, torrents, candidate):
        # create channelsearch-response message
        meta = self.get_meta_message(u"channelsearch-response")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), destination=(candidate,), payload=(keywords, torrents))

        self._dispersy._forward([message])

        nr_requests = sum([len(tors) for tors in torrents.values()])
        self._logger.debug("sending %s results", nr_requests)

    def check_channelsearch_response(self, messages):
        with self._dispersy.database:
            for message in messages:
                for cid in message.payload.torrents.iterkeys():
                    channel_id = self._get_channel_id(cid)
                    if not channel_id:
                        community = self._get_channel_community(cid)
                        yield DelayMessageReqChannelMessage(message, community, includeSnapshot=True)
                        break
                else:
                    yield message

            # ensure that no commits occur
            raise IgnoreCommits()

    def on_channelsearch_response(self, messages):
        # request missing torrents
        self.on_channelcast(messages)

        for message in messages:
            # show results in gui
            keywords = message.payload.keywords
            query = " ".join(keywords)

            self._logger.debug("got search response for '%s'", query)

            # emit a results signal if integrated with Tribler
            if self.tribler_session is not None:
                from Tribler.Core.simpledefs import SIGNAL_ALLCHANNEL, SIGNAL_ON_SEARCH_RESULTS
                torrents = message.payload.torrents
                results = {'keywords': keywords,
                           'torrents': torrents}
                self.tribler_session.uch.notify(SIGNAL_ALLCHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results)

    def disp_create_votecast(self, cid, vote, timestamp, store=True, update=True, forward=True):
        # reclassify community
        if vote == 2:
            communityclass = ChannelCommunity
        else:
            communityclass = PreviewChannelCommunity

        community_old = self._get_channel_community(cid)
        community = self.dispersy.reclassify_community(community_old, communityclass)
        community._candidates = community_old._candidates

        # check if we need to cancel a previous vote
        latest_dispersy_id = self._votecast_db.get_latest_vote_dispersy_id(community._channel_id, None)
        if latest_dispersy_id:
            message = self._dispersy.load_message_by_packetid(self, latest_dispersy_id)
            if message:
                self.create_undo(message)

        # create new vote message
        meta = self.get_meta_message(u"votecast")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(cid, vote, timestamp))
        self._dispersy.store_update_forward([message], store, update, forward)

        return message

    def check_votecast(self, messages):
        with self._dispersy.database:
            communities = {}
            channel_ids = {}
            for cid in set([message.payload.cid for message in messages]):
                channel_id = self._get_channel_id(cid)
                if channel_id:
                    channel_ids[cid] = channel_id
                else:
                    communities[cid] = self._get_channel_community(cid)

            for message in messages:
                community = communities.get(message.payload.cid)
                if community:
                    # at this point we should NOT have the channel message for this community
                    if __debug__:
                        try:
                            self._dispersy.database.execute(
                                u"SELECT * FROM sync WHERE community = ? AND meta_message = ? AND undone = 0",
                                (community.database_id, community.get_meta_message(u"channel").database_id)).next()
                            self._logger.error("We already have the channel message... no need to wait for it %s",
                                               community.cid.encode("HEX"))
                        except StopIteration:
                            pass

                    self._logger.debug("Did not receive channel, requesting channel message '%s' from %s",
                                       community.cid.encode("HEX"), message.candidate.sock_addr)
                    # request torrents if positive vote
                    yield DelayMessageReqChannelMessage(message, community, includeSnapshot=message.payload.vote > 0)

                else:
                    message.channel_id = channel_ids[message.payload.cid]
                    yield message

            # ensure that no commits occur
            raise IgnoreCommits()

    def on_votecast(self, messages):
        if self.tribler_session is not None:
            votelist = []
            for message in messages:
                dispersy_id = message.packet_id
                channel_id = getattr(message, "channel_id", 0)

                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None

                    # if channel_id is not found, then this is a manual join
                    # insert placeholder into database which will be replaced after channelmessage has been received
                    if not channel_id:
                        select_channel = "SELECT id FROM _Channels WHERE dispersy_cid = ?"
                        channel_id = self._channelcast_db._db.fetchone(select_channel, (buffer(message.payload.cid),))

                        if not channel_id:
                            insert_channel = "INSERT INTO _Channels (dispersy_cid, peer_id, name) " \
                                             "VALUES (?, ?, ?); SELECT last_insert_rowid();"
                            channel_id = self._channelcast_db._db.fetchone(insert_channel,
                                                                           (buffer(message.payload.cid), -1, ''))
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

                votelist.append((channel_id, peer_id, dispersy_id, message.payload.vote, message.payload.timestamp))

            self._votecast_db.on_votes_from_dispersy(votelist)

    def undo_votecast(self, descriptors, redo=False):
        if self.tribler_session is not None:
            contains_my_vote = False
            votelist = []
            now = long(time())
            for _, _, packet in descriptors:
                message = packet.load_message()
                dispersy_id = message.packet_id

                channel_id = self._get_channel_id(message.payload.cid)
                votelist.append((None if redo else now, channel_id, dispersy_id))

                authentication_member = message.authentication.member
                my_vote = authentication_member == self._my_member
                if my_vote:
                    contains_my_vote = True

            self._votecast_db.on_remove_votes_from_dispersy(votelist, contains_my_vote)

    def _get_channel_community(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        try:
            return self._dispersy.get_community(cid, True)
        except CommunityNotFoundException:
            if self.auto_join_channel:
                self._logger.info("join channel community %s", cid.encode("HEX"))
                return ChannelCommunity.init_community(self._dispersy, self._dispersy.get_member(mid=cid),
                                                       self._my_member, tribler_session=self.tribler_session)
            else:
                self._logger.info("join preview community %s", cid.encode("HEX"))
                return PreviewChannelCommunity.init_community(self._dispersy, self._dispersy.get_member(mid=cid),
                                                              self._my_member, tribler_session=self.tribler_session)

    def unload_preview(self):
        cleanpoint = time() - 300
        inactive = [community for community in self.dispersy._communities.itervalues() if isinstance(
            community, PreviewChannelCommunity) and community.init_timestamp < cleanpoint]
        self._logger.debug("cleaning %d/%d previewchannel communities", len(inactive), len(self.dispersy._communities))

        for community in inactive:
            community.unload_community()

    def _get_channel_id(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        return self._channelcast_db.getChannelIdFromDispersyCID(buffer(cid))

    def _selectTorrentsToCollect(self, cid, infohashes):
        channel_id = self._get_channel_id(cid)

        row = self._channelcast_db.getCountMaxFromChannelId(channel_id)
        if row:
            nrTorrrents, latestUpdate = row
        else:
            nrTorrrents = 0
            latestUpdate = 0

        collect = []

        # filter infohashes using recentlyRequested
        infohashes = filter(lambda infohash: infohash not in self._recentlyRequested, infohashes)

        # only request updates if nrT < 100 or we have not received an update in the last half hour
        if nrTorrrents < 100 or latestUpdate < (time() - 1800):
            infohashes = list(infohashes)
            haveTorrents = self._channelcast_db.hasTorrents(channel_id, infohashes)
            for i in range(len(infohashes)):
                if not haveTorrents[i]:
                    collect.append(infohashes[i])

        self._recentlyRequested.extend(collect)
        self._recentlyRequested = self._recentlyRequested[:100]

        return collect

    def _get_packets_from_infohashes(self, cid, infohashes):
        assert all(isinstance(infohash, str) for infohash in infohashes)
        assert all(len(infohash) == 20 for infohash in infohashes)

        channel_id = self._get_channel_id(cid)

        packets = []
        for infohash in infohashes:
            dispersy_id = self._channelcast_db.getTorrentFromChannelId(
                channel_id, infohash, ['ChannelTorrents.dispersy_id'])

            if dispersy_id and dispersy_id > 0:
                try:
                    # 2. get the message
                    packets.append(self._get_packet_from_dispersy_id(dispersy_id, "torrent"))
                except RuntimeError:
                    pass

        return packets

    def _get_packet_from_dispersy_id(self, dispersy_id, messagename):
        try:
            packet, = self._dispersy.database.execute(
                u"SELECT sync.packet FROM community JOIN sync ON sync.community = community.id WHERE sync.id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError("Unknown dispersy_id")
        return str(packet)

    def _drop_all_newer(self, dispersy_id):
        self._channelcast_db.drop_all_newer(dispersy_id)


class ChannelCastDBStub():

    def __init__(self, dispersy):
        self._dispersy = dispersy
        self.channel_id = None
        self.mychannel = False
        self.latest_result = 0

        self.cachedTorrents = None
        self.recentTorrents = []

    def convert_to_messages(self, results):
        messages = self._dispersy.convert_packets_to_messages(str(packet) for packet, _ in results)
        for packet_id, message in zip((packet_id for _, packet_id in results), messages):
            if message:
                message.packet_id = packet_id
                yield message.community.cid, message

    def getChannelIdFromDispersyCID(self, cid):
        return self.channel_id

    def getCountMaxFromChannelId(self, channel_id):
        if self.cachedTorrents:
            return len(self.cachedTorrents), self.latest_result

    def getRecentAndRandomTorrents(self, NUM_OWN_RECENT_TORRENTS=15, NUM_OWN_RANDOM_TORRENTS=10, NUM_OTHERS_RECENT_TORRENTS=15, NUM_OTHERS_RANDOM_TORRENTS=10, NUM_OTHERS_DOWNLOADED=5):
        torrent_dict = {}

        for _, payload in self.recentTorrents[:max(NUM_OWN_RECENT_TORRENTS, NUM_OTHERS_RECENT_TORRENTS)]:
            torrent_dict.setdefault(self.channel_id, set()).add(payload.infohash)

        if len(self.recentTorrents) >= NUM_OWN_RECENT_TORRENTS:
            for infohash in self.getRandomTorrents(self.channel_id, max(NUM_OWN_RANDOM_TORRENTS, NUM_OTHERS_RANDOM_TORRENTS)):
                torrent_dict.setdefault(self.channel_id, set()).add(infohash)

        return torrent_dict

    def getRandomTorrents(self, channel_id, limit=15):
        torrents = self._cachedTorrents.keys()
        if len(torrents) > limit:
            return sample(torrents, limit)
        return torrents

    def newTorrent(self, message):
        self._cachedTorrents[message.payload.infohash] = message

        self.recentTorrents.append((message.distribution.global_time, message.payload))
        self.recentTorrents.sort(reverse=True)
        self.recentTorrents[:50]

        self.latest_result = time()

    def setChannelId(self, channel_id, mychannel):
        self.channel_id = channel_id
        self.mychannel = mychannel

    def getMyChannelId(self):
        if self.mychannel:
            return self.channel_id

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
            self.recentTorrents.append((message.distribution.global_time, message.payload))

        self.recentTorrents.sort(reverse=True)
        self.recentTorrents[:50]


class VoteCastDBStub():

    def __init__(self, dispersy):
        self._dispersy = dispersy
        self._votecache = {}

    def getDispersyId(self, cid, public_key):
        if public_key in self._votecache:
            return self._votecache[public_key]

        sql = u"SELECT sync.id FROM sync JOIN member ON sync.member = member.id JOIN community ON community.id = sync.community JOIN meta_message ON sync.meta_message = meta_message.id WHERE community.classification = 'AllChannelCommunity' AND meta_message.name = 'votecast' AND member.public_key = ? ORDER BY global_time DESC LIMIT 1"
        try:
            id, = self._dispersy.database.execute(sql, (buffer(public_key),)).next()
            self._votecache[public_key] = int(id)
            return self._votecache[public_key]
        except StopIteration:
            return

    def getVoteForMyChannel(self, public_key):
        id = self.getDispersyId(None, public_key)
        if id:  # if we have a votecastmessage from this peer in our sync table, then signal a mark as favorite
            return 2
        return 0

    def get_latest_vote_dispersy_id(self, channel_id, voter_id):
        return


class PeerDBStub():

    def __init__(self, dispersy):
        self._dispersy = dispersy

    def addOrGetPeerID(self, public_key):
        return public_key
