from random import expovariate

from conversion import ChannelConversion
from payload import ChannelPayload, TorrentPayload, PlaylistPayload, CommentPayload, ModificationPayload, PlaylistTorrentPayload, MissingChannelPayload


from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.Core.dispersy.resolution import LinearResolution, PublicResolution
from Tribler.Core.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.Core.dispersy.destination import CommunityDestination, AddressDestination
from Tribler.Core.dispersy.member import MyMember

from message import DelayMessageReqChannelMessage

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint
    from lencoder import log
    
    
class ChannelCommunity(Community):
    """
    Each user owns zero or more ChannelCommunities that other can join and use to discuss.
    """
    def __init__(self, cid, master_key):
        self.integrate_with_tribler = False
        self._channel_id = None
        self._last_sync_range = None
        self._last_sync_space_remaining = 0
        
        super(ChannelCommunity, self).__init__(cid, master_key)

        if self.integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, PeerDBHandler
            from Tribler.Core.CacheDB.sqlitecachedb import bin2str
            from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
            from Tribler.Core.defaults import NTFY_CHANNELCAST, NTFY_UPDATE
            from Tribler.Core.CacheDB.Notifier import Notifier
            
            # tribler channelcast database
            self._peer_db = PeerDBHandler.getInstance()
            self._channelcast_db = ChannelCastDBHandler.getInstance()
            
            # torrent collecting
            self._rtorrent_handler = RemoteTorrentHandler.getInstance()
            
            # notifier
            self._notifier = Notifier.getInstance().notify
    
            # tribler channel_id
            self._channel_id = self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(self._cid),))
            
            #modification_types
            self._modification_types = dict(self._channelcast_db._db.fetchall(u"SELECT name, id FROM MetaDataTypes"))
        else:
            try:
                message = self._get_latest_channel_message()
                if message:
                    self._channel_id = self._cid
            except:
                pass
            
        self._rawserver = self._dispersy.rawserver.add_task

    def initiate_meta_messages(self):
        if self.integrate_with_tribler:
            disp_on_torrent = self._disp_on_torrent
            disp_on_playlist = self._disp_on_playlist
            disp_on_comment = self._disp_on_comment
            disp_on_modification = self._disp_on_modification
            disp_on_playlist_torrent = self._disp_on_playlist_torrent
        else:
            def dummy_function(*params):
                return
            
            def handled_function(messages):
                for message in messages:
                    for _ in message.payload.torrentlist:
                        log("dispersy.log", "handled-barter-record")
            
            disp_on_torrent = handled_function
            disp_on_playlist = dummy_function
            disp_on_comment = dummy_function
            disp_on_modification = dummy_function
            disp_on_playlist_torrent = dummy_function
        
        return [Message(self, u"channel", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), ChannelPayload(), self._disp_check_channel, self._disp_on_channel),
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"random-order"), CommunityDestination(node_count=10), TorrentPayload(), self._disp_check_torrent, disp_on_torrent),
                Message(self, u"playlist", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), PlaylistPayload(), self._disp_check_playlist, disp_on_playlist),
                Message(self, u"comment", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), CommentPayload(), self._disp_check_comment, disp_on_comment),
                Message(self, u"modification", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), ModificationPayload(), self._disp_check_modification, disp_on_modification),
                Message(self, u"playlist_torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), PlaylistTorrentPayload(), self._disp_check_playlist_torrent, disp_on_playlist_torrent),
                Message(self, u"missing-channel", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingChannelPayload(), self._disp_check_missing_channel, self._disp_on_missing_channel),
                ]

    @property
    def dispersy_sync_interval(self):
        if self.integrate_with_tribler:
            return Community.dispersy_sync_interval(self)
        return 5

    @property
    def dispersy_sync_bloom_filters(self):
        """
        Returns a list with sync ranges that are synced this interval.

        Strategy:

         1. We choose a sync range using an exponential distribution.

         2. If the last sync range resulted in new packets we -also- sync using that range, given
            that it is different than the one choosen with at point 1.
        """
        lambd = 1.0 / (len(self._sync_ranges) / 2.0)
        index = min(int(expovariate(lambd)), len(self._sync_ranges) - 1)
        sync_range = self._sync_ranges[index]
        time_high = 0 if index == 0 else self._sync_ranges[index - 1].time_low

        # possibly add another range when the previous range resulted in new packets AND is
        # different from the one we now randomly choose AND the previous sync range still exists
        # (may have been removed, merged, or split).
        last_sync_range = self._last_sync_range
        if last_sync_range and \
               self._last_sync_space_remaining != last_sync_range.space_remaining and \
               last_sync_range.time_low != sync_range.time_low and \
               last_sync_range in self._sync_ranges:
            last_index = self._sync_ranges.index(last_sync_range)
            last_time_high = 0 if last_index == 0 else self._sync_ranges[last_index - 1].time_low

            self._last_sync_space_remaining = last_sync_range.space_remaining
            return [(sync_range.time_low, time_high, sync_range.bloom_filter),
                    (last_sync_range.time_low, last_time_high, last_sync_range.bloom_filter)]

        else:
            self._last_sync_range = None if index == 0 else sync_range
            self._last_sync_space_remaining = sync_range.space_remaining
            return [(sync_range.time_low, time_high, sync_range.bloom_filter)]

    def initiate_conversions(self):
        return [DefaultConversion(self), ChannelConversion(self)]

    def create_channel(self, name, description, store=True, update=True, forward=True):
        def dispersy_thread():
            self._disp_create_channel(name, description, store, update, forward)
        self._rawserver(dispersy_thread)
    
    def _disp_create_channel(self, name, description, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"channel")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(name, description))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_channel(self, messages):
        for message in messages:
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def _disp_on_channel(self, messages):
        for message in messages:
            if __debug__: dprint(message)

            if self.integrate_with_tribler:
                authentication_member = message.authentication.member
                if isinstance(authentication_member, MyMember):
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
    
                self._channel_id = self._channelcast_db.on_channel_from_dispersy(self._cid, peer_id, message.payload.name, message.payload.description)
            else:
                log("dispersy.log", "received-channel-record") # TODO: should change this to something more specific to channels
                self._channel_id = self._cid

    def _disp_create_torrent(self, infohash, timestamp, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"torrent")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement([(infohash, timestamp)]))
        self._dispersy.store_update_forward([message], store, update, forward)
        
        log("dispersy.log", "created-barter-record", size = len(message.packet)) # TODO: should change this to something more specific to channels
        return message
    
    def _disp_create_torrents(self, torrentlist, store=True, update=True, forward=True):
        messages = []
        
        max_torrents = 5 
        meta = self.get_meta_message(u"torrent")
        while len(torrentlist) > 0:
            curlist = torrentlist[:max_torrents]
            message = meta.implement(meta.authentication.implement(self._my_member),
                                     meta.distribution.implement(self.claim_global_time()),
                                     meta.destination.implement(),
                                     meta.payload.implement(curlist))
            
            log("dispersy.log", "created-torrent-record", size = len(message.packet), nr_torrents = len(curlist))
            for _ in curlist:
                log("dispersy.log", "created-barter-record")
            
            messages.append(message)
            torrentlist = torrentlist[max_torrents:]
            
        self._dispersy.store_update_forward(messages, store, update, forward)
        return messages

    def _disp_check_torrent(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
                
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def _disp_on_torrent(self, messages):
        torrentlist = []
        infohashes = set()
        addresses = set()
        
        for message in messages:
            if __debug__: dprint(message)
            
            dispersy_id = message.packet_id
            for infohash, timestamp in message.payload.torrentlist:
                torrentlist.append((self._channel_id, dispersy_id, infohash, timestamp))
                infohashes.add(infohash)
            
            addresses.add(message.address)
            
        self._channelcast_db.on_torrents_from_dispersy(torrentlist)
        
        #start requesting these .torrents, remote torrent collector will actually only make request if we do not already have the 
        #.torrent on disk
        def notify():
            self._notifier(NTFY_CHANNELCAST, NTFY_UPDATE, self._channel_id)
        
        permids = set()
        for address in addresses:
            for member in self.get_members_from_address(address):
                permids.add(member.public_key)
        
        for infohash in infohashes:
            for permid in permids:
                self._rtorrent_handler.download_torrent(permid, infohash, lambda infohash, metadata, filename: notify() ,2)

    #create, check or receive playlist
    def create_playlist(self, name, description, infohashes = [], store=True, update=True, forward=True):
        def dispersy_thread():
            message = self._disp_create_playlist.create_playlist(name, description)
            self._disp_create_playlist_torrents(infohashes, message, store, update, forward)
    
        self._rawserver(dispersy_thread)

    def _disp_create_playlist(self, name, description, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"playlist")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(name, description))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_playlist(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def _disp_on_playlist(self, messages):
        for message in messages:
            if __debug__: dprint(message)
            dispersy_id = message.packet_id
            self._channelcast_db.on_playlist_from_dispersy(self._channel_id, dispersy_id, message.payload.name, message.payload.description)

    #create, check or receive comments
    def create_comment(self, text, timestamp, reply_to, reply_after, playlist_id, infohash, store=True, update=True, forward=True):
        def dispersy_thread():
            reply_to_message = reply_to
            reply_after_message = reply_after
            playlist_message = playlist_id
            
            if reply_to:
                reply_to_message = self._get_message_from_dispersy_id(reply_to, 'comment')
            if reply_after:
                reply_after_message = self._get_message_from_dispersy_id(reply_after, 'comment')
            if playlist_id:
                playlist_message = self._get_message_from_playlist_id(playlist_id)
            self._disp_create_comment(text, timestamp, reply_to_message, reply_after_message, playlist_message, infohash, store, update, forward)
    
        self._rawserver(dispersy_thread)

    def _disp_create_comment(self, text, timestamp, reply_to_message, reply_after_message, playlist_message, infohash, store=True, update=True, forward=True):
        reply_to_mid = None
        reply_to_global_time = None
        if reply_to_message:
            message = reply_to_message.load_message()
            reply_to_mid = message.authentication.member.mid
            reply_to_global_time = message.distribution.global_time
        
        reply_after_mid = None
        reply_after_global_time = None
        if reply_after_message:
            message = reply_after_message.load_message()
            reply_after_mid = message.authentication.member.mid
            reply_after_global_time = message.distribution.global_time
        
        meta = self.get_meta_message(u"comment")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(text, timestamp, reply_to_message, reply_to_mid, reply_to_global_time, reply_after_message, reply_after_mid, reply_after_global_time, playlist_message, infohash))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_comment(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message
    
    def _disp_on_comment(self, messages):
        for message in messages:
            if __debug__: dprint(message)

            dispersy_id = message.packet_id
            
            authentication_member = message.authentication.member
            if isinstance(authentication_member, MyMember):
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
                
            mid_global_time = "%s@%d"%(message.authentication.member.mid, message.distribution.global_time)
            
            if message.payload.reply_to_packet:
                reply_to_id = message.payload.reply_to_packet.packet_id
            else:
                reply_to_id = message.payload.reply_to_id
            
            if message.payload.reply_after_packet:
                reply_after_id = message.payload.reply_after_packet.packet_id
            else:
                reply_after_id = message.payload.reply_after_id
            
            playlist_dispersy_id = None
            if message.payload.playlist_packet:
                playlist_dispersy_id = message.payload.playlist_packet.packet_id
            self._channelcast_db.on_comment_from_dispersy(self._channel_id, dispersy_id, mid_global_time, peer_id, message.payload.text, message.payload.timestamp, reply_to_id , reply_after_id, playlist_dispersy_id, message.payload.infohash)
        
    #modify channel, playlist or torrent
    def modifyChannel(self, modifications, store=True, update=True, forward=True):
        def dispersy_thread():
            modification_on_message = self._get_latest_channel_message()
            
            for type, value in modifications.iteritems():
                type = unicode(type)
                type_id = self._modification_types[type]
                
                latest_modification = self._get_latest_modification_from_channel_id(type_id)
                self._disp_create_modification(type, value, modification_on_message, latest_modification, store, update, forward)
        
        self._rawserver(dispersy_thread)
        
    def modifyPlaylist(self, playlist_id, modifications, store=True, update=True, forward=True):
        def dispersy_thread():
            modification_on_message = self._get_message_from_playlist_id(playlist_id)
            
            for type, value in modifications.iteritems():
                type = unicode(type)
                type_id = self._modification_types[type]
                
                latest_modification = self._get_latest_modification_from_playlist_id(playlist_id, type_id)
                self._disp_create_modification(type, value, modification_on_message, latest_modification, store, update, forward)
        
        self._rawserver(dispersy_thread)
    
    def modifyTorrent(self, channeltorrent_id, modifications, store=True, update=True, forward=True):
        def dispersy_thread():
            modification_on_message = self._get_message_from_torrent_id(channeltorrent_id)
            
            for type, value in modifications.iteritems():
                type = unicode(type)
                type_id = self._modification_types[type]
                
                latest_modification = self._get_latest_modification_from_torrent_id(channeltorrent_id, type_id)
                self._disp_create_modification(type, value, modification_on_message, latest_modification, store, update, forward)
                
        self._rawserver(dispersy_thread)
        
    def _disp_create_modification(self, modification_type, modifcation_value, modification_on, latest_modification, store=True, update=True, forward=True):
        latest_modification_mid = None
        latest_modification_global_time = None
        if latest_modification:
            message = latest_modification.load_message()
            latest_modification_mid = message.authentication.member.mid
            latest_modification_global_time = message.distribution.global_time
        
        meta = self.get_meta_message(u"modification")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(modification_type, modifcation_value, modification_on, latest_modification, latest_modification_mid, latest_modification_global_time))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_modification(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def _disp_on_modification(self, messages):
        for message in messages:
            if __debug__: dprint(message)
            
            dispersy_id = message.packet_id
            message_name = message.payload.modification_on.name
            mid_global_time = "%s@%d"%(message.authentication.member.mid, message.distribution.global_time)
            
            modifying_dispersy_id = message.payload.modification_on.packet_id
            modification_type = message.payload.modification_type
            modification_type_id = self._modification_types[modification_type]
            modification_value = message.payload.modification_value
            
            if message.payload.prev_modification_packet:
                prev_modification_id = message.payload.prev_modification_packet.packet_id
            else:
                prev_modification_id = message.payload.prev_modification_id
            prev_modification_global_time = message.payload.prev_modification_global_time
            
            #load local ids from database
            link_id = None
            if message_name ==  u"torrent":
                link_id = self._get_torrent_id_from_message(modifying_dispersy_id)
                
            elif message_name == u"playlist":
                link_id = self._get_playlist_id_from_message(modifying_dispersy_id)
                
            elif message_name == u"channel":
                link_id = self._channel_id
            
            #always store metadata
            self._channelcast_db.on_metadata_from_dispersy(message_name, link_id, dispersy_id, mid_global_time, modification_type_id, modification_value, prev_modification_id, prev_modification_global_time)
            
            #see if this is new information, if so call on_X_from_dispersy to update local 'cached' information
            if message_name ==  u"torrent":
                latest = self._get_latest_modification_from_torrent_id(link_id, modification_type_id)
                if latest.packet_id == dispersy_id:
                    self._channelcast_db.on_torrent_modification_from_dispersy(link_id, modification_type, modification_value)
        
            elif message_name == u"playlist":
                latest = self._get_latest_modification_from_playlist_id(link_id, modification_type_id)
                if latest.packet_id == dispersy_id:
                    self._channelcast_db.on_playlist_modification_from_dispersy(link_id, modification_type, modification_value)
        
            elif message_name == u"channel":
                latest = self._get_latest_modification_from_channel_id(modification_type_id)
                if latest.packet_id == dispersy_id:
                    self._channelcast_db.on_channel_modification_from_dispersy(self._channel_id, modification_type, modification_value)
            
    #create, check or receive playlist_torrent message
    def create_playlist_torrents(self, infohashes, playlist_id, store=True, update=True, forward=True):
        def dispersy_thread():
            message = self._get_message_from_playlist_id(playlist_id)
            self._disp_create_playlist_torrents(infohashes, message, store, update, forward)
            
        self._rawserver(dispersy_thread)
        
    def _disp_create_playlist_torrents(self, infohashes, playlist_message, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"playlist_torrent")
        messages = []
        for infohash in infohashes:
            message = meta.implement(meta.authentication.implement(self._my_member),
                                     meta.distribution.implement(self.claim_global_time()),
                                     meta.destination.implement(),
                                     meta.payload.implement(infohash, playlist_message))
            messages.append(message)

        self._dispersy.store_update_forward(messages, store, update, forward)
        return message
    
    def _disp_check_playlist_torrent(self, address, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            if not self._timeline.check(message):
                raise DropMessage("TODO: implement delay by proof")
            yield message
    
    def _disp_on_playlist_torrent(self, address, messages):
        for message in messages:
            
            playlist_dispersy_id = message.payload.playlist.packet_id
            self._channelcast_db.on_playlist_torrent(playlist_dispersy_id, message.payload.infohash)
            
    #check or receive missing channel message
    def _disp_check_missing_channel(self, messages):
        for message in messages:
            yield message

    def _disp_on_missing_channel(self, messages):
        channelmessage = self._get_latest_channel_message()
        for message in messages:
            log("dispersy.log", "sending-channel-record", address = message.address, packet = channelmessage.packet) # TODO: maybe move to barter.log

            self._dispersy._send([message.address], [channelmessage.packet])
            
    #helper functions
    def _get_latest_channel_message(self):
        # 1. get the packet
        try:
            sql = u"SELECT sync.packet, sync.id FROM sync JOIN name ON sync.name = name.id JOIN community ON community.id = sync.community WHERE community.cid = ? AND name.value = 'channel' ORDER BY global_time DESC"
            packet, packet_id = self._dispersy.database.execute(sql, (buffer(self._cid), )).next()
        except StopIteration:
            raise RuntimeError("Could not find requested packet")
        packet = str(packet)
        
        # 2. convert packet into a Message instance
        try:
            message = self.get_conversion(packet[:22]).decode_message(("", -1), packet)
        except ValueError:
            raise RuntimeError("Unable to decode packet")
        message.packet_id = packet_id

        # 3. check
        assert message.name == 'channel', "Expecting a 'channel' message"
        return message
        
    def _get_message_from_playlist_id(self, playlist_id):
        assert isinstance(playlist_id, (int, long))
        # 1. get the dispersy identifier from the channel_id
        dispersy_id = self._channelcast_db._db.fetchone(u"SELECT dispersy_id FROM Playlists WHERE id = ?", (playlist_id,))

        # 2. get the message
        message = self._get_message_from_dispersy_id(dispersy_id, 'playlist')
        return message
    
    def _get_playlist_id_from_message(self, dispersy_id):
        assert isinstance(dispersy_id, (int, long))
        return self._channelcast_db._db.fetchone(u"SELECT id FROM Playlists WHERE dispersy_id = ?", (dispersy_id,))
        
    def _get_message_from_torrent_id(self, torrent_id):
        assert isinstance(torrent_id, (int, long))

        # 1. get the dispersy identifier from the channel_id
        dispersy_id = self._channelcast_db._db.fetchone(u"SELECT dispersy_id FROM ChannelTorrents WHERE id = ?", (torrent_id,))
        
        # 2. get the message
        message = self._get_message_from_dispersy_id(dispersy_id, "torrent")
        return message
    
    def _get_torrent_id_from_message(self, dispersy_id):
        assert isinstance(dispersy_id, (int, long))
        return self._channelcast_db._db.fetchone(u"SELECT id FROM ChannelTorrents WHERE dispersy_id = ?", (dispersy_id,))
    
    def _get_latest_modification_from_channel_id(self, type_id):
        assert isinstance(type_id, (int, long))
        
        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(u"SELECT dispersy_id, prev_global_time FROM ChannelMetaData, MetaDataChannel WHERE ChannelMetaData.id = MetaDataChannel.metadata_id AND type_id = ? AND channel_id = ? ORDER BY prev_global_time DESC", (type_id, self._channel_id))
        return self._determine_latest_modification(dispersy_ids)
    
    def _get_latest_modification_from_torrent_id(self, channeltorrent_id, type_id):
        assert isinstance(channeltorrent_id, (int, long))
        assert isinstance(type_id, (int, long))

        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(u"SELECT dispersy_id, prev_global_time FROM ChannelMetaData, MetaDataTorrent WHERE ChannelMetaData.id = MetaDataTorrent.metadata_id AND type_id = ? AND channeltorrent_id = ? ORDER BY prev_global_time DESC", (type_id, channeltorrent_id))
        return self._determine_latest_modification(dispersy_ids)
    
    def _get_latest_modification_from_playlist_id(self, playlist_id, type_id):
        assert isinstance(playlist_id, (int, long))
        assert isinstance(type_id, (int, long))

        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(u"SELECT dispersy_id, prev_global_time FROM ChannelMetaData, MetaDataPlaylist WHERE ChannelMetaData.id = MetaDataPlaylist.metadata_id AND type_id = ? AND playlist_id = ? ORDER BY prev_global_time DESC", (type_id, playlist_id))
        return self._determine_latest_modification(dispersy_ids)
        
    def _determine_latest_modification(self, list):
        
        if len(list) > 0:
            # 1. determine if we have a conflict
            max_global_time = list[0][1]
            conflicting_messages = []
            for dispersy_id, prev_global_time in list:
                if prev_global_time >= max_global_time:
                    message = self._get_message_from_dispersy_id(dispersy_id, 'modification')
                    message = message.load_message()
                    conflicting_messages.append(message)
                    
                    max_global_time = prev_global_time
                else:
                    break
            
            # 2. see if we have a conflict
            if len(conflicting_messages) > 1:
                
                # 3. solve conflict using mid to sort on
                def cleverSort(message_a, message_b):
                    public_key_a = message_a.authentication.member.public_key
                    public_key_b = message_a.authentication.member.public_key
                    
                    if public_key_a == public_key_b:
                        return cmp(message_b.distribution.global_time, message_a.distribution.global_time)
                    
                    return cmp(public_key_a, public_key_b)
                
                conflicting_messages.sort(cleverSort)
            
            if len(conflicting_messages) > 0:
                # 4. return first message
                return conflicting_messages[0]
        
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
