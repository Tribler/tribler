from conversion import ChannelConversion
from payload import ChannelPayload, TorrentPayload, PlaylistPayload, CommentPayload, ModificationPayload

from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import bin2str

from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler

from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.authentication import MemberAuthentication
from Tribler.Core.dispersy.resolution import LinearResolution
from Tribler.Core.dispersy.distribution import FullSyncDistribution
from Tribler.Core.dispersy.destination import CommunityDestination
from Tribler.Core.dispersy.member import MyMember

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class ChannelCommunity(Community):
    """
    Each user owns zero or more ChannelCommunities that other can join and use to discuss.
    """
    def __init__(self, cid, master_key):
        super(ChannelCommunity, self).__init__(cid, master_key)

        # tribler torrent database
        self._channelcast_db = ChannelCastDBHandler.getInstance()

        # tribler remote torrent handler
        self._remote_torrent_handler = RemoteTorrentHandler.getInstance()

        # tribler channel_id
        self.channel_id = self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(self._cid),))

    def initiate_meta_messages(self):
        return [Message(self, u"channel", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), ChannelPayload(), self.check_channel, self.on_channel),
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"random-order"), CommunityDestination(node_count=10), TorrentPayload(), self.check_torrent, self.on_torrent),
                Message(self, u"playlist", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), PlaylistPayload(), self.check_playlist, self.on_playlist),
                Message(self, u"comment", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), CommentPayload(), self.check_comment, self.on_comment),
                Message(self, u"modification", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), ModificationPayload(), self.check_modification, self.on_modification),
                ]

    def initiate_conversions(self):
        return [DefaultConversion(self), ChannelConversion(self)]

    def create_channel(self, name, description, update_locally=True, store_and_forward=True):
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)
        meta = self.get_meta_message(u"channel")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(name, description))

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback(("", -1), message)

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def check_channel(self, address, message):
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")

    def on_channel(self, address, message):
        if __debug__: dprint(message)
        
        authentication_member = message.authentication.member
        if isinstance(authentication_member, MyMember):
            peer_id = None
        else:
            peer_id = self._get_peerid_from_mid(authentication_member.public_key)
        
        self._channelcast_db.on_channel_from_dispersy(self._cid, peer_id, message.payload.name, message.payload.description)
        self.channel_id = self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (buffer(self._cid),))

    def create_torrent(self, infohash, timestamp, update_locally=True, store_and_forward=True):
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)
        meta = self.get_meta_message(u"torrent")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(infohash, timestamp))

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback(("", -1), message)

        return message

    def check_torrent(self, address, message):
        dprint(message)
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")

    def on_torrent(self, address, message):
        if __debug__: dprint(message)

        dispersy_id = message.packet_id
        self._channelcast_db.on_torrent_from_dispersy(self.channel_id, dispersy_id, message.payload.infohash, message.payload.timestamp)

    def create_playlist(self, name, description, update_locally=True, store_and_forward=True):
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)
        meta = self.get_meta_message(u"playlist")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(name, description))

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback(("", -1), message)

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def check_playlist(self, address, message):
        dprint(message)
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")

    def on_playlist(self, address, message):
        if __debug__: dprint(message)
        # --> Channelcastdbhandler.on_playlist_from_dispersy

    def create_comment(self, text, timestamp, reply_to, reply_after, update_locally=True, store_and_forward=True):
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)
        meta = self.get_meta_message(u"comment")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(text, timestamp, reply_to, reply_after))

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback(("", -1), message)

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def check_comment(self, address, message):
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")
    
    def _get_peerid_from_mid(self, mid):
        return self._channelcast_db._db.fetchone(u"SELECT peer_id FROM Peer WHERE permid = ?", (bin2str(mid),))
    
    def on_comment(self, address, message):
        if __debug__: dprint(message)
        
        dispersy_id = message.packet_id
        peer_id = self._get_peerid_from_mid(message.member.mid)
        
        self._channelcast_db.on_comment_from_dispersy(self.channel_id, dispersy_id, peer_id, message.payload.text, message.payload.timestamp, message.payload.reply_to, message.payload.reply_after)
        
    def create_modification(self, modification, modification_on, update_locally=True, store_and_forward=True):
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)
        meta = self.get_meta_message(u"modification")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(modification, modification_on))

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback(("", -1), message)

        return message

    def check_modification(self, address, message):
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")

    def on_modification(self, address, message):
        if __debug__: dprint(message)
        message_name = message.payload.modification_on.name
        
        modification_dict = message.payload.modification
        modifying_dispersy_id = message.payload.modification_on.packet_id
        
        if message_name ==  u"torrent":
            self._channelcast_db.on_torrent_modification_from_dispersy(modifying_dispersy_id, modification_dict)
        
        elif message_name == u"playlist":
            self._channelcast_db.on_playlist_modification_from_dispersy(modifying_dispersy_id, modification_dict)
        
        elif message_name == u"channel":
            self._channelcast_db.on_channel_modification_from_dispersy(self._cid, modification_dict)
