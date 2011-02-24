from conversion import ChannelConversion
from payload import ChannelPayload, TorrentPayload, PlaylistPayload, CommentPayload, ModificationPayload

from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler

from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.authentication import MemberAuthentication
from Tribler.Core.dispersy.resolution import LinearResolution
from Tribler.Core.dispersy.distribution import FullSyncDistribution
from Tribler.Core.dispersy.destination import CommunityDestination

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class ChannelCommunity(Community):
    """
    Each user owns zero or more ChannelCommunities that other can join and use to discuss.
    """
    def __init__(self, cid):
        super(ChannelCommunity, self).__init__(cid)

        # tribler torrent database
        self._channelcast_db = ChannelCastDBHandler.getInstance()

        # tribler remote torrent handler
        self._remote_torrent_handler = RemoteTorrentHandler.getInstance()

        # available conversions
        self.add_conversion(ChannelConversion(self), True)

    def initiate_meta_messages(self):
        return [Message(self, u"channel", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), ChannelPayload(), self.check_channel, self.on_channel),
                Message(self, u"torrent", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"random-order"), CommunityDestination(node_count=10), TorrentPayload(), self.check_torrent, self.on_torrent),
                Message(self, u"playlist", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), PlaylistPayload(), self.check_playlist, self.on_playlist),
                Message(self, u"comment", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), CommentPayload(), self.check_comment, self.on_comment),
                Message(self, u"modification", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), ModificationPayload(), self.check_modification, self.on_modification),
                ]

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
        channel_id = self._channelcast_db._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_id = ?", (dispersy_id,))

        self._channelcast_db.on_torrent_from_dispersy(channel_id, dispersy_id, message.payload.infohash, message.payload.timestamp)

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

    def create_comment(self, text, reply_to, reply_after, update_locally=True, store_and_forward=True):
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)
        meta = self.get_meta_message(u"comment")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(text, reply_to, reply_after))

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback(("", -1), message)

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def check_comment(self, address, message):
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")

    def on_comment(self, address, message):
        if __debug__: dprint(message)
        # --> Channelcastdbhandler.on_comment_from_dispersy

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
        # --> Channelcastdbhandler.on_torrent_modification_from_dispersy
        # --> Channelcastdbhandler.on_playlist_modification_from_dispersy
        # --> Channelcastdbhandler.on_comment_modification_from_dispersy
