from hashlib import sha1

from conversion import AllChannelConversion
from preview import PreviewChannelCommunity
from payload import ChannelCastPayload, VoteCastPayload, ChannelSearchRequestPayload, ChannelSearchResponsePayload

# from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler
# from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler

from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.Core.dispersy.resolution import PublicResolution
from Tribler.Core.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.Core.dispersy.destination import AddressDestination, CommunityDestination
from Tribler.Core.dispersy.member import MyMember

from Tribler.Community.channel.message import DelayMessageReqChannelMessage
from Tribler.Community.channel.community import ChannelCommunity

from distutils.util import execute

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint


CHANNELCAST_FIRST_MESSAGE = 3
CHANNELCAST_INTERVAL = 15

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
            cid = sha1(master_key).digest()

            dispersy_database = DispersyDatabase.get_instance()
            dispersy_database.execute(u"INSERT OR IGNORE INTO community (user, classification, cid, public_key) VALUES (?, ?, ?, ?)",
                                      (my_member.database_id, cls.get_classification(), buffer(cid), buffer(master_key)))

            # new community instance
            community = cls.load_community(cid, master_key, *args, **kargs)

            # send out my initial dispersy-identity
            community.create_dispersy_identity()

            # add new community
            communities.append(community)

        return communities

    def __init__(self, cid, master_key, integrate_with_tribler = True):
        super(AllChannelCommunity, self).__init__(cid, master_key)
        
        if integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, VoteCastDBHandler, PeerDBHandler
            from Tribler.Core.defaults import NTFY_CHANNELCAST, NTFY_UPDATE
            from Tribler.Core.CacheDB.Notifier import Notifier
        
            # tribler channelcast database
            self._channelcast_db = ChannelCastDBHandler.getInstance()
            self._votecast_db = VoteCastDBHandler.getInstance()
            self._peer_db = PeerDBHandler.getInstance()
            self._notifier = Notifier.getInstance().notify
        else:
            self._channelcast_db = ChannelCastDBStub(self._dispersy)
            self._votecast_db = VoteCastDBStub(self._dispersy)
            self._peer_db = PeerDBStub(self._dispersy)
            self._notifier = False
            
        self._rawserver = self.dispersy.rawserver.add_task
        self._rawserver(self.create_channelcast, CHANNELCAST_FIRST_MESSAGE)

    def initiate_meta_messages(self):
        # Message(self, u"torrent-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), TorrentRequestPayload()),
        # Message(self, u"torrent-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), TorrentResponsePayload()),
        return [Message(self, u"channelcast", NoAuthentication(), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=10), ChannelCastPayload(), self.check_channelcast, self.on_channelcast),
                Message(self, u"votecast", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), VoteCastPayload(), self.check_votecast, self.on_votecast),
                Message(self, u"channel-search-request", NoAuthentication(), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=10), ChannelSearchRequestPayload(), self.check_channel_search_request, self.on_channel_search_request),
                Message(self, u"channel-search-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), ChannelSearchResponsePayload(), self.check_channel_search_response, self.on_channel_search_response),
                ]

    def initiate_conversions(self):
        return [DefaultConversion(self), AllChannelConversion(self)]

    def create_channelcast(self, forward=True):
        try:
            sync_ids = list(self._channelcast_db.getRecentAndRandomTorrents())
            if len(sync_ids) > 0:
                # select channel messages (associated with the sync_ids)
                sql = u"SELECT sync.packet FROM sync WHERE sync.id IN ("
                sql += (u"?, "*len(sync_ids))[:-2]
                sql += u")"
                
                packets = [str(packet) for packet, in self._dispersy.database.execute(sql, sync_ids)]
        
                meta = self.get_meta_message(u"channelcast")
                message = meta.implement(meta.authentication.implement(),
                                         meta.distribution.implement(self.global_time),
                                         meta.destination.implement(),
                                         meta.payload.implement(packets))
                self._dispersy.store_update_forward([message], False, False, forward)
                return message
        finally:
            self._rawserver(self.create_channelcast, CHANNELCAST_INTERVAL)

    def check_channelcast(self, messages):
        # no timeline check because NoAuthentication policy is used
        return messages

    def on_channelcast(self, messages):
        incoming_packets = []
        addresses = set()
        channels = set()

        for message in messages:
            incoming_packets.extend((message.address, packet) for packet in message.payload.packets)
            addresses.add(message.address)

        for _, packet in incoming_packets:
            # ensure that all the PreviewChannelCommunity instances exist
            try:
                community = self._dispersy.get_community(packet[:20], True)
            except KeyError:
                if __debug__: dprint("join_community ", packet[:20].encode("HEX"))
                community = PreviewChannelCommunity.join_community(packet[:20], "", self._my_member)
                
            channels.add(community._channel_id)

        # handle all packets
        if incoming_packets:
            self._dispersy.on_incoming_packets(incoming_packets)
        
        # start requesting not yet collected torrents
        if self._notifier:
            def notify(channel_id):
                self._notifier(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)
            
            infohashes = []
            for channel_id in channels:
                for infohash in self._channelcast_db.selectTorrentsToCollect(channel_id):
                    infohashes.append((infohash, channel_id))
            
            permids = set()
            for address in addresses:
                for member in self.get_members_from_address(address):
                    permids.add(member.public_key)
    
                    # HACK! update the Peer table, if the tribler overlay did not discover this peer's
                    # address yet
                    if not self._peer_db.hasPeer(member.public_key):
                        self._peer_db.addPeer(member.public_key, {"ip":address[0], "port":7760})
                
            for infohash, channel_id in infohashes:
                for permid in permids:
                    self._rtorrent_handler.download_torrent(permid, str(infohash), lambda infohash, metadata, filename: notify(channel_id) ,3)
                    
    
    def create_votecast(self, cid, vote, timestamp, store=True, update=True, forward=True):
        def dispersy_thread():
            self._disp_create_votecast(vote, timestamp, store, update, forward)
        self._rawserver(dispersy_thread)
    
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
            if isinstance(authentication_member, MyMember):
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
            
            try:
                community = self._dispersy.get_community(cid, True)
            except KeyError:
                if __debug__: dprint("join_community ", cid.encode("HEX"))
                community = PreviewChannelCommunity.join_community(cid, "", self._my_member)
            
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
                yield DelayMessageReqChannelMessage(message, cid)
                
        #send all 'newer' votes to addresses
        for address in to_send.keys():
            self._dispersy._send([address], to_send[address])
        
    def on_votecast(self, messages):
        if self._notifier:
            for message in messages:
                cid = message.payload.cid
                dispersy_id = message.packet_id
                
                authentication_member = message.authentication.member
                if isinstance(authentication_member, MyMember):
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
                
                try:
                    community = self._dispersy.get_community(cid, True)
                except KeyError:
                    if __debug__: dprint("join_community ", cid.encode("HEX"))
                    community = PreviewChannelCommunity.join_community(cid, "", self._my_member)
                
                self._votecast_db.on_vote_from_dispersy(community._channel_id, peer_id, dispersy_id, message.payload.vote, message.payload.timestamp)

    # def _start_torrent_request_queue(self):
    #     # check that we are not working on a request already
    #     if not self._torrent_request_outstanding:
    #         while True:
    #             if not self._torrent_request_queue:
    #                 if __debug__: dprint("no more infohashes outstanding")
    #                 return

    #             address, infohash = self._torrent_request_queue.pop(0)
    #             if self._torrent_database._db.fetchone(u"SELECT 1 FROM Torrent WHERE infohash = ?", (infohash,)):
    #                 if __debug__: dprint("we already have this infohash")
    #                 continue

    #             # found an infohash to request
    #             break

    #         self.create_torrent_request(address, infohash, self._fulfill_torrent_request, (address,))
    #         self._torrent_request_outstanding = True

    # def _fulfill_torrent_request(self, address, message, req_address):
    #     if message:
    #         # todo: handle torrent insert
    #         pass

    #     else:
    #         # timeout on a request to req_address.  all requests to this address will likely
    #         # timeout, hence remove all these requests
    #         self._torrent_request_queue = [(address, infohash) for address, infohash in self._torrent_request_queue if not address == req_address]

    #     self._torrent_request_outstanding = False
    #     self._start_torrent_request_queue()

    # def create_torrent_request(self, address, infohash, response_func, response_args=(), timeout=10.0, store_and_forward=True):
    #     """
    #     Create a message to request a .torrent file.
    #     """
    #     assert isinstance(infohash, str)
    #     assert len(infohash) == 20
    #     assert hasattr(response_func, "__call__")
    #     assert isinstance(response_args, tuple)
    #     assert isinstance(timeout, float)
    #     assert timeout > 0.0
    #     assert isinstance(store_and_forward, bool)

    #     meta = self.get_meta_message(u"torrent-request")
    #     request = meta.implement(meta.authentication.implement(),
    #                              meta.distribution.implement(self.global_time),
    #                              meta.destination.implement(address),
    #                              meta.payload.implement(infohash))

    #     if store_and_forward:
    #         self._dispersy.store_and_forward([request])

    #     if response_func:
    #         meta = self.get_meta_message(u"torrent-response")
    #         footprint = meta.generate_footprint(payload=(infohash,))
    #         self._dispersy.await_message(footprint, response_func, response_args, timeout)

    #     return request

    # def on_torrent_request(self, address, message):
    #     """
    #     Received a 'torrent-request' message.
    #     """
    #     # we need to find the .torrent file and read the binary data
    #     torrent = self._torrent_database.getTorrent(message.payload.infohash)
    #     dprint(torrent, lines=1)
    #     if not (torrent and torrent["destination_path"] and os.path.isfile(torrent["destination_path"])):
    #         raise DropMessage("We do not have the requested infohash")
    #         return
    #     torrent_data = open(torrent["destination_path"], "r").read()

    #     # we need to find, optionally, some meta data such as associated 'channel', 'torrent', and
    #     # 'modify' messages.

    #     # todo: niels?
    #     # messages = [Message]

    #     meta = self.get_meta_message(u"torrent-response")
    #     response = meta.implement(meta.authentication.implement(),
    #                               meta.distribution.implement(self.global_time),
    #                               meta.destination.implement(address),
    #                               meta.payload.implement(message.payload.infohash, torrent_data, messages))

    #     self._dispersy.store_and_forward([message])

    # def on_torrent_response(self, address, message):
    #     """
    #     Received a 'torrent-response' message.
    #     """
    #     # we ignore this message because we get a different callback to match it to the request
    #     pass

    def create_channel_search_request(self, skip, search, response_func, response_args=(), timeout=10.0, method=u"simple-any-keyword", store=True, forward=True):
        """
        Create a message to request a remote channel search.
        """
        assert isinstance(skip, (tuple, list))
        assert not filter(lambda x: not isinstance(x, Message), skip)
        assert isinstance(search, (tuple, list))
        assert not filter(lambda x: not isinstance(x, unicode), search)
        assert isinstance(method, unicode)
        assert method in (u"simple-any-keyword", u"simple-all-keywords")
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(timeout, float)
        assert timeout > 0.0

        # todo: we need to set a max items in the bloom filter to limit the size.  the bloom filter
        # be no more than +/- 1000 bytes large.
        skip_bloomfilter = BloomFilter(max(1, len(skip)), 0.1)
        map(skip_bloomfilter.add, (message.packet for message in skip))

        meta = self.get_meta_message(u"channel-search-request")
        request = meta.implement(meta.authentication.implement(),
                                 meta.distribution.implement(self.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(skip_bloomfilter, search, method))

        if response_func:
            meta = self.get_meta_message(u"channel-search-response")
            footprint = meta.generate_footprint(payload=(sha1(request.packet).digest(),))
            self._dispersy.await_message(footprint, response_func, response_args, timeout)

        self._dispersy.store_update_forward([request], store, False, forward)
        return request

    def check_channel_search_request(self, messages):
        for message in messages:
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def on_channel_search_request(self, messages):
        """
        Received a 'channel-search-request' message.
        """
        responses = []
        for request in messages:
            # we need to find channels matching the search criteria

            packets = []

            # todo: niels?
            # packets = [packets]

            # we need to find, optionally, some meta data such as associated 'torrent', and 'modify'
            # messages.

            # todo: niels?
            # packets = [packets]

            meta = self.get_meta_message(u"channel-search-response")
            responses.append(meta.implement(meta.authentication.implement(),
                                            meta.distribution.implement(self.global_time),
                                            meta.destination.implement(address),
                                            meta.payload.implement(sha1(request.packet).digest(), packets)))
        self._dispersy.store_update_forward(responses, False, False, True)

    def check_channel_search_response(self, messages):
        for message in messages:
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def on_channel_search_response(self, messages):
        """
        Received a 'channel-search-response' message.
        """
        # we ignore this message because we get a different callback to match it to the request
        pass

    def _get_message_from_dispersy_id(self, dispersy_id, messagename):
        # 1. get the packet
        try:
            cid, packet, packet_id = self._dispersy.database.execute(u"SELECT community.cid, sync.packet, sync.id FROM community JOIN sync ON sync.community = community.id WHERE sync.id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError("Unknown dispersy_id")
        cid = str(cid)
        packet = str(packet)

        # 2: check cid
        assert cid == self._cid, "Message not part of this community"

        # 3. convert packet into a Message instance
        try:
            message = self.get_conversion(packet[:22]).decode_message(("", -1), packet)
        except ValueError, v:
            #raise RuntimeError("Unable to decode packet")
            raise
        message.packet_id = packet_id
        
        # 4. check
        assert message.name == messagename, "Expecting a '%s' message"%messagename
        return message


class ChannelCastDBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy
    
    def getRecentAndRandomTorrents(self):
        sync_ids = set()
        
        # 15 latest packets
        sql = u"SELECT sync.id, global_time FROM sync JOIN name ON sync.name = name.id JOIN community ON community.id = sync.community WHERE community.classification = 'ChannelCommunity' AND name.value = 'torrent' ORDER BY global_time DESC LIMIT 15"
        results = self._dispersy.database.execute(sql)
        
        for syncid, _ in results:
            sync_ids.add(syncid)
            
        if len(results) == 15:
            least_recent = results[-1][1]
            sql = u"SELECT sync.id FROM sync JOIN name ON sync.name = name.id JOIN community ON community.id = sync.community WHERE community.classification = 'ChannelCommunity' AND name.value = 'torrent' AND global_time < ? ORDER BY random() DESC LIMIT 10"
            results = self._dispersy.database.execute(sql, (least_recent, ))

            for syncid, in results:
                sync_ids.add(syncid)
             
        return sync_ids

class VoteCastDBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy
        
    def getDispersyId(self, cid, public_key):
        sql = u"SELECT sync.id FROM sync JOIN user ON sync.user = user.id JOIN community ON community.id = sync.community WHERE community.cid = ? AND user.public_key = ? ORDER BY global_time DESC LIMIT 1"
        try:
            id,  = self._dispersy.database.execute(sql, (buffer(cid), buffer(public_key))).next()
            return int(id)
        
        except StopIteration:
            return
        
class PeerDBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy
        
    def addOrGetPeerID(self, public_key):
        return public_key