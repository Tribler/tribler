from binascii import unhexlify

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, TorrentDBHandler, VoteCastDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Test.Core.test_sqlitecachedbhandler import AbstractDB
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestChannelDBHandler(AbstractDB):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(TestChannelDBHandler, self).setUp()

        self.cdb = ChannelCastDBHandler(self.session)
        self.tdb = TorrentDBHandler(self.session)
        self.vdb = VoteCastDBHandler(self.session)
        self.cdb.votecast_db = self.vdb
        self.cdb.torrent_db = self.tdb

    def test_get_metadata_torrents(self):
        self.assertEqual(len(self.cdb.get_metadata_torrents()), 2)
        self.assertEqual(len(self.cdb.get_metadata_torrents(is_collected=False)), 1)

    def test_get_torrent_metadata(self):
        result = self.cdb.get_torrent_metadata(1)
        self.assertEqual(result, {"thumb_hash": unhexlify("1234")})
        self.assertIsNone(self.cdb.get_torrent_metadata(200))

    def test_get_dispersy_cid_from_channel_id(self):
        self.assertEqual(self.cdb.getDispersyCIDFromChannelId(1), "1")
        self.assertEqual(self.cdb.getDispersyCIDFromChannelId(3), "3")

    def test_get_channel_id_from_dispersy_cid(self):
        self.assertEqual(self.cdb.getChannelIdFromDispersyCID(1), 1)
        self.assertEqual(self.cdb.getChannelIdFromDispersyCID(3), 3)

    def test_get_count_max_from_channel_id(self):
        self.assertEqual(self.cdb.getCountMaxFromChannelId(1), (2, 1457809687))
        self.assertEqual(self.cdb.getCountMaxFromChannelId(2), (1, 1457809861))

    def test_search_channel(self):
        self.assertEqual(len(self.cdb.searchChannels("another")), 1)
        self.assertEqual(len(self.cdb.searchChannels("fancy")), 2)

    def test_get_channel(self):
        channel = self.cdb.getChannel(1)
        self.assertEqual(channel, (1, '1', u'Test Channel 1', u'Test', 3, 7, 5, 2, 1457795713, False))
        self.assertIsNone(self.cdb.getChannel(1234))

    def test_get_channels(self):
        channels = self.cdb.getChannels([1, 2, 3])
        self.assertEqual(len(channels), 3)

    def test_get_channels_by_cid(self):
        self.assertEqual(len(self.cdb.getChannelsByCID(["3"])), 0)

    def test_get_all_channels(self):
        self.assertEqual(len(self.cdb.getAllChannels()), 8)

    def test_get_new_channels(self):
        self.assertEqual(len(self.cdb.getNewChannels()), 1)

    def test_get_latest_updated(self):
        res = self.cdb.getLatestUpdated()
        self.assertEqual(res[0][0], 6)
        self.assertEqual(res[1][0], 7)
        self.assertEqual(res[2][0], 5)

    def test_get_most_popular_channels(self):
        res = self.cdb.getMostPopularChannels()
        self.assertEqual(res[0][0], 6)
        self.assertEqual(res[1][0], 7)
        self.assertEqual(res[2][0], 8)

    def test_get_my_subscribed_channels(self):
        res = self.cdb.getMySubscribedChannels(include_dispersy=True)
        self.assertEqual(len(res), 1)
        res = self.cdb.getMySubscribedChannels()
        self.assertEqual(len(res), 0)

    def test_get_channels_no_votecast(self):
        self.cdb.votecast_db = None
        self.assertFalse(self.cdb._getChannels("SELECT id FROM channels"))

    def test_get_my_channel_id(self):
        self.cdb._channel_id = 42
        self.assertEqual(self.cdb.getMyChannelId(), 42)
        self.cdb._channel_id = None
        self.assertEqual(self.cdb.getMyChannelId(), 1)

    def test_get_torrent_markings(self):
        res = self.cdb.getTorrentMarkings(3)
        self.assertEqual(res, [[u'test', 2, True], [u'another', 1, True]])
        res = self.cdb.getTorrentMarkings(1)
        self.assertEqual(res, [[u'test', 1, True]])

    def test_on_remove_playlist_torrent(self):
        self.assertEqual(len(self.cdb.getTorrentsFromPlaylist(1, ['Torrent.torrent_id'])), 1)
        self.cdb.on_remove_playlist_torrent(1, 1, str2bin('AA8cTG7ZuPsyblbRE7CyxsrKUCg='), False)
        self.assertEqual(len(self.cdb.getTorrentsFromPlaylist(1, ['Torrent.torrent_id'])), 0)

    def test_on_remove_torrent_from_dispersy(self):
        self.assertEqual(self.cdb.getTorrentFromChannelTorrentId(1, ['ChannelTorrents.dispersy_id']), 3)
        self.cdb.on_remove_torrent_from_dispersy(1, 3, False)
        self.assertIsNone(self.cdb.getTorrentFromChannelTorrentId(1, ['ChannelTorrents.dispersy_id']))

    def test_search_local_channels(self):
        """
        Testing whether the right results are returned when searching in the local database for channels
        """
        results = self.cdb.search_in_local_channels_db("fancy")
        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0][-1], 0.0)  # Relevance score of result should not be zero

        results = self.cdb.search_in_local_channels_db("fdajlkerhui")
        self.assertEqual(len(results), 0)
