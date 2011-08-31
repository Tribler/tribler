from hashlib import sha1
from time import time

from conversion import AllChannelConversion
from payload import ChannelCastPayload, VoteCastPayload, ChannelSearchRequestPayload, ChannelSearchResponsePayload

# from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler
# from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler

from Tribler.Core.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.destination import AddressDestination, CommunityDestination
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.resolution import PublicResolution

from Tribler.community.channel.message import DelayMessageReqChannelMessage
from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.community.allchannel.payload import ChannelCastRequestPayload
from traceback import print_exc

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint
from lencoder import log

CHANNELCAST_FIRST_MESSAGE = 3.0
CHANNELCAST_INTERVAL = 5.0
CHANNELCAST_BLOCK_PERIOD = 10.0 * 60.0

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
    def load_communities(cls, my_member, *args, **kargs):
        """
        Returns a list with all AllChannelCommunity instances that we are part off.

        Since there is one global AllChannelCommunity, we will return one using a static public
        master member key.
        """
        communities = super(AllChannelCommunity, cls).load_communities(*args, **kargs)

        if not communities:
            master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403b2c94642d3a2228c2f274dcac5ddebc1b36da58282931b960ac19b0c1238bc8d5a17dfeee037ef3c320785fea6531f9bd498000643a7740bc182fae15e0461b158dcb9b19bcd6903f4acc09dc99392ed3077eca599d014118336abb372a9e6de24f83501797edc25e8f4cce8072780b56db6637844b394c90fc866090e28bdc0060831f26b32d946a25699d1e8a89b".decode("HEX")
            master = Member.get_instance(master_key)

            dispersy_database = DispersyDatabase.get_instance()
            dispersy_database.execute(u"INSERT OR IGNORE INTO community (master, member, classification) VALUES (?, ?, ?)",
                                      (master.database_id, my_member.database_id, cls.get_classification()))

            # new community instance
            community = cls.load_community(master, *args, **kargs)

            # send out my initial dispersy-identity
            community.create_dispersy_identity()

            # add new community
            communities.append(community)

        return communities

    def __init__(self, master, integrate_with_tribler = True):
        super(AllChannelCommunity, self).__init__(master)
        
        self.integrate_with_tribler = integrate_with_tribler
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
        
        self._blocklist = {}

    def initiate_meta_messages(self):
        # Message(self, u"torrent-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), TorrentRequestPayload()),
        # Message(self, u"torrent-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), TorrentResponsePayload()),
        return [Message(self, u"channelcast", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), ChannelCastPayload(), self.check_channelcast, self.on_channelcast),
                Message(self, u"channelcast-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), ChannelCastRequestPayload(), self.check_channelcast_request, self.on_channelcast_request),
                Message(self, u"votecast", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), VoteCastPayload(), self.check_votecast, self.on_votecast)
                ]

    def initiate_conversions(self):
        return [DefaultConversion(self), AllChannelConversion(self)]
    
    @property
    def dispersy_sync_interval(self):
        return 5.0

    def create_channelcast(self, forward=True):
        try:
            now = time()
            
            favoriteTorrents = None
            normalTorrents = self._channelcast_db.getRecentAndRandomTorrents()

            #cleanup blocklist
            for address in self._blocklist.keys():
                if self._blocklist[address] + CHANNELCAST_BLOCK_PERIOD < now: #unblock address
                    self._blocklist.pop(address)
            
            if len(normalTorrents) > 0:
                #loop through all candidates to see if we can find a non-blocked address
                for candidate in self._dispersy.yield_online_candidates(self, 100):
                    if not candidate.address in self._blocklist:
                        log("dispersy.log", "trying-to-send-channelcast")
                        
                        peer_ids = set()
                        for member in candidate.members:
                            key = member.public_key
                            peer_ids.add(self._peer_db.addOrGetPeerID(key))
                        log("dispersy.log", "not-blocked", peers = len(peer_ids))
                        
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
                            torrents = normalTorrents
                            
                        if len(torrents) > 0:
                            meta = self.get_meta_message(u"channelcast")
                            message = meta.implement(meta.authentication.implement(),
                                                     meta.distribution.implement(self.global_time),
                                                     meta.destination.implement(),
                                                     meta.payload.implement(torrents))
                            
                            self._dispersy._send([candidate.address], [message.packet])
                            
                            #we've send something to this address, add to blocklist
                            key = candidate.address
                            self._blocklist[key] = now
                            
                            header = message.packet[:22].encode('HEX')
                            nr_torrents = sum(len(torrent) for torrent in torrents.values())
                            log("dispersy.log", "sending-channelcast", address = candidate.address, torrents = nr_torrents, marked = didFavorite, size=len(message.packet), header=header, cid=self.cid.encode('HEX'))
                            
                            #we're done
                            break
            else:
                log("dispersy.log", "no-data-for-channelcast")
                
        except:
            print_exc()
            raise
        
        finally:
            self._register_task(self.create_channelcast, delay=CHANNELCAST_INTERVAL)

    def check_channelcast(self, messages):
        log("dispersy.log", "checking-channelcast")
        # no timeline check because NoAuthentication policy is used
        return messages

    def on_channelcast(self, messages):
        for message in messages:
            log("dispersy.log", "received-channelcast")
            
            toCollect = {}
            for cid, torrents in message.payload.torrents.iteritems():
                # ensure that all the PreviewChannelCommunity instances exist
                try:
                    community = self._dispersy.get_community(cid, True)
                except KeyError:
                    if __debug__: dprint("join_community ", cid.encode("HEX"))
                    community = PreviewChannelCommunity.join_community(Member.get_instance(cid, public_key_available=False), self._my_member)

                # if __debug__:
                #     dprint(type(message.payload), " ", type(message.payload.meta), force=1)
                #     for infohash in torrents:
                #         assert isinstance(infohash, str)
                #         assert len(infohash) == 20
                
                for infohash in community.selectTorrentsToCollect(torrents):
                    toCollect.setdefault(cid,set()).add(infohash)
                
            nr_requests = sum([len(torrents) for torrents in toCollect.values()])
            if nr_requests > 0:
                self.create_channelcast_request(toCollect, message.address)
    
    def create_channelcast_request(self, toCollect, address):
        nr_requests = sum([len(torrents) for torrents in toCollect.values()])
        log("dispersy.log", "requesting-channelcast-torrents", nrTorrentsRequested = nr_requests)
        
        #create channelcast request message
        meta = self.get_meta_message(u"channelcast-request")
        message = meta.implement(meta.authentication.implement(),
                                 meta.distribution.implement(self.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(toCollect))
        self._dispersy._send([address], [message.packet])
    
    def check_channelcast_request(self, messages):
        # no timeline check because NoAuthentication policy is used
        return messages

    def on_channelcast_request(self, messages):
        for message in messages:
            requested_packets = []
            for cid, torrents in message.payload.torrents.iteritems():
                # ensure that all the PreviewChannelCommunity instances exist
                try:
                    community = self._dispersy.get_community(cid, True)
                except KeyError:
                    if __debug__: dprint("join_community ", cid.encode("HEX"))
                    community = PreviewChannelCommunity.join_community(cid, "", self._my_member)
                
                for infohash in torrents:
                    tormessage = community._get_message_from_torrent_infohash(infohash)
                    requested_packets.append(tormessage.packet)
            
            self._dispersy._send([message.address], requested_packets)
    
    def create_votecast(self, cid, vote, timestamp, store=True, update=True, forward=True):
        self._register_task(self._disp_create_votecast, (vote, timestamp, store, update, forward))

    def _disp_create_votecast(self, cid, vote, timestamp, store=True, update=True, forward=True):
        #reclassify community
        if vote == 2:
            communityclass = ChannelCommunity
        else:
            communityclass = PreviewChannelCommunity
            
        try:
            community = self.dispersy.get_community(cid)
        except KeyError:
            community = cid
        community = self.dispersy.reclassify_community(community, communityclass)

        #create vote message        
        meta = self.get_meta_message(u"votecast")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(cid, vote, timestamp))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message
                    
    def check_votecast(self, messages):
        to_send = {}
        
        for message in messages:
            cid = message.payload.cid
            
            authentication_member = message.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
            
            try:
                community = self._dispersy.get_community(cid, True)
            except KeyError:
                if __debug__: dprint("join_community ", cid.encode("HEX"))
                community = PreviewChannelCommunity.join_community(Member.get_instance(cid, public_key_available=False), self._my_member)
            
            if community._channel_id:
                dispersy_id = self._votecast_db.getDispersyId(community._channel_id, peer_id)
                if dispersy_id and dispersy_id != -1:
                    curmessage = self._get_message_from_dispersy_id(dispersy_id, 'votecast')
                    
                    #see if this message is newer
                    if curmessage.distribution.global_time > message.distribution.global_time:
                        yield DropMessage("Older vote than we currently have")
                        
                        if message.address not in to_send:
                            to_send[message.address] = []
                        to_send[message.address].append(curmessage.packet)
            else:
                yield DelayMessageReqChannelMessage(message, community)
                
        #send all 'newer' votes to addresses
        for address in to_send.keys():
            self._dispersy._send([address], to_send[address])
        
    def on_votecast(self, messages):
        if self.integrate_with_tribler:
            for message in messages:
                cid = message.payload.cid
                dispersy_id = message.packet_id
                
                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
                
                try:
                    community = self._dispersy.get_community(cid, True)
                except KeyError:
                    if __debug__: dprint("join_community ", cid.encode("HEX"))
                    community = PreviewChannelCommunity.join_community(Member.get_instance(cid, public_key_available=False), self._my_member)
                
                self._votecast_db.on_vote_from_dispersy(community._channel_id, peer_id, dispersy_id, message.payload.vote, message.payload.timestamp)
    
    def _get_message_from_dispersy_id(self, dispersy_id, messagename):
        # 1. get the packet
        try:
            cid, packet, packet_id = self._dispersy.database.execute(u"SELECT community.cid, sync.packet, sync.id FROM community JOIN sync ON sync.community = community.id WHERE sync.id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError("Unknown dispersy_id")
        cid = str(cid)
        packet = str(packet)

        # 2. convert packet into a Message instance
        try:
            message = self.get_conversion(packet[:22]).decode_message(("", -1), packet)
        except ValueError, v:
            #raise RuntimeError("Unable to decode packet")
            raise
        message.packet_id = packet_id
        
        # 3. check
        assert message.name == messagename, "Expecting a '%s' message"%messagename
        return message

class ChannelCastDBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy
        self._cachedTorrents = {}
    
    def convert_to_messages(self, results):
        messages = self._dispersy.convert_packets_to_messages(str(packet) for packet, _ in results)
        for packet_id, message in zip((packet_id for _, packet_id in results), messages):
            if message:
                message.packet_id = packet_id
                yield message.community.cid, message
        # for cid, packet, packet_id in results:
        #     cid = str(cid)
        #     packet = str(packet)
            
        #     try:
        #         community = self._dispersy.get_community(cid)
        #         message = community.get_conversion(packet[:22]).decode_message(("", -1), packet)
        #         message.packet_id = packet_id
                
        #         messages.append((cid, message))
                
        #     except ValueError, v:
        #         #raise RuntimeError("Unable to decode packet")
        #         import sys
        #         print >> sys.stderr, "Unable to decode packet", cid, packet
        #         raise
        # return messages
    
    def getRecentAndRandomTorrents(self, NUM_OWN_RECENT_TORRENTS=15, NUM_OWN_RANDOM_TORRENTS=10, NUM_OTHERS_RECENT_TORRENTS=15, NUM_OTHERS_RANDOM_TORRENTS=10, NUM_OTHERS_DOWNLOADED=5):
        torrent_dict = {}
        last_result_time = None
        
        sql = u"SELECT sync.packet, sync.id FROM sync JOIN meta_message ON sync.meta_message = meta_message.id JOIN community ON community.id = sync.community WHERE community.classification = 'ChannelCommunity' AND meta_message.name = 'torrent' ORDER BY global_time DESC LIMIT ?"
        results = list(self._dispersy.database.execute(sql, (NUM_OWN_RECENT_TORRENTS, )))
        
        messages = list(self.convert_to_messages(results))
        for cid, message in messages:
            torrent_dict.setdefault(cid,set()).add(message.payload.infohash)
            last_result_time = message.payload.timestamp
            
        if len(messages) == NUM_OWN_RECENT_TORRENTS:
            sql = u"SELECT sync.packet, sync.id FROM sync JOIN meta_message ON sync.meta_message = meta_message.id JOIN community ON community.id = sync.community WHERE community.classification = 'ChannelCommunity' AND meta_message.name = 'torrent' AND global_time < ? ORDER BY random() DESC LIMIT ?"
            results = list(self._dispersy.database.execute(sql, (last_result_time, NUM_OWN_RANDOM_TORRENTS)))
            
            messages = self.convert_to_messages(results)
            for cid, message in messages:
                torrent_dict.setdefault(cid,set()).add(message.payload.infohash)
                last_result_time = message.payload.timestamp
        return torrent_dict

    def _cacheTorrents(self):
        sql = u"SELECT sync.packet, sync.id FROM sync JOIN meta_message ON sync.meta_message = meta_message.id JOIN community ON community.id = sync.community WHERE community.classification = 'ChannelCommunity' AND meta_message.name = 'torrent'"
        results = list(self._dispersy.database.execute(sql))
        messages = self.convert_to_messages(results)
        
        self._cachedTorrents = {}
        for _, message in messages:
            self._cachedTorrents[message.payload.infohash] = message  

    def hasTorrents(self, channel_id, infohashes):
        self._cacheTorrents()

        returnAr = []
        for infohash in infohashes:
            if infohash in self._cachedTorrents:
                returnAr.append(True)
            else:
                returnAr.append(False)
        return returnAr
    
    def getTorrentFromChannelId(self, channel_id, infohash, keys):
        if not infohash in self._cachedTorrents:
            self._cacheTorrents()
        
        if infohash in self._cachedTorrents:
            return self._cachedTorrents[infohash].packet_id

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
