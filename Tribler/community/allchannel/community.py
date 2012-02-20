from hashlib import sha1
from time import time

from conversion import AllChannelConversion

from Tribler.Core.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.destination import CandidateDestination, CommunityDestination
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.resolution import PublicResolution

from Tribler.community.channel.message import DelayMessageReqChannelMessage
from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.community.allchannel.payload import ChannelCastRequestPayload,\
    ChannelCastPayload, VoteCastPayload, ChannelSearchPayload, ChannelSearchResponsePayload
from traceback import print_exc
import sys

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint
    from lencoder import log

CHANNELCAST_FIRST_MESSAGE = 3.0
CHANNELCAST_INTERVAL = 15.0
CHANNELCAST_BLOCK_PERIOD = 10.0 * 60.0 #block for 10 minutes

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
    def get_master_members(cls):
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
        master = Member.get_instance(master_key)
        return [master]

    @classmethod
    def load_community(cls, master, my_member, integrate_with_tribler = True, auto_join_channel = False):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler = integrate_with_tribler, auto_join_channel = auto_join_channel)
        else:
            return super(AllChannelCommunity, cls).load_community(master, integrate_with_tribler = integrate_with_tribler, auto_join_channel = auto_join_channel)

    def __init__(self, master, integrate_with_tribler = True, auto_join_channel = False):
        super(AllChannelCommunity, self).__init__(master)
        
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
        self._register_task(self.unload_preview, priority=-128)
        
        self._blocklist = {}
        self._searchCallbacks = {}

    def initiate_meta_messages(self):
        return [Message(self, u"channelcast", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), ChannelCastPayload(), self.check_channelcast, self.on_channelcast),
                Message(self, u"channelcast-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), ChannelCastRequestPayload(), self.check_channelcast_request, self.on_channelcast_request),
                Message(self, u"channelsearch", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=10), ChannelSearchPayload(), self.check_channelsearch, self.on_channelsearch),
                Message(self, u"channelsearch-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), ChannelSearchResponsePayload(), self.check_channelsearch_response, self.on_channelsearch_response),
                Message(self, u"votecast", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), VoteCastPayload(), self.check_votecast, self.on_votecast, self.undo_votecast)
                ]

    def initiate_conversions(self):
        return [DefaultConversion(self), AllChannelConversion(self)]

    def create_channelcast(self):
        try:
            now = time()
            
            favoriteTorrents = None
            normalTorrents = None

            #cleanup blocklist
            for candidate in self._blocklist.keys():
                if self._blocklist[candidate] + CHANNELCAST_BLOCK_PERIOD < now: #unblock address
                    self._blocklist.pop(candidate)
            
            #loop through all candidates to see if we can find a non-blocked address
            for candidate in self._dispersy.yield_random_candidates(self, 10, self._blocklist.keys()):
                peer_ids = set()
                for member in candidate.members_in_community(self):
                    key = member.public_key
                    peer_ids.add(self._peer_db.addOrGetPeerID(key))
                        
                #see if all members on this address are subscribed to my channel
                didFavorite = len(peer_ids) > 0
                for peer_id in peer_ids:
                    vote = self._votecast_db.getVoteForMyChannel(peer_id)
                    if vote != 2:
                        didFavorite = False
                        break
                        
                #Modify type of message depending on if all peers have marked my channels as their favorite
                if didFavorite:
                    if not favoriteTorrents:
                        favoriteTorrents = self._channelcast_db.getRecentAndRandomTorrents(0, 0, 25, 25 ,5)
                    torrents = favoriteTorrents
                else:
                    if not normalTorrents:
                        normalTorrents = self._channelcast_db.getRecentAndRandomTorrents()
                    torrents = normalTorrents
                            
                if len(torrents) > 0:
                    meta = self.get_meta_message(u"channelcast")
                    message = meta.impl(authentication=(self._my_member,),
                                        distribution=(self.global_time,), payload=(torrents,))
                            
                    self._dispersy._send([candidate], [message.packet], key = meta.name)
                            
                    #we've send something to this address, add to blocklist
                    self._blocklist[candidate] = now
                            
                    if DEBUG:
                        nr_torrents = sum(len(torrent) for torrent in torrents.values())
                        print >> sys.stderr, "AllChannelCommunity: sending channelcast message containing",nr_torrents,"torrents to",candidate.address,"didFavorite",didFavorite

                    if __debug__:
                        if not self.integrate_with_tribler:
                            nr_torrents = sum(len(torrent) for torrent in torrents.values())
                            log("dispersy.log", "Sending channelcast message containing %d torrents to %s didFavorite %s"%(nr_torrents,candidate.address,didFavorite))
                    
                    #we're done
                    break       

            else:
                if DEBUG:
                    print >> sys.stderr, "AllChannelCommunity: no candidates to send channelcast message too"
                if __debug__:
                    if not self.integrate_with_tribler:
                        log("dispersy.log", "Could not send channelcast message, no candidates")
        except:
            print_exc()
            raise
        
        finally:
            self._register_task(self.create_channelcast, delay=CHANNELCAST_INTERVAL)

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
                    toCollect.setdefault(cid,set()).add(infohash)
                
            nr_requests = sum([len(torrents) for torrents in toCollect.values()])
            if nr_requests > 0:
                self.create_channelcast_request(toCollect, message.candidate)

                if __debug__:
                    if not self.integrate_with_tribler:
                        log("dispersy.log", "requesting-torrents", nr_requests = nr_requests)
    
    def create_channelcast_request(self, toCollect, candidate):
        #create channelcast request message
        meta = self.get_meta_message(u"channelcast-request")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(toCollect,))
        self._dispersy._send([candidate], [message.packet], key = meta.name)
        
        if DEBUG:
            nr_requests = sum([len(torrents) for torrents in toCollect.values()])
            print >> sys.stderr, "AllChannelCommunity: requesting",nr_requests,"torrents from",candidate
    
    def check_channelcast_request(self, messages):
        # no timeline check because PublicResolution policy is used
        return messages

    def on_channelcast_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                reqmessages = self._get_messages_from_infohashes(cid, torrents)
                for reqmessage in reqmessages:
                    requested_packets.append(reqmessage.packet)

            if requested_packets:
                self._dispersy._send([message.candidate], requested_packets, key = u'channelcast-response')
            
            if DEBUG:
                print >> sys.stderr, "AllChannelCommunity: got request for ",len(requested_packets),"torrents from",message.candidate
    
    def create_channelsearch(self, keywords, callback):
        #clear searchcallbacks if new search
        query = " ".join(keywords)
        if query not in self._searchCallbacks:
            self._searchCallbacks.clear()
        self._searchCallbacks.setdefault(query, set()).add(callback)
        
        meta = self.get_meta_message(u"channelsearch")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,),
                            payload=(keywords, ))
        
        self._dispersy.store_update_forward([message], store = False, update = False, forward = True)
        
        if DEBUG:
            print >> sys.stderr, "AllChannelCommunity: searching for",query
    
    def check_channelsearch(self, messages):
        #no timeline check because PublicResolution policy is used
        return messages

    def on_channelsearch(self, messages):
        for message in messages:
            keywords = message.payload.keywords
            query = " ".join(keywords)
            
            if DEBUG:
                print >> sys.stderr, "AllChannelCommunity: got search request for",query
            
            results = self._channelcast_db.searchChannelsTorrent(query, 7, 7, dispersyOnly = True)
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
        #create channelsearch-response message
        meta = self.get_meta_message(u"channelsearch-response")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(keywords, torrents))
        
        self._dispersy._send([candidate], [message.packet], key = meta.name)
        
        if DEBUG:
            nr_requests = sum([len(tors) for tors in torrents.values()])
            print >> sys.stderr, "AllChannelCommunity: sending",nr_requests,"results"
    
    def check_channelsearch_response(self, messages):
        #no timeline check because PublicResolution policy is used
        return messages
        
    def on_channelsearch_response(self, messages):
        #request missing torrents
        self.on_channelcast(messages)
        
        for message in messages:
            #show results in gui
            keywords = message.payload.keywords
            query = " ".join(keywords)
            
            if DEBUG:
                print >> sys.stderr, "AllChannelCommunity: got search response for",query
            
            if query in self._searchCallbacks:
                torrents = message.payload.torrents
                for callback in self._searchCallbacks[query]:
                    callback(keywords, torrents)
                    
            elif DEBUG:
                print >> sys.stderr, "AllChannelCommunity: no callback found"

    def _disp_create_votecast(self, cid, vote, timestamp, store=True, update=True, forward=True):
        #reclassify community
        if vote == 2:
            communityclass = ChannelCommunity
        else:
            communityclass = PreviewChannelCommunity
        
        community = self._get_channel_community(cid)
        community = self.dispersy.reclassify_community(community, communityclass)

        #check if we need to cancel a previous vote
        latest_dispersy_id = self._votecast_db.get_latest_vote_dispersy_id(community._channel_id, None)
        if latest_dispersy_id:
            message = self._get_message_from_dispersy_id(latest_dispersy_id, "votecast")
            if message:
                self._dispersy.create_undo(self, message)

        #create new vote message
        meta = self.get_meta_message(u"votecast")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(cid, vote, timestamp))
        self._dispersy.store_update_forward([message], store, update, forward)
        
        if DEBUG:
            print >> sys.stderr, "AllChannelCommunity: sending votecast message, vote=",vote
        
        return message
                    
    def check_votecast(self, messages):
        for message in messages:
            if __debug__: dprint(message)
            
            channel_id = self._get_channel_id(message.payload.cid)
            if not channel_id:
                community = self._get_channel_community(message.payload.cid)
                yield DelayMessageReqChannelMessage(message, community, includeSnapshot = message.payload.vote > 0) #request torrents if positive vote
            else:
                yield message
                
    def on_votecast(self, messages):
        if self.integrate_with_tribler:
            for message in messages:
                if __debug__: dprint(message)
                dispersy_id = message.packet_id
                
                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                    channel_id = self._get_channel_id(message.payload.cid)
                    
                    #if channel_id is not found, then this is a manual join
                    #insert placeholder into database which will be replaced after channelmessage has been received
                    if not channel_id:
                        insert_channel = "INSERT INTO _Channels (dispersy_cid, peer_id, name) VALUES (?, ?, ?); SELECT last_insert_rowid();"
                        channel_id = self._channelcast_db._db.fetchone(insert_channel, (buffer(message.payload.cid), -1, ''))
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
                    channel_id = self._get_channel_id(message.payload.cid)
                    
                self._votecast_db.on_vote_from_dispersy(channel_id, peer_id, dispersy_id, message.payload.vote, message.payload.timestamp)
                
                if DEBUG:
                    print >> sys.stderr, "AllChannelCommunity: got votecast message"
    
    def undo_votecast(self, descriptors):
        if self.integrate_with_tribler:
            for _, _, packet in descriptors:
                message = packet.load_message()
                dispersy_id = message.packet_id
                
                channel_id = self._get_channel_id(message.payload.cid)
                self._votecast_db.on_remove_vote_from_dispersy(channel_id, dispersy_id)

    def _get_channel_community(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20
        
        try:
            return self._dispersy.get_community(cid, True)
        except KeyError:
            if self.auto_join_channel:
                if __debug__: dprint("join channel community ", cid.encode("HEX"))
                return ChannelCommunity.join_community(Member.get_instance(cid, public_key_available=False), self._my_member, self.integrate_with_tribler)
            else:
                if __debug__: dprint("join preview community ", cid.encode("HEX"))
                return PreviewChannelCommunity.join_community(Member.get_instance(cid, public_key_available=False), self._my_member, self.integrate_with_tribler)
            
    def unload_preview(self):
        while True:
            desync = (yield 300.0)
            if desync > 0.1:
                yield desync
                
            inactive = [community for community in self.dispersy._communities.itervalues() if isinstance(community, PreviewChannelCommunity)]
            if __debug__:
                print("cleaning ", len(inactive), "/", len(self.dispersy._communities), " previewchannel communities")
                
            for community in inactive:
                community.unload_community()
    
    def _get_channel_id(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20
        
        return self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(cid),))
    
    def _selectTorrentsToCollect(self, cid, infohashes):
        channel_id = self._get_channel_id(cid)
        
        sql = u"SELECT COUNT(*), MAX(inserted) FROM ChannelTorrents WHERE channel_id = ? LIMIT 1"
        row = self._channelcast_db._db.fetchone(sql, (channel_id,))
        if row:
            nrTorrrents, latestUpdate = row
        else:
            nrTorrrents = 0
            latestUpdate = 0
        
        collect = []
        
        #only request updates if nrT < 25 or we have not received an update in the last hour
        if nrTorrrents < 25 or latestUpdate < (time() - 3600): 
            infohashes = list(infohashes)
            haveTorrents = self._channelcast_db.hasTorrents(channel_id, infohashes)
            for i in range(len(infohashes)):
                if not haveTorrents[i]:
                    collect.append(infohashes[i])
        return collect
    
    def _get_messages_from_infohashes(self, cid, infohashes):
        channel_id = self._get_channel_id(cid)
        
        messages = []
        for infohash in infohashes:
            dispersy_id = self._channelcast_db.getTorrentFromChannelId(channel_id, infohash, ['dispersy_id'])
            
            if dispersy_id and dispersy_id > 0:
                try:
                    # 2. get the message
                    message = self._get_message_from_dispersy_id(dispersy_id, "torrent")
                    if message:
                        messages.append(message)
                    
                except RuntimeError:
                    pass
        return messages

    def _get_message_from_dispersy_id(self, dispersy_id, messagename):
        # 1. get the packet
        try:
            packet, packet_id = self._dispersy.database.execute(u"SELECT sync.packet, sync.id FROM community JOIN sync ON sync.community = community.id WHERE sync.id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError("Unknown dispersy_id")

        # 2. convert packet into a Message instance
        message = self._dispersy.convert_packet_to_message(str(packet))        
        if message:
            assert message.name == messagename, "Expecting a '%s' message"%messagename
            message.packet_id = packet_id
        else:
            raise RuntimeError("unable to convert packet")
        
        if message.name == messagename:
            return message
        
    def _drop_all_newer(self, dispersy_id):
        self._channelcast_db.drop_all_newer(dispersy_id)

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
    
    def getRecentAndRandomTorrents(self, NUM_OWN_RECENT_TORRENTS=15, NUM_OWN_RANDOM_TORRENTS=10, NUM_OTHERS_RECENT_TORRENTS=15, NUM_OTHERS_RANDOM_TORRENTS=10, NUM_OTHERS_DOWNLOADED=5):
        torrent_dict = {}
        last_result_time = None
        
        sql = u"SELECT sync.packet, sync.id FROM sync JOIN meta_message ON sync.meta_message = meta_message.id JOIN community ON community.id = sync.community WHERE community.classification = 'ChannelCommunity' AND meta_message.name = 'torrent' ORDER BY global_time DESC LIMIT ?"
        results = list(self._dispersy.database.execute(sql, (NUM_OWN_RECENT_TORRENTS, )))
        
        messages = list(self.convert_to_messages(results))
        for cid, message in messages:
            torrent_dict.setdefault(cid,set()).add(message.payload.infohash)
            last_result_time = message.payload.timestamp
            
            if message.payload.infohash not in self._cachedTorrents:
                self._cachedTorrents[message.payload.infohash] = message
            
        if len(messages) == NUM_OWN_RECENT_TORRENTS:
            sql = u"SELECT sync.packet, sync.id FROM sync JOIN meta_message ON sync.meta_message = meta_message.id JOIN community ON community.id = sync.community WHERE community.classification = 'ChannelCommunity' AND meta_message.name = 'torrent' AND global_time < ? ORDER BY random() DESC LIMIT ?"
            results = list(self._dispersy.database.execute(sql, (last_result_time, NUM_OWN_RANDOM_TORRENTS)))
            
            messages = self.convert_to_messages(results)
            for cid, message in messages:
                torrent_dict.setdefault(cid,set()).add(message.payload.infohash)
                last_result_time = message.payload.timestamp
                
                if message.payload.infohash not in self._cachedTorrents:
                    self._cachedTorrents[message.payload.infohash] = message
                
        return torrent_dict
    
    def getRandomTorrents(self, channel_id, limit = 15):
        sql = u"SELECT sync.packet, sync.id FROM sync JOIN meta_message ON sync.meta_message = meta_message.id JOIN community ON community.id = sync.community WHERE community.classification = 'ChannelCommunity' AND meta_message.name = 'torrent' ORDER BY random() DESC LIMIT ?"
        results = list(self._dispersy.database.execute(sql, (limit,)))
        messages = self.convert_to_messages(results)
        
        for _, message in messages:
            if message.payload.infohash not in self._cachedTorrents:
                self._cachedTorrents[message.payload.infohash] = message
        
        return [message.payload.infohash for _, message in messages]
            
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

class VoteCastDBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy
        
    def getDispersyId(self, cid, public_key):
        sql = u"SELECT sync.id FROM sync JOIN member ON sync.member = member.id JOIN community ON community.id = sync.community JOIN meta_message ON sync.meta_message = meta_message.id WHERE community.classification = 'AllChannelCommunity' AND meta_message.name = 'votecast' AND member.public_key = ? ORDER BY global_time DESC LIMIT 1"
        try:
            id,  = self._dispersy.database.execute(sql, (buffer(public_key), )).next()
            return int(id)
        except StopIteration:
            return
        
    def getVoteForMyChannel(self, public_key):
        id = self.getDispersyId(None, public_key)
        if id: #if we have a votecastmessage from this peer in our sync table, then signal a mark as favorite
            return 2
        return 0
        
class PeerDBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy
        
    def addOrGetPeerID(self, public_key):
        return public_key
