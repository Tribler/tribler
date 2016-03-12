from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler
from Tribler.Test.Core.test_sqlitecachedbhandler import AbstractDB
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMyPreferenceDBHandler(AbstractDB):

    def setUp(self):
        super(TestMyPreferenceDBHandler, self).setUp()

        self.tdb = TorrentDBHandler(self.session)
        self.mdb = MyPreferenceDBHandler(self.session)
        self.mdb._torrent_db = self.tdb

    @blocking_call_on_reactor_thread
    def tearDown(self):
        self.mdb.close()
        self.mdb = None
        self.tdb.close()
        self.tdb = None

        super(TestMyPreferenceDBHandler, self).tearDown()

    @blocking_call_on_reactor_thread
    def test_getPrefList(self):
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 12

    @blocking_call_on_reactor_thread
    def test_addMyPreference_deletePreference(self):
        p = self.mdb.getOne(('torrent_id', 'destination_path', 'creation_time'), torrent_id=126)
        torrent_id = p[0]
        infohash = self.tdb.getInfohash(torrent_id)
        destpath = p[1]
        creation_time = p[2]
        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 12
        assert infohash in pl

        data = {'destination_path': destpath}
        self.mdb.addMyPreference(torrent_id, data)
        p2 = self.mdb.getOne(('torrent_id', 'destination_path', 'creation_time'), torrent_id=126)
        assert p2[0] == p[0] and p2[1] == p[1]

        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash(returnDeleted=False)
        assert len(pl) == 11
        assert infohash not in pl

        data = {'destination_path': destpath, 'creation_time': creation_time}
        self.mdb.addMyPreference(torrent_id, data)
        p3 = self.mdb.getOne(('torrent_id', 'destination_path', 'creation_time'), torrent_id=126)
        assert p3 == p, p3

    @blocking_call_on_reactor_thread
    def test_getMyPrefListInfohash(self):
        preflist = self.mdb.getMyPrefListInfohash()
        for p in preflist:
            assert not p or len(p) == 20, len(p)
        assert len(preflist) == 12, u"preflist length = %s" % len(preflist)

    @blocking_call_on_reactor_thread
    def test_getMyPrefStats(self):
        res = self.mdb.getMyPrefStats()
        assert len(res) == 12
        for k in res:
            data = res[k]
            assert isinstance(data, basestring), "data is not destination_path: %s" % type(data)

    @blocking_call_on_reactor_thread
    def test_get_my_pref_list_infohash_limit(self):
        self.assertEqual(len(self.mdb.getMyPrefListInfohash(limit=10)), 10)
