from random import expovariate, choice, randint

from conversion import ChannelConversion
from payload import ChannelPayload, TorrentPayload, PlaylistPayload, CommentPayload, ModificationPayload, PlaylistTorrentPayload, MissingChannelPayload, WarningPayload, MarkTorrentPayload


from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.message import Message, DropMessage, DelayMessageByProof
from Tribler.Core.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.Core.dispersy.resolution import LinearResolution, PublicResolution
from Tribler.Core.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.Core.dispersy.destination import CommunityDestination, AddressDestination

from message import DelayMessageReqChannelMessage
from threading import currentThread, Event
from traceback import print_stack
import sys

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint
    from lencoder import log

_register_task = None

def forceDispersyThread(func):
    def invoke_func(*args,**kwargs):
        if not currentThread().getName()== 'Dispersy':
            def dispersy_thread():
                func(*args, **kwargs)
            _register_task(dispersy_thread)
        else:
            func(*args, **kwargs)
            
    invoke_func.__name__ = func.__name__
    return invoke_func

def forceAndReturnDispersyThread(func):
    def invoke_func(*args,**kwargs):
        if not currentThread().getName()== 'Dispersy':
            event = Event()
            
            result = None
            def dispersy_thread():
                try:
                    result = func(*args, **kwargs)
                    
                finally:
                    event.set()
                
            _register_task(dispersy_thread)
            
            if event.wait(100):
                return result
            
            print_stack()
            print >> sys.stderr, "GOT TIMEOUT ON forceAndReturnDispersyThread", func.__name__
        else:
            return func(*args, **kwargs)
            
    invoke_func.__name__ = func.__name__
    return invoke_func

class ChannelCommunity(Community):
    """
    Each user owns zero or more ChannelCommunities that other can join and use to discuss.
    """
    def __init__(self, master):
        self.integrate_with_tribler = False
        self._channel_id = None
        self._last_sync_range = None
        self._last_sync_space_remaining = 0
        
        super(ChannelCommunity, self).__init__(master)

        global _register_task
        _register_task = self._dispersy.callback.register

        if self.integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, PeerDBHandler
            from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
            from Tribler.Core.CacheDB.Notifier import Notifier
            
            # tribler channelcast database
            self._peer_db = PeerDBHandler.getInstance()
            self._channelcast_db = ChannelCastDBHandler.getInstance()
            
            # torrent collecting
            self._rtorrent_handler = RemoteTorrentHandler.getInstance()
            
            # notifier
            self._notifier = Notifier.getInstance().notify
    
            # tribler channel_id
            self._channel_id = self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(self._master_member.mid),))

            #modification_types
            self._modification_types = self._channelcast_db.modification_types
        
        else:
            def post_init():
                try:
                    message = self._get_latest_channel_message()
                    if message:
                        self._channel_id = self._master_member.mid
                except:
                    pass
            # call this after the init is completed and the community is attached to dispersy
            _register_task(post_init)

            from Tribler.community.allchannel.community import ChannelCastDBStub
            self._channelcast_db = ChannelCastDBStub(self._dispersy)
        
    def initiate_meta_messages(self):
        if self.integrate_with_tribler:
            disp_on_channel = self._disp_on_channel
            disp_on_torrent = self._disp_on_torrent
            disp_on_playlist = self._disp_on_playlist
            disp_on_comment = self._disp_on_comment
            disp_on_modification = self._disp_on_modification
            disp_on_playlist_torrent = self._disp_on_playlist_torrent
            disp_on_warning = self._disp_on_warning
            disp_on_mark_torrent = self._disp_on_mark_torrent
        else:
            def dummy_function(*params):
                return
            
            def handled_function(messages):
                for _ in messages:
                    log("dispersy.log", "handled-barter-record",type = "torrent")
                        
            def handled_channel_function(messages):
                dprint("handled-channel-record", stack = True)
                log("dispersy.log", "received-channel-record")
                self._channel_id = self._master_member.mid
            
            disp_on_channel = handled_channel_function
            disp_on_torrent = handled_function
            disp_on_playlist = dummy_function
            disp_on_comment = dummy_function
            disp_on_modification = dummy_function
            disp_on_playlist_torrent = dummy_function
            disp_on_warning = dummy_function
            disp_on_mark_torrent = dummy_function
        
        return [Message(self, u"channel", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=130), CommunityDestination(node_count=10), ChannelPayload(), self._disp_check_channel, disp_on_channel),
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=129), CommunityDestination(node_count=10), TorrentPayload(), self._disp_check_torrent, disp_on_torrent, delay=3.0),
                Message(self, u"playlist", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), PlaylistPayload(), self._disp_check_playlist, disp_on_playlist, delay=3.0),
                Message(self, u"comment", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), CommentPayload(), self._disp_check_comment, disp_on_comment, delay=3.0),
                Message(self, u"modification", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), ModificationPayload(), self._disp_check_modification, disp_on_modification, delay=3.0),
                Message(self, u"playlist_torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), PlaylistTorrentPayload(), self._disp_check_playlist_torrent, disp_on_playlist_torrent, delay=3.0),
                Message(self, u"warning", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), WarningPayload(), self._disp_check_warning, disp_on_warning, delay=3.0),
                Message(self, u"mark_torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CommunityDestination(node_count=10), MarkTorrentPayload(), self._disp_check_mark_torrent, disp_on_mark_torrent, delay=3.0),
                Message(self, u"missing-channel", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingChannelPayload(), self._disp_check_missing_channel, self._disp_on_missing_channel),
                ]

#    @property
#    def dispersy_sync_bloom_filters(self):
#        #return self.bloom_option_1()
#        log("dispersy.log", "syncing-bloom-filters", nrfilters = len(self._sync_ranges))
#        
#        return self.bloom_option_2()
#        
#    def bloom_option_1(self):
#        #did we choose a sync range in the previous run where we got data?
#        if self._last_sync_range and self._last_sync_space_remaining != self._last_sync_range.space_remaining:
#            #stick to this one, try again
#            index = self._sync_ranges.index(self._last_sync_range)
#        else:
#            #first time or choose a different one
#            lambd = 1.0 / (len(self._sync_ranges) / 2.0)
#            index = min(int(expovariate(lambd)), len(self._sync_ranges) - 1)
#        
#        sync_range = self._sync_ranges[index]
#        time_high = 0 if index == 0 else self._sync_ranges[index - 1].time_low
#        
#        self._last_sync_range = None
#        self._last_sync_space_remaining = None
#        if index != 0: #first sync range will probably always have 'new' data, do not stick to that one  
#            self._last_sync_range = sync_range
#            self._last_sync_space_remaining = sync_range.space_remaining
#            
#        return [(sync_range.time_low, time_high, choice(sync_range.bloom_filters))]        
#    
#    def bloom_option_2(self):
#        index = randint(0, len(self._sync_ranges) - 1)
#        sync_range = self._sync_ranges[index]
#        time_high = 0 if index == 0 else self._sync_ranges[index - 1].time_low
#        
#        self._last_sync_range = None
#        self._last_sync_space_remaining = None
#        if index != 0: #first sync range will probably always have 'new' data, do not stick to that one  
#            self._last_sync_range = sync_range
#            self._last_sync_space_remaining = sync_range.space_remaining
#            
#        return [(sync_range.time_low, time_high, choice(sync_range.bloom_filters))]
    
    @property    
    def dispersy_sync_bloom_filter_error_rate(self):
        return 0.3
    
    @property
    def dispersy_candidate_online_scores(self):
        return []
    
    @property
    def dispersy_candidate_direct_observation_score(self):
        return 1

    @property
    def dispersy_candidate_indirect_observation_score(self):
        return 1
    
    @property
    def dispersy_sync_interval(self):
        return 5.0
    
    @property
    def dispersy_sync_response_limit(self):
        return 50 * 1024

    def initiate_conversions(self):
        return [DefaultConversion(self), ChannelConversion(self)]

    def create_channel(self, name, description, store=True, update=True, forward=True):
        self._disp_create_channel(name, description, store, update, forward)
    
    @forceDispersyThread
    def _disp_create_channel(self, name, description, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"channel")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(name, description))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_channel(self, messages):
        log("dispersy.log", "only-accepting", keys = self._meta_messages.keys())
        
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                log("dispersy.log", "not-accepted")
                yield DelayMessageByProof(message)
                continue
            
            log("dispersy.log", "accepted")
            yield message

    def _disp_on_channel(self, messages):
        for message in messages:
            if __debug__: dprint(message)

            authentication_member = message.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
            self._channel_id = self._channelcast_db.on_channel_from_dispersy(self._master_member.mid, peer_id, message.payload.name, message.payload.description)

    def _disp_create_torrent_from_torrentdef(self, torrentdef, timestamp, store=True, update=True, forward=True):
        files = torrentdef.get_files_as_unicode_with_length()
        return self._disp_create_torrent(torrentdef.get_infohash(), timestamp, unicode(torrentdef.get_name()), tuple(files), torrentdef.get_trackers_as_single_tuple(), store, update, forward)

    def _disp_create_torrent(self, infohash, timestamp, name, files, trackers, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"torrent")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(infohash, timestamp, name, files, trackers))
        self._dispersy.store_update_forward([message], store, update, forward)
        
        log("dispersy.log", "created-barter-record", size = len(message.packet)) # TODO: should change this to something more specific to channels
        return message
    
    def _disp_create_torrents(self, torrentlist, store=True, update=True, forward=True):
        messages = []
        
        meta = self.get_meta_message(u"torrent")
        for infohash, timestamp, name, files, trackers in torrentlist:
            message = meta.implement(meta.authentication.implement(self._my_member),
                                     meta.distribution.implement(self.claim_global_time()),
                                     meta.destination.implement(),
                                     meta.payload.implement(infohash, timestamp, name, files, trackers))
            
            log("dispersy.log", "created-torrent-record", size = len(message.packet))
            log("dispersy.log", "created-barter-record")
            messages.append(message)
            
        self._dispersy.store_update_forward(messages, store, update, forward)
        return messages

    def _disp_check_torrent(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
                
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            yield message

    def _disp_on_torrent(self, messages):
        torrentlist = []
        infohashes = set()
        addresses = set()
        
        for message in messages:
            if __debug__: dprint(message)
            
            dispersy_id = message.packet_id
            torrentlist.append((self._channel_id, dispersy_id, message.payload.infohash, message.payload.timestamp, message.payload.name, message.payload.files, message.payload.trackers))
            infohashes.add(message.payload.infohash)
            
            addresses.add(message.address)
        
        permids = set()
        for address in addresses:
            for member in self.get_members_from_address(address):
                permids.add(member.public_key)
        
        self._channelcast_db.on_torrents_from_dispersy(torrentlist)
        for infohash in infohashes:
            for permid in permids:
                self._rtorrent_handler.download_torrent(permid, infohash, None ,2)

    #create, check or receive playlists
    def create_playlist(self, name, description, infohashes = [], store=True, update=True, forward=True):
        def dispersy_thread():
            message = self._disp_create_playlist(name, description)
            self._disp_create_playlist_torrents(infohashes, message, store, update, forward)
    
        self._register_task(dispersy_thread)

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
            
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            yield message

    def _disp_on_playlist(self, messages):
        for message in messages:
            if __debug__: dprint(message)
            dispersy_id = message.packet_id
            
            self._channelcast_db.on_playlist_from_dispersy(self._channel_id, dispersy_id, message.payload.name, message.payload.description)

    #create, check or receive comments
    @forceDispersyThread
    def create_comment(self, text, timestamp, reply_to, reply_after, playlist_id, infohash, store=True, update=True, forward=True):
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

    @forceDispersyThread
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
            
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            yield message
    
    def _disp_on_comment(self, messages):
        for message in messages:
            if __debug__: dprint(message)

            dispersy_id = message.packet_id
            
            authentication_member = message.authentication.member
            if authentication_member == self._my_member:
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
    @forceDispersyThread
    def modifyChannel(self, modifications, store=True, update=True, forward=True):
        latest_modifications = {}
        for type, value in modifications.iteritems():
            type = unicode(type)
            type_id = self._modification_types[type]
            latest_modifications[type] = self._get_latest_modification_from_channel_id(type_id)
        modification_on_message = self._get_latest_channel_message()
            
        for type, value in modifications.iteritems():
            type = unicode(type)
            self._disp_create_modification(type, value, modification_on_message, latest_modifications[type], store, update, forward)
    
    @forceDispersyThread
    def modifyPlaylist(self, playlist_id, modifications, store=True, update=True, forward=True):
        latest_modifications = {}
        for type, value in modifications.iteritems():
            type = unicode(type)
            type_id = self._modification_types[type]
            latest_modifications[type] = self._get_latest_modification_from_playlist_id(playlist_id, type_id)
        
        modification_on_message = self._get_message_from_playlist_id(playlist_id)
        for type, value in modifications.iteritems():
            type = unicode(type)
            self._disp_create_modification(type, value, modification_on_message, latest_modifications[type], store, update, forward)
    
    @forceDispersyThread
    def modifyTorrent(self, channeltorrent_id, modifications, store=True, update=True, forward=True):
        latest_modifications = {}
        for type, value in modifications.iteritems():
            type = unicode(type)
            type_id = self._modification_types[type]
            latest_modifications[type] = self._get_latest_modification_from_torrent_id(channeltorrent_id, type_id)
        
        modification_on_message = self._get_message_from_torrent_id(channeltorrent_id)
        for type, value in modifications.iteritems():
            type = unicode(type)
            self._disp_create_modification(type, value, modification_on_message, latest_modifications[type], store, update, forward)
        
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
            
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
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
            playlist_id = channeltorrent_id = None
            if message_name ==  u"torrent":
                channeltorrent_id = self._get_torrent_id_from_message(modifying_dispersy_id)
                
            elif message_name == u"playlist":
                playlist_id = self._get_playlist_id_from_message(modifying_dispersy_id)
            
            #always store metadata
            self._channelcast_db.on_metadata_from_dispersy(message_name, channeltorrent_id, playlist_id, self._channel_id, dispersy_id, mid_global_time, modification_type_id, modification_value, prev_modification_id, prev_modification_global_time)
            
            #see if this is new information, if so call on_X_from_dispersy to update local 'cached' information
            if message_name ==  u"torrent":
                latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type_id)
                if latest.packet_id == dispersy_id:
                    self._channelcast_db.on_torrent_modification_from_dispersy(channeltorrent_id, modification_type, modification_value)
        
            elif message_name == u"playlist":
                latest = self._get_latest_modification_from_playlist_id(playlist_id, modification_type_id)
                if latest.packet_id == dispersy_id:
                    self._channelcast_db.on_playlist_modification_from_dispersy(playlist_id, modification_type, modification_value)
        
            elif message_name == u"channel":
                latest = self._get_latest_modification_from_channel_id(modification_type_id)
                if latest.packet_id == dispersy_id:
                    self._channelcast_db.on_channel_modification_from_dispersy(self._channel_id, modification_type, modification_value)

            
    #create, check or receive playlist_torrent messages
    @forceDispersyThread
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
    
    def _disp_check_playlist_torrent(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            accepted, proof = self._timeline.check(message)
            if not accepted:
                raise DelayMessageByProof(message)
            yield message
    
    def _disp_on_playlist_torrent(self, messages):
        for message in messages:
            playlist_dispersy_id = message.payload.playlist.packet_id
            
            self._channelcast_db.on_playlist_torrent(playlist_dispersy_id, message.payload.infohash)
            
    #check or receive missing channel messages
    def _disp_check_missing_channel(self, messages):
        for message in messages:
            yield message

    def _disp_on_missing_channel(self, messages):
        channelmessage = self._get_latest_channel_message()
        for message in messages:
            log("dispersy.log", "sending-channel-record", address = message.address, packet = channelmessage.packet) # TODO: maybe move to barter.log

            self._dispersy._send([message.address], [channelmessage.packet])
            
    #check or receive warning messages
    @forceDispersyThread
    def _disp_create_warning(self, text, timestamp, cause, store=True, update=True, forward=True):
        message = cause.load_message()
        mid = message.authentication.member.mid
        global_time = message.distribution.global_time
        
        meta = self.get_meta_message(u"warning")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(text, timestamp, cause, mid, global_time))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_warning(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            accepted, proof = self._timeline.check(message)
            if not accepted:
                raise DelayMessageByProof(message)
            yield message
            
    def _disp_on_warning(self, messages):
        for message in messages:
            if __debug__: dprint(message)

            dispersy_id = message.packet_id
            
            authentication_member = message.authentication.member
            if authentication_member == self._my_member:
                by_peer_id = None
            else:
                by_peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
                
            cause = message.payload.packet.packet_id
            
            cause_message = message.payload.packet.load_message()
            authentication_member = cause_message.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
            
            self._channelcast_db.on_warning(self._channel_id, dispersy_id, peer_id, by_peer_id, cause, message.payload.text, message.payload.timestamp)
            
    #check or receive torrent_mark messages
    @forceDispersyThread
    def _disp_create_mark_torrent(self, infohash, type, timestamp, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"mark_torrent")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(infohash, type, timestamp))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_mark_torrent(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            accepted, proof = self._timeline.check(message)
            if not accepted:
                raise DelayMessageByProof(message)
            yield message
    
    def _disp_on_mark_torrent(self, messages):
        for message in messages:
            global_time = message.distribution.global_time
            
            authentication_member = message.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
            self._channelcast_db.on_mark_torrent(self._channel_id, global_time, peer_id, message.payload.infohash, message.payload.type, message.payload.timestamp)
    
    #AllChannel functions
    def selectTorrentsToCollect(self, infohashes):
        infohashes = list(infohashes)
        
        collect = []
        haveTorrents = self._channelcast_db.hasTorrents(self._channel_id, infohashes)
        for i in range(len(infohashes)):
            if not haveTorrents[i]:
                collect.append(infohashes[i])
        return collect
    
    #helper functions
    @forceAndReturnDispersyThread
    def _get_latest_channel_message(self):
        channel_meta = self.get_meta_message(u"channel")

        # 1. get the packet
        try:
            packet, packet_id = self._dispersy.database.execute(u"SELECT packet, id FROM sync WHERE meta_message = ? ORDER BY global_time DESC LIMIT 1",
                                                                (channel_meta.database_id,)).next()
        except StopIteration:
            raise RuntimeError("Could not find requested packet")

        message = self._dispersy.convert_packet_to_message(str(packet))
        if message:
            assert message.name == u"channel", "Expecting a 'channel' message"
            message.packet_id = packet_id
        else:
            raise RuntimeError("unable to convert packet")

        return message
        
    def _get_message_from_playlist_id(self, playlist_id):
        assert isinstance(playlist_id, (int, long))
        
        # 1. get the dispersy identifier from the channel_id
        dispersy_id = self._channelcast_db.getPlaylist(playlist_id, ('dispersy_id',)).dispersy_id

        # 2. get the message
        message = self._get_message_from_dispersy_id(dispersy_id, 'playlist')
        return message
    
    def _get_playlist_id_from_message(self, dispersy_id):
        assert isinstance(dispersy_id, (int, long))
        return self._channelcast_db._db.fetchone(u"SELECT id FROM Playlists WHERE dispersy_id = ?", (dispersy_id,))
        
    def _get_message_from_torrent_id(self, torrent_id):
        assert isinstance(torrent_id, (int, long))

        # 1. get the dispersy identifier from the channel_id
        dispersy_id = self._channelcast_db.getTorrentFromChannelTorrentId(torrent_id, ['dispersy_id'])
        
        # 2. get the message
        message = self._get_message_from_dispersy_id(dispersy_id, "torrent")
        return message
    
    def _get_message_from_torrent_infohash(self, torrent_infohash):
        assert isinstance(torrent_infohash, str), 'infohash is a %s'%type(torrent_infohash)
        assert len(torrent_infohash) == 20, 'infohash has length %d'%len(torrent_infohash)

        # 1. get the dispersy identifier from the channel_id
        dispersy_id = self._channelcast_db.getTorrentFromChannelId(self._channel_id, torrent_infohash, ['dispersy_id'])
        
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
        
    @forceAndReturnDispersyThread
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
    
    @forceAndReturnDispersyThread
    def _get_message_from_dispersy_id(self, dispersy_id, messagename):
        # 1. get the packet
        try:
            packet, packet_id = self._dispersy.database.execute(u"SELECT packet, id FROM sync WHERE id = ?", (dispersy_id,)).next()
        except StopIteration:
            raise RuntimeError("Unknown dispersy_id")

        message = self._dispersy.convert_packet_to_message(str(packet))
        if message:
            assert not messagename or message.name == messagename
            message.packet_id = packet_id
        else:
            raise RuntimeError("unable to convert packet")

        return message
