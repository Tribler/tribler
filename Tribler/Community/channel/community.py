from conversion import ChannelConversion
from payload import ChannelPayload, TorrentPayload, PlaylistPayload, CommentPayload, ModificationPayload, PlaylistTorrentPayload, MissingChannelPayload

from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import bin2str

from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler

from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.message import Message, DropMessage, DelayMessageReqChannelMessage
from Tribler.Core.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.Core.dispersy.resolution import LinearResolution, PublicResolution
from Tribler.Core.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.Core.dispersy.destination import CommunityDestination, AddressDestination
from Tribler.Core.dispersy.member import MyMember

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class ChannelCommunity(Community):
    """
    Each user owns zero or more ChannelCommunities that other can join and use to discuss.
    """
    def __init__(self, cid, master_key):
        super(ChannelCommunity, self).__init__(cid, master_key)

        # tribler channelcast database
        self._channelcast_db = ChannelCastDBHandler.getInstance()

        # tribler channel_id
        self.channel_id = self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(self._cid),))

    def initiate_meta_messages(self):
        return [Message(self, u"channel", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), ChannelPayload(), self.check_channel, self.on_channel),
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"random-order"), CommunityDestination(node_count=10), TorrentPayload(), self.check_torrent, self.on_torrent),
                Message(self, u"playlist", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), PlaylistPayload(), self.check_playlist, self.on_playlist),
                Message(self, u"comment", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), CommentPayload(), self.check_comment, self.on_comment),
                Message(self, u"modification", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), ModificationPayload(), self.check_modification, self.on_modification),
                Message(self, u"playlist_torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), PlaylistTorrentPayload(), self.check_playlist_torrent, self.on_playlist_torrent),
                Message(self, u"missing-channel", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingChannelPayload(), self.check_missing_channel, self.on_missing_channel),
                ]

    def initiate_conversions(self):
        return [DefaultConversion(self), ChannelConversion(self)]

    def create_channel(self, name, description, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"channel")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(name, description))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def check_channel(self, messages):
        for message in messages:
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def on_channel(self, messages):
        for message in messages:
            if __debug__: dprint(message)

            authentication_member = message.authentication.member
            if isinstance(authentication_member, MyMember):
                peer_id = None
            else:
                peer_id = self._channelcast_db._db.getPeerID(authentication_member.public_key)

            self._channelcast_db.on_channel_from_dispersy(self._cid, peer_id, message.payload.name, message.payload.description)
            self.channel_id = self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(self._cid),))

    def create_torrent(self, infohash, timestamp, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"torrent")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(infohash, timestamp))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message
    
    def create_torrents(self, torrentlist, store=True, update=True, forward=True):
        messages = []
        
        meta = self.get_meta_message(u"torrent")
        for infohash, timestamp in torrentlist:
            message = meta.implement(meta.authentication.implement(self._my_member),
                                     meta.distribution.implement(self._timeline.global_time),
                                     meta.destination.implement(),
                                     meta.payload.implement(infohash, timestamp))
            messages.append(message)
        self._dispersy.store_update_forward(messages, store, update, forward)
        return messages

    def check_torrent(self, messages):
        for message in messages:
            if not self.channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
                
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def on_torrent(self, messages):
        torrentlist = []
        for message in messages:
            if __debug__: dprint(message)
            dispersy_id = message.packet_id
            torrentlist.append((self.channel_id, dispersy_id, message.payload.infohash, message.payload.timestamp))
        self._channelcast_db.on_torrents_from_dispersy(torrentlist)

    def create_playlist(self, name, description, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"playlist")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(name, description))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def check_playlist(self, messages):
        for message in messages:
            if not self.channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def on_playlist(self, messages):
        for message in messages:
            if __debug__: dprint(message)
            dispersy_id = message.packet_id
            self._channelcast_db.on_playlist_from_dispersy(self.channel_id, dispersy_id, message.payload.name, message.payload.description)

    def create_comment(self, text, timestamp, reply_to, reply_after, playlist, infohash, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"comment")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(text, timestamp, reply_to, reply_after, playlist, infohash))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def check_comment(self, messages):
        for message in messages:
            if not self.channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message
    
    def on_comment(self, messages):
        for message in messages:
            if __debug__: dprint(message)

            dispersy_id = message.packet_id
            
            authentication_member = message.authentication.member
            if isinstance(authentication_member, MyMember):
                peer_id = None
            else:
                peer_id = self._channelcast_db._db.getPeerID(authentication_member.public_key)
            
            playlist_dispersy_id = None
            if message.payload.playlist:
                playlist_dispersy_id = message.payload.playlist.packet_id
            self._channelcast_db.on_comment_from_dispersy(self.channel_id, dispersy_id, peer_id, message.payload.text, message.payload.timestamp, message.payload.reply_to, message.payload.reply_after, playlist_dispersy_id, message.payload.infohash)
        
    def create_modification(self, modification, modification_on, latest_modification, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"modification")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(modification, modification_on, latest_modification))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def check_modification(self, messages):
        for message in messages:
            if not self.channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay by proof")
                continue
            yield message

    def on_modification(self, messages):
        for message in messages:
            if __debug__: dprint(message)
            message_name = message.payload.modification_on.name
        
            modification_dict = message.payload.modification
            modifying_dispersy_id = message.payload.modification_on.packet_id
            latest_dispersy_modifier = message.packet_id
        
            if message_name ==  u"torrent":
                self._channelcast_db.on_torrent_modification_from_dispersy(modifying_dispersy_id, modification_dict, latest_dispersy_modifier)
        
            elif message_name == u"playlist":
                self._channelcast_db.on_playlist_modification_from_dispersy(modifying_dispersy_id, modification_dict, latest_dispersy_modifier)
        
            elif message_name == u"channel":
                self._channelcast_db.on_channel_modification_from_dispersy(self._cid, modification_dict, latest_dispersy_modifier)
            
    def create_playlist_torrent(self, infohash, playlistmessage, update_locally=True, store_and_forward=True):
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)
        meta = self.get_meta_message(u"playlist_torrent")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(infohash, playlistmessage))

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback([message])

        return message
    
    def check_playlist_torrent(self, address, messages):
        for message in messages:
            if not self.channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue
            
            if not self._timeline.check(message):
                raise DropMessage("TODO: implement delay by proof")
            yield message
    
    def on_playlist_torrent(self, address, messages):
        for message in messages:
            
            playlist_dispersy_id = message.payload.playlist.packet_id
            self._channelcast_db.on_playlist_torrent(playlist_dispersy_id, message.payload.infohash)
            
    def check_missing_channel(self, address, messages):
        for message in messages:
            if not self._timeline.check(message):
                raise DropMessage("TODO: implement delay by proof")
            yield message

    def on_missing_channel(self, address, messages):
        #send message?
        pass