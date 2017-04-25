from twisted.internet.defer import inlineCallbacks

from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.Community.Channel.channel_test_base import ChannelTestBase

TEST_CHANNEL_NAME = "TestName"
TEST_CHANNEL_DESC = "TestDescription"
TEST_TORRENT_INFOHASH = "zyxwv" * 4


class TestChannelCommunity(ChannelTestBase):

    """Outline and design:
        - In these unittests Node 1 has all of the data and
          Node 2 receives all of the data.

        - Node 1 and 2 have seperate Dispersy's [and Sessions].
    """

    @blocking_call_on_reactor_thread
    def test_db_init(self):
        """Initialization should come with channelcast
            and peer databases.
        """
        self.assertIsNotNone(self.community1._channelcast_db)
        self.assertIsNotNone(self.community1._peer_db)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_create_channel(self):
        """When a channel is created its name, description and
            channel id should be set locally and remotely.
        """
        self.community1.create_channel(TEST_CHANNEL_NAME, TEST_CHANNEL_DESC)

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        self.assertIsNotNone(self.community1.get_channel_id())
        self.assertEqual(self.community1.get_channel_name(), TEST_CHANNEL_NAME)
        self.assertEqual(
            self.community1.get_channel_description(), TEST_CHANNEL_DESC)
        self.assertIsNotNone(self.community2.get_channel_id())
        c2chan = self.community2._channelcast_db.getChannel(
            self.community2.get_channel_id())
        self.assertEqual(c2chan[2], TEST_CHANNEL_NAME)
        self.assertEqual(c2chan[3], TEST_CHANNEL_DESC)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_default_channel_mode(self):
        """The master member should have all permissions,
            a random stranger should not. By default all
            channels should be created closed.
        """
        self.community1.create_channel(TEST_CHANNEL_NAME, TEST_CHANNEL_DESC)

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        self.assertListEqual([ChannelCommunity.CHANNEL_CLOSED, True],
                             list(self.community1.get_channel_mode()))
        self.assertListEqual([ChannelCommunity.CHANNEL_CLOSED, False],
                             list(self.community2.get_channel_mode()))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_change_channel_mode(self):
        """When the channel mode is changed, it should propagate
            locally and remotely.
        """
        self.community1.create_channel(TEST_CHANNEL_NAME, TEST_CHANNEL_DESC)

        # Order of the test list is important, as
        # channels start closed.
        for mode in [ChannelCommunity.CHANNEL_OPEN,
                     ChannelCommunity.CHANNEL_SEMI_OPEN,
                     ChannelCommunity.CHANNEL_CLOSED]:
            self.community1.set_channel_mode(mode)

            # Allow the packets to be processed
            yield self._allow_packet_delivery()

            self.assertListEqual([mode, True],
                                 list(self.community1.get_channel_mode()))
            self.assertListEqual([mode, False],
                                 list(self.community2.get_channel_mode()))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_create_torrent(self):
        """When a torrent is created/added, it should propagate
            locally and remotely.
        """
        self.community1.create_channel(TEST_CHANNEL_NAME, TEST_CHANNEL_DESC)
        self.community1._disp_create_torrent(TEST_TORRENT_INFOHASH,
                                             1,
                                             u"fakeTorrent",
                                             ((u"fakeFile", 0),),
                                             ("http://localhost/announce",))

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        self.assertTrue(
            self.community1._channelcast_db.hasTorrent(
                self.community1._channel_id,
                TEST_TORRENT_INFOHASH))
        self.assertTrue(
            self.community2._channelcast_db.hasTorrent(
                self.community1._channel_id,
                TEST_TORRENT_INFOHASH))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_remove_torrent(self):
        """When a torrent is removed, it should propagate
            locally and remotely.
        """
        self.test_create_torrent()

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        # Get the Torrent message packet_id, conveniently
        # this is the last message in the sync database.
        self.community1.remove_torrents(
            [self._get_last_synced_packet_id(self.dispersy1, self.community1)])

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        self.assertFalse(
            self.community1._channelcast_db.hasTorrent(
                self.community1._channel_id,
                TEST_TORRENT_INFOHASH))
        self.assertFalse(
            self.community2._channelcast_db.hasTorrent(
                self.community1._channel_id,
                TEST_TORRENT_INFOHASH))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_create_playlist(self):
        """When a playlist is created, it should propagate
            locally and remotely.
        """
        self.community1.create_channel(TEST_CHANNEL_NAME, TEST_CHANNEL_DESC)
        self.community1.create_playlist("TestPlaylist",
                                        "TestPlaylistDescription",
                                        [TEST_TORRENT_INFOHASH])

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        for community in [self.community1, self.community2]:
            results = community._channelcast_db.getPlaylistsFromChannelId(
                self.community1._channel_id,
                ['PlaylistTorrents.playlist_id'])
            pid = results[0][1]
            self.assertIsNotNone(pid)
            tid = community._channelcast_db.torrent_db.getTorrentID(
                TEST_TORRENT_INFOHASH)
            self.assertTrue(
                community._channelcast_db.playlistHasTorrent(pid, tid))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_create_playlist_notorrent(self):
        """Empty playlists should also be allowed.
        """
        self.community1.create_channel(TEST_CHANNEL_NAME, TEST_CHANNEL_DESC)
        self.community1.create_playlist("TestPlaylist",
                                        "TestPlaylistDescription",
                                        [])

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        for community in [self.community1, self.community2]:
            results = community._channelcast_db.getPlaylistsFromChannelId(
                self.community1._channel_id,
                ['PlaylistTorrents.playlist_id'])
            pid = results[0][1]
            self.assertIsNotNone(pid)
            tid = community._channelcast_db.torrent_db.getTorrentID(
                TEST_TORRENT_INFOHASH)
            self.assertFalse(
                community._channelcast_db.playlistHasTorrent(pid, tid))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_remove_playlist(self):
        """When a playlist is removed, it should propagate
            locally and remotely.
        """
        self.test_create_playlist()

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        # Get the Playlist message packet_id, conveniently
        # this is the last message in the sync database.
        self.community1.remove_playlists(
            [self._get_last_synced_packet_id(self.dispersy1, self.community1)])

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        for community in [self.community1, self.community2]:
            results = community._channelcast_db.getPlaylistsFromChannelId(
                self.community1._channel_id,
                ['PlaylistTorrents.playlist_id'])
            self.assertIsNone(results[0][0])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_create_comment(self):
        """Create a comment on a playlist.
            Outlandish unicode characters should be supported.
            Should be propagated locally and remotely.
        """
        self.test_create_playlist()

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        results = self.community1._channelcast_db.getPlaylistsFromChannelId(
            self.community1._channel_id,
            ['PlaylistTorrents.playlist_id'])
        pid = results[0][1]
        unistr = " ".join([unichr(9959), unichr(39764), unichr(9959), ''])
        self.community1.create_comment(
            unistr, 1, None, None, pid, TEST_TORRENT_INFOHASH)

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        for community in [self.community1, self.community2]:
            received, _ = community._channelcast_db.getCommentsFromPlayListId(
                pid, ['comment', 'time_stamp'])[0]
            self.assertEqual(unistr, received)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_create_comment_reply(self):
        """Replies should also be allowed.
            Should be propagated locally and remotely.
        """
        self.test_create_playlist()
        results = self.community1._channelcast_db.getPlaylistsFromChannelId(
            self.community1._channel_id,
            ['PlaylistTorrents.playlist_id'])
        pid = results[0][1]
        unistr = " ".join([unichr(9959), unichr(39764), unichr(9959), ''])
        self.community1.create_comment(
            unistr, 1, None, None, pid, TEST_TORRENT_INFOHASH)

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        (did, _), _ = self.community1._channelcast_db.getCommentsFromPlayListId(
            pid, ['Comments.id', 'time_stamp'])
        unistr = "".join(
            [unichr(10013), " ", unichr(20840), unichr(33021), unichr(10013), ''])
        self.community1.create_comment(
            unistr, 1, did, did, pid, TEST_TORRENT_INFOHASH)

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        for community in [self.community1, self.community2]:
            received = [a for (
                a, _) in community._channelcast_db.getCommentsFromPlayListId(pid,
                                                                             ['comment',
                                                                              'time_stamp'])]
            self.assertIn(unistr, received)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_remove_comment(self):
        """When a comment is removed, it should propagate
            locally and remotely.
        """
        self.test_create_playlist()
        results = self.community1._channelcast_db.getPlaylistsFromChannelId(
            self.community1._channel_id,
            ['PlaylistTorrents.playlist_id'])
        pid = results[0][1]
        unistr = " ".join([unichr(9959), unichr(39764), unichr(9959), ''])
        self.community1.create_comment(
            unistr, 1, None, None, pid, TEST_TORRENT_INFOHASH)

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        results = self.community1._channelcast_db.getPlaylistsFromChannelId(
            self.community1._channel_id,
            ['PlaylistTorrents.playlist_id'])
        pid = results[0][1]
        self.community1.remove_comment(
            self._get_last_synced_packet_id(self.dispersy1, self.community1))

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        for community in [self.community1, self.community2]:
            received = community._channelcast_db.getCommentsFromPlayListId(
                pid, ['comment', 'time_stamp'])
            self.assertFalse(received)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_modify_channel(self):
        """Test modifying the name and description
            of a channel separately.
        """
        self.test_create_channel()

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        newname = unichr(12420) + unichr(12388)
        newdesc = unichr(12513) + unichr(12452) + unichr(
            12489) + unichr(12459) + unichr(12501) + unichr(12455)
        self.community1.modifyChannel({'name': newname})

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        c1chan = self.community1._channelcast_db.getChannel(
            self.community1.get_channel_id())
        self.assertEqual(c1chan[2], newname)
        c2chan = self.community2._channelcast_db.getChannel(
            self.community2.get_channel_id())
        self.assertEqual(c2chan[2], newname)

        self.community1.modifyChannel({'description': newdesc})

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        c1chan = self.community1._channelcast_db.getChannel(
            self.community1.get_channel_id())
        self.assertEqual(c1chan[3], newdesc)
        c2chan = self.community2._channelcast_db.getChannel(
            self.community2.get_channel_id())
        self.assertEqual(c2chan[3], newdesc)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_modify_playlist(self):
        """Test modifying the name and description
            of a playlist separately.
        """
        self.test_create_playlist()
        results = self.community1._channelcast_db.getPlaylistsFromChannelId(
            self.community1._channel_id,
            ['PlaylistTorrents.playlist_id'])
        pid = results[0][1]

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        newname = unichr(33464) + unichr(32773)
        newdesc = unichr(33464) + unichr(22931)
        self.community1.modifyPlaylist(pid, {'name': newname})

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        c1chan = self.community1._channelcast_db.getPlaylist(
            pid, ['Playlists.name', 'Playlists.description'])
        self.assertEqual(c1chan[0], newname)
        c2chan = self.community2._channelcast_db.getPlaylist(
            pid, ['Playlists.name', 'Playlists.description'])
        self.assertEqual(c2chan[0], newname)

        self.community1.modifyPlaylist(pid, {'description': newdesc})

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        c1chan = self.community1._channelcast_db.getPlaylist(
            pid, ['Playlists.name', 'Playlists.description'])
        self.assertEqual(c1chan[1], newdesc)
        c2chan = self.community2._channelcast_db.getPlaylist(
            pid, ['Playlists.name', 'Playlists.description'])
        self.assertEqual(c2chan[1], newdesc)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_modify_torrent(self):
        """Test modifying the name and description
            of a torrent separately.
        """
        self.test_create_torrent()
        tid, = self.community1._channelcast_db.get_random_channel_torrents(
            ['ChannelTorrents.torrent_id'], 1)[0]

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        newname = unichr(12467) + unichr(12473) + unichr(12503) + unichr(12524)
        newdesc = unichr(21516) + unichr(20154)
        self.community1.modifyTorrent(tid, {'name': newname})

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        c1chan = self.community1._channelcast_db.getTorrentFromChannelTorrentId(
            tid, ['ChannelTorrents.name', 'ChannelTorrents.description'])
        self.assertEqual(c1chan[0], newname)
        c2chan = self.community2._channelcast_db.getTorrentFromChannelTorrentId(
            tid, ['ChannelTorrents.name', 'ChannelTorrents.description'])
        self.assertEqual(c2chan[0], newname)

        self.community1.modifyTorrent(tid, {'description': newdesc})

        # Allow the packets to be processed
        yield self._allow_packet_delivery()

        c1chan = self.community1._channelcast_db.getTorrentFromChannelTorrentId(
            tid, ['ChannelTorrents.name', 'ChannelTorrents.description'])
        self.assertEqual(c1chan[1], newdesc)
        c2chan = self.community2._channelcast_db.getTorrentFromChannelTorrentId(
            tid, ['ChannelTorrents.name', 'ChannelTorrents.description'])
        self.assertEqual(c2chan[1], newdesc)
