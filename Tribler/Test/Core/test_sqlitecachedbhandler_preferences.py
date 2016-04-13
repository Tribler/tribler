from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Test.Core.test_sqlitecachedbhandler import AbstractDB
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMyPreferenceDBHandler(AbstractDB):

    def setUp(self):
        super(TestMyPreferenceDBHandler, self).setUp()

        self.tdb = TorrentDBHandler(self.session)
        self.mdb = MyPreferenceDBHandler(self.session)
        self.mdb._torrent_db = self.tdb

    def tearDown(self):
        self.mdb.close()
        self.mdb = None
        self.tdb.close()
        self.tdb = None

        super(TestMyPreferenceDBHandler, self).tearDown()

    @blocking_call_on_reactor_thread
    def test_getPrefList(self):
        pl = self.mdb.getMyPrefListInfohash()
        self.assertEqual(len(pl), 12)

    @blocking_call_on_reactor_thread
    def test_addMyPreference_deletePreference(self):
        p = self.mdb.getOne(('torrent_id', 'destination_path', 'creation_time'), torrent_id=126)
        torrent_id = p[0]
        infohash = self.tdb.getInfohash(torrent_id)
        destpath = p[1]
        creation_time = p[2]
        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash()
        self.assertEqual(len(pl), 12)
        self.assertIn(infohash, pl)

        data = {'destination_path': destpath}
        self.mdb.addMyPreference(torrent_id, data)
        p2 = self.mdb.getOne(('torrent_id', 'destination_path', 'creation_time'), torrent_id=126)
        self.assertTrue(p2[0] == p[0])
        self.assertTrue(p2[1] == p[1])

        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash(returnDeleted=False)
        self.assertEqual(len(pl), 11)
        self.assertNotIn(infohash, pl)

        data = {'destination_path': destpath, 'creation_time': creation_time}
        self.mdb.addMyPreference(torrent_id, data)
        p3 = self.mdb.getOne(('torrent_id', 'destination_path', 'creation_time'), torrent_id=126)
        self.assertEqual(p3, p)

    @blocking_call_on_reactor_thread
    def test_getMyPrefListInfohash(self):
        preflist = self.mdb.getMyPrefListInfohash()
        for p in preflist:
            self.assertTrue(not p or len(p) == 20)
        self.assertEqual(len(preflist), 12)

    @blocking_call_on_reactor_thread
    def test_get_my_pref_stats(self):
        res = self.mdb.getMyPrefStats()
        self.assertEqual(len(res), 12)
        for k in res:
            data = res[k]
            self.assertIsInstance(data, basestring, "data is not destination_path: %s" % type(data))

        res = self.mdb.getMyPrefStats(torrent_id=126)
        self.assertEqual(len(res), 1)

    @blocking_call_on_reactor_thread
    def test_my_pref_stats_infohash(self):
        infohash = str2bin('AB8cTG7ZuPsyblbRE7CyxsrKUCg=')
        self.assertIsNone(self.mdb.getMyPrefStatsInfohash(infohash))
        infohash = str2bin('ByJho7yj9mWY1ORWgCZykLbU1Xc=')
        self.assertTrue(self.mdb.getMyPrefStatsInfohash(infohash))

    @blocking_call_on_reactor_thread
    def test_get_my_pref_list_infohash_limit(self):
        self.assertEqual(len(self.mdb.getMyPrefListInfohash(limit=10)), 10)

    @blocking_call_on_reactor_thread
    def test_add_my_preference(self):
        self.assertTrue(self.mdb.addMyPreference(127, {'destination_path': 'C:/mytorrent'}))
        self.assertTrue(self.mdb.addMyPreference(12345678, {'destination_path': 'C:/mytorrent'}))
        self.assertFalse(self.mdb.addMyPreference(12345678, {'destination_path': 'C:/mytorrent'}))

    def test_delete_my_preference(self):
        self.mdb.deletePreference(126)
        res = self.mdb.getMyPrefStats(126)
        self.assertFalse(res[126])
        self.mdb.deletePreference(12348934)

    def test_update_dest_dir(self):
        self.mdb.updateDestDir(126, 'C:/mydest')
        res = self.mdb.getMyPrefStats(126)
        self.assertEqual(res[126], 'C:/mydest')
        self.mdb.updateDestDir(126, {})
        self.assertEqual(res[126], 'C:/mydest')
