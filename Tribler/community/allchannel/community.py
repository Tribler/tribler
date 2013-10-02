from Tribler.dispersy.logger import get_logger
logger = get_logger(__name__)

from hashlib import sha1
from itertools import islice
from time import time

from conversion import AllChannelConversion

from Tribler.dispersy.dispersy import MissingMessageCache
from Tribler.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.database import IgnoreCommits
from Tribler.dispersy.destination import CandidateDestination, CommunityDestination
from Tribler.dispersy.dispersydatabase import DispersyDatabase
from Tribler.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.dispersy.message import Message, DropMessage, \
    BatchConfiguration
from Tribler.dispersy.resolution import PublicResolution

from Tribler.community.channel.message import DelayMessageReqChannelMessage
from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.community.allchannel.payload import ChannelCastRequestPayload, \
    ChannelCastPayload, VoteCastPayload, ChannelSearchPayload, ChannelSearchResponsePayload
from traceback import print_exc
import sys
from random import sample

if __debug__:
    from Tribler.dispersy.tool.lencoder import log

CHANNELCAST_FIRST_MESSAGE = 3.0
CHANNELCAST_INTERVAL = 15.0
CHANNELCAST_BLOCK_PERIOD = 10.0 * 60.0  # block for 10 minutes

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
        master = dispersy.get_member(master_key)
        return [master]

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, auto_join_channel=False):
        try:
            dispersy.database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, auto_join_channel=auto_join_channel)
        else:
            return super(AllChannelCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, auto_join_channel=auto_join_channel)

    @property
    def dispersy_sync_bloom_filter_strategy(self):
        return self._dispersy_claim_sync_bloom_filter_modulo

    def __init__(self, dispersy, master, integrate_with_tribler=True, auto_join_channel=False):
        super(AllChannelCommunity, self).__init__(dispersy, master)

        self.integrate_with_tribler = integrate_with_tribler
        self.auto_join_channel = auto_join_channel

        if self.integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, VoteCastDBHandler, PeerDBHandler

            # tribler channelcast database
            self._channelcast_db = ChannelCastDBHandler.getInstance()
            self._votecast_db = VoteCastDBHandler.getInstance()
            self._peer_db = PeerDBHandler.getInstance()

        else:
            self._channelcast_db = ChannelCastDBStub(self._dispersy)
            self._votecast_db = VoteCastDBStub(self._dispersy)
            self._peer_db = PeerDBStub(self._dispersy)

        self._register_task = self.dispersy.callback.register
        self._register_task(self.create_channelcast, delay=CHANNELCAST_FIRST_MESSAGE)
        # 15/02/12 Boudewijn: add the callback id to _pending_callbacks to allow the task to be
        # unregistered when the community is unloaded
        self._pending_callbacks.append(self._register_task(self.unload_preview, priority= -128))

        self._blocklist = {}
        self._searchCallbacks = {}

        from Tribler.community.channel.community import register_callback
        register_callback(dispersy.callback)

    def initiate_meta_messages(self):
        batch_delay = 1.0

        return [Message(self, u"channelcast", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), ChannelCastPayload(), self.check_channelcast, self.on_channelcast),
                Message(self, u"channelcast-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), ChannelCastRequestPayload(), self.check_channelcast_request, self.on_channelcast_request),
                Message(self, u"channelsearch", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=10), ChannelSearchPayload(), self.check_channelsearch, self.on_channelsearch),
                Message(self, u"channelsearch-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), ChannelSearchResponsePayload(), self.check_channelsearch_response, self.on_channelsearch_response),
                Message(self, u"votecast", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), VoteCastPayload(), self.check_votecast, self.on_votecast, self.undo_votecast, batch=BatchConfiguration(max_window=batch_delay))
                ]

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
        mychannel_id = None
        while True:
            try:
                now = time()

                favoriteTorrents = None
                normalTorrents = None

                # cleanup blocklist
                for candidate in self._blocklist.keys():
                    if self._blocklist[candidate] + CHANNELCAST_BLOCK_PERIOD < now:  # unblock address
                        self._blocklist.pop(candidate)

                # fetch mychannel_id if neccesary
                if mychannel_id == None:
                    mychannel_id = self._channelcast_db.getMyChannelId()

                # loop through all candidates to see if we can find a non-blocked address
                for candidate in [candidate for candidate in self._iter_categories([u'walk', u'stumble'], once=True) if not candidate in self._blocklist]:
                    if not candidate:
                        continue

                    didFavorite = False
                    # only check if we actually have a channel
                    if mychannel_id:
                        peer_ids = set()
                        for member in candidate.get_members():
                            key = member.public_key
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

                        if DEBUG:
                            nr_torrents = sum(len(torrent) for torrent in torrents.values())
                            print >> sys.stderr, "AllChannelCommunity: sending channelcast message containing", nr_torrents, "torrents to", candidate.sock_addr, "didFavorite", didFavorite

                        if __debug__:
                            if not self.integrate_with_tribler:
                                nr_torrents = sum(len(torrent) for torrent in torrents.values())
                                log("dispersy.log", "Sending channelcast message containing %d torrents to %s didFavorite %s" % (nr_torrents, candidate.sock_addr, didFavorite))

                        # we're done
                        break

                else:
                    if DEBUG:
                        print >> sys.stderr, "AllChannelCommunity: no candidates to send channelcast message too"
                    if __debug__:
                        if not self.integrate_with_tribler:
                            log("dispersy.log", "Could not send channelcast message, no candidates")
            except:
                print_exc()

            yield CHANNELCAST_INTERVAL

    def get_nr_connections(self):
        return len(list(self.dispersy_yield_candidates()))

    def check_channelcast(self, messages):
        # no timeline check because PublicResolution policy is used
        return messages

    def on_channelcast(self, messages):
        for message in messages:
            if DEBUG:
                print >> sys.stderr, "AllChannelCommunity: received channelcast message"

            toCollect = {}
            for cid, torrents in message.payload.torrents.iteritems():
                for infohash in self._selectTorrentsToCollect(cid, torrents):
                    toCollect.setdefault(cid, set()).add(infohash)

            nr_requests = sum([len(torrents) for torrents in toCollect.values()])
            if nr_requests > 0:
                self.create_channelcast_request(toCollect, message.candidate)

                if __debug__:
                    if not self.integrate_with_tribler:
                        log("dispersy.log", "requesting-torrents", nr_requests=nr_requests)

    def create_channelcast_request(self, toCollect, candidate):
        # create channelcast request message
        meta = self.get_meta_message(u"channelcast-request")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), destination=(candidate,), payload=(toCollect,))
        self._dispersy._forward([message])

        if DEBUG:
            nr_requests = sum([len(torrents) for torrents in toCollect.values()])
            print >> sys.stderr, "AllChannelCommunity: requesting", nr_requests, "torrents from", candidate

    def check_channelcast_request(self, messages):
        # no timeline check because PublicResolution policy is used
        return messages

    def on_channelcast_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                requested_packets.extend(self._get_packets_from_infohashes(cid, torrents))

            if requested_packets:
                self._dispersy.statistics.dict_inc(self._dispersy.statistics.outgoing, u"channelcast-response", len(requested_packets))
                self._dispersy.endpoint.send([message.candidate], requested_packets)

            if DEBUG:
                print >> sys.stderr, "AllChannelCommunity: got request for ", len(requested_packets), "torrents from", message.candidate

    def create_channelsearch(self, keywords, callback):
        # clear searchcallbacks if new search
        query = " ".join(keywords)
        if query not in self._searchCallbacks:
            self._searchCallbacks.clear()
        self._searchCallbacks.setdefault(query, set()).add(callback)

        meta = self.get_meta_message(u"channelsearch")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,),
                            payload=(keywords,))

        if DEBUG:
            print >> sys.stderr, "AllChannelCommunity: searching for", query

        return self._dispersy._forward([message])

    def check_channelsearch(self, messages):
        # no timeline check because PublicResolution policy is used
        return messages

    def on_channelsearch(self, messages):
        for message in messages:
            keywords = message.payload.keywords
            query = " ".join(keywords)

            if DEBUG:
                print >> sys.stderr, "AllChannelCommunity: got search request for", query

            results = self._channelcast_db.searchChannelsTorrent(query, 7, 7, dispersyOnly=True)
            if len(results) > 0:
                responsedict = {}
                for channel_id, dispersy_cid, name, infohash, torname, time_stamp in results:
                    infohashes = responsedict.setdefault(dispersy_cid, set())
                    infohashes.add(infohash)
                    if DEBUG:
                        print >> sys.stderr, "AllChannelCommunity: found cid:", dispersy_cid.encode("HEX"), " infohash:", infohash.encode("HEX")

                self.create_channelsearch_response(keywords, responsedict, message.candidate)
            elif DEBUG:
                print >> sys.stderr, "AllChannelCommunity: no results"

    def create_channelsearch_response(self, keywords, torrents, candidate):
        # create channelsearch-response message
        meta = self.get_meta_message(u"channelsearch-response")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), destination=(candidate,), payload=(keywords, torrents))

        self._dispersy._forward([message])
        if DEBUG:
            nr_requests = sum([len(tors) for tors in torrents.values()])
            print >> sys.stderr, "AllChannelCommunity: sending", nr_requests, "results"

    def check_channelsearch_response(self, messages):
        with self._dispersy.database:
            for message in messages:
                for cid in message.payload.torrents.keys():
                    channel_id = self._get_channel_id(cid)
                    if not channel_id:
                        community = self._get_channel_community(cid)
                        yield DelayMessageReqChannelMessage(message, community, includeSnapshot=True)
                        break
                else:
                    yield message

    def on_channelsearch_response(self, messages):
        # request missing torrents
        self.on_channelcast(messages)

        for message in messages:
            # show results in gui
            keywords = message.payload.keywords
            query = " ".join(keywords)

            if DEBUG:
                print >> sys.stderr, "AllChannelCommunity: got search response for", query

            if query in self._searchCallbacks:
                torrents = message.payload.torrents
                for callback in self._searchCallbacks[query]:
                    callback(keywords, torrents)

            elif DEBUG:
                print >> sys.stderr, "AllChannelCommunity: no callback found"

    def disp_create_votecast(self, cid, vote, timestamp, store=True, update=True, forward=True):
        # reclassify community
        if vote == 2:
            communityclass = ChannelCommunity
        else:
            communityclass = PreviewChannelCommunity

        community = self._get_channel_community(cid)
        community = self.dispersy.reclassify_community(community, communityclass)

        # check if we need to cancel a previous vote
        latest_dispersy_id = self._votecast_db.get_latest_vote_dispersy_id(community._channel_id, None)
        if latest_dispersy_id:
            message = self._get_message_from_dispersy_id(latest_dispersy_id, "votecast")
            if message:
                self._dispersy.create_undo(self, message)

        # create new vote message
        meta = self.get_meta_message(u"votecast")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(cid, vote, timestamp))
        self._dispersy.store_update_forward([message], store, update, forward)

        if DEBUG:
            print >> sys.stderr, "AllChannelCommunity: sending votecast message, vote=", vote

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
                logger.debug("%s", message)

                community = communities.get(message.payload.cid)
                if community:
                    assert community.cid == message.payload.cid
                    # at this point we should NOT have the channel message for this community
                    if __debug__:
                        try:
                            self._dispersy.database.execute(u"SELECT * FROM sync WHERE community = ? AND meta_message = ? AND undone = 0", (community.database_id, community.get_meta_message(u"channel").database_id)).next()

                            print >> sys.stderr, "!!!We already have the channel message... no need to wait for it", community.cid.encode("HEX")
                            yield DropMessage(message, "Tribler and Dispersy databases not in sync...")
                            continue

                        except StopIteration:
                            pass

                    yield DelayMessageReqChannelMessage(message, community, includeSnapshot=message.payload.vote > 0)  # request torrents if positive vote
                else:
                    message.channel_id = channel_ids[message.payload.cid]
                    yield message

            # ensure that no commits occur
            raise IgnoreCommits()

    def on_votecast(self, messages):
        if self.integrate_with_tribler:
            votelist = []
            for message in messages:
                logger.debug("%s", message)
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
                            insert_channel = "INSERT INTO _Channels (dispersy_cid, peer_id, name) VALUES (?, ?, ?); SELECT last_insert_rowid();"
                            channel_id = self._channelcast_db._db.fetchone(insert_channel, (buffer(message.payload.cid), -1, ''))
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

                votelist.append((channel_id, peer_id, dispersy_id, message.payload.vote, message.payload.timestamp))

                if DEBUG:
                    print >> sys.stderr, "AllChannelCommunity: got votecast message"

            self._votecast_db.on_votes_from_dispersy(votelist)

            # this might be a response to a dispersy-missing-message
            self._dispersy.handle_missing_messages(messages, MissingMessageCache)

    def undo_votecast(self, descriptors, redo=False):
        if self.integrate_with_tribler:
            for _, _, packet in descriptors:
                message = packet.load_message()
                dispersy_id = message.packet_id

                channel_id = self._get_channel_id(message.payload.cid)
                self._votecast_db.on_remove_vote_from_dispersy(channel_id, dispersy_id, redo)

    def _get_channel_community(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        try:
            return self._dispersy.get_community(cid, True)
        except KeyError:
            if self.auto_join_channel:
                logger.debug("join channel community %s", cid.encode("HEX"))
                return ChannelCommunity.join_community(self._dispersy, self._dispersy.get_temporary_member_from_id(cid), self._my_member, self.integrate_with_tribler)
            else:
                logger.debug("join preview community %s", cid.encode("HEX"))
                return PreviewChannelCommunity.join_community(self._dispersy, self._dispersy.get_temporary_member_from_id(cid), self._my_member, self.integrate_with_tribler)

    def unload_preview(self):
        while True:
            yield 60.0

            cleanpoint = time() - 300
            inactive = [community for community in self.dispersy._communities.itervalues() if isinstance(community, PreviewChannelCommunity) and community.init_timestamp < cleanpoint]
            logger.debug("cleaning %d/%d previewchannel communities", len(inactive), len(self.dispersy._communities))

            for community in inactive:
                community.unload_community()

    def _get_channel_id(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20

        channel_id = self._channelcast_db.getChannelIdFromDispersyCID(buffer(cid))
        if not channel_id:
            self._get_channel_community(cid)
        return channel_id

    def _selectTorrentsToCollect(self, cid, infohashes):
        channel_id = self._get_channel_id(cid)

        row = self._channelcast_db.getCountMaxFromChannelId(channel_id)
        if row:
            nrTorrrents, latestUpdate = row
        else:
            nrTorrrents = 0
            latestUpdate = 0

        collect = []

        # only request updates if nrT < 100 or we have not received an update in the last half hour
        if nrTorrrents < 100 or latestUpdate < (time() - 1800):
            infohashes = list(infohashes)
            haveTorrents = self._channelcast_db.hasTorrents(channel_id, infohashes)
            for i in range(len(infohashes)):
                if not haveTorrents[i]:
                    collect.append(infohashes[i])
        return collect

    def _get_packets_from_infohashes(self, cid, infohashes):
        channel_id = self._get_channel_id(cid)

        packets = []
        for infohash in infohashes:
            dispersy_id = self._channelcast_db.getTorrentFromChannelId(channel_id, infohash, ['ChannelTorrents.dispersy_id'])

            if dispersy_id and dispersy_id > 0:
                try:
                    # 2. get the message
                    packets.append(self._get_packet_from_dispersy_id(dispersy_id, "torrent"))

                except RuntimeError:
                    pass
        return packets

    def _get_packet_from_dispersy_id(self, dispersy_id, messagename):
        try:
            packet, = self._dispersy.database.execute(u"SELECT sync.packet FROM community JOIN sync ON sync.community = community.id WHERE sync.id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError("Unknown dispersy_id")
        return str(packet)

    def _get_message_from_dispersy_id(self, dispersy_id, messagename):
        # 1. get the packet
        try:
            packet, packet_id = self._dispersy.database.execute(u"SELECT sync.packet, sync.id FROM community JOIN sync ON sync.community = community.id WHERE sync.id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError("Unknown dispersy_id")

        # 2. convert packet into a Message instance
        message = self._dispersy.convert_packet_to_message(str(packet), verify=False)
        if message:
            message.packet_id = packet_id
        else:
            raise RuntimeError("Unable to convert packet")

        if message.name == messagename:
            return message

        raise RuntimeError("Message is of an incorrect type, expecting a '%s' message got a '%s'" % (messagename, message.name))

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
