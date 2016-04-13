from binascii import unhexlify
import os
from shutil import copy as copyfile
from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.leveldbstore import LevelDbStore
from Tribler.Test.Core.test_sqlitecachedbhandler import AbstractDB
from Tribler.Test.test_as_server import TESTS_DATA_DIR
from Tribler.dispersy.util import blocking_call_on_reactor_thread


S_TORRENT_PATH_BACKUP = os.path.join(TESTS_DATA_DIR, 'bak_single.torrent')
M_TORRENT_PATH_BACKUP = os.path.join(TESTS_DATA_DIR, 'bak_multiple.torrent')


class TestTorrentFullSessionDBHandler(AbstractDB):

    def setUpPreSession(self):
        super(TestTorrentFullSessionDBHandler, self).setUpPreSession()
        self.config.set_megacache(True)

    def setUp(self):
        super(TestTorrentFullSessionDBHandler, self).setUp()
        self.tdb = TorrentDBHandler(self.session)

    @blocking_call_on_reactor_thread
    def test_initialize(self):
        self.tdb.initialize()
        self.assertIsNone(self.tdb.mypref_db)
        self.assertIsNone(self.tdb.votecast_db)
        self.assertIsNone(self.tdb.channelcast_db)


class TestTorrentDBHandler(AbstractDB):

    def setUpPreSession(self):
        super(TestTorrentDBHandler, self).setUpPreSession()
        self.config.set_megacache(True)
        self.config.set_torrent_store(True)

    def setUp(self):
        super(TestTorrentDBHandler, self).setUp()

        from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
        from Tribler.Core.Modules.tracker_manager import TrackerManager
        self.session.lm = TriblerLaunchMany()
        self.session.lm.tracker_manager = TrackerManager(self.session)
        self.session.lm.tracker_manager.initialize()
        self.tdb = TorrentDBHandler(self.session)
        self.tdb.torrent_dir = TESTS_DATA_DIR
        self.tdb.category = Category.getInstance()
        self.tdb.mypref_db = MyPreferenceDBHandler(self.session)

    def tearDown(self):
        self.tdb.mypref_db.close()
        self.tdb.mypref_db = None
        self.tdb.close()
        self.tdb = None

        super(TestTorrentDBHandler, self).tearDown()

    @blocking_call_on_reactor_thread
    def test_hasTorrent(self):
        infohash_str = 'AA8cTG7ZuPsyblbRE7CyxsrKUCg='
        infohash = str2bin(infohash_str)
        self.assertTrue(self.tdb.hasTorrent(infohash))
        self.assertTrue(self.tdb.hasTorrent(infohash)) # cache will trigger
        fake_infohash = 'fake_infohash_100000'
        self.assertFalse(self.tdb.hasTorrent(fake_infohash))

    @blocking_call_on_reactor_thread
    def test_get_infohash(self):
        self.assertTrue(self.tdb.getInfohash(1))
        self.assertFalse(self.tdb.getInfohash(1234567))

    @blocking_call_on_reactor_thread
    def test_add_update_Torrent(self):
        self.addTorrent()
        self.updateTorrent()

    @blocking_call_on_reactor_thread
    def addTorrent(self):
        old_size = self.tdb.size()
        old_tracker_size = self.tdb._db.size('TrackerInfo')

        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')

        sid = self.tdb.getTorrentID(s_infohash)
        mid = self.tdb.getTorrentID(m_infohash)

        single_torrent_file_path = os.path.join(self.getStateDir(), 'single.torrent')
        multiple_torrent_file_path = os.path.join(self.getStateDir(), 'multiple.torrent')

        copyfile(S_TORRENT_PATH_BACKUP, single_torrent_file_path)
        copyfile(M_TORRENT_PATH_BACKUP, multiple_torrent_file_path)

        single_tdef = TorrentDef.load(single_torrent_file_path)
        self.assertEqual(s_infohash, single_tdef.get_infohash())
        multiple_tdef = TorrentDef.load(multiple_torrent_file_path)
        self.assertEqual(m_infohash, multiple_tdef.get_infohash())

        self.tdb.addExternalTorrent(single_tdef)
        self.tdb.addExternalTorrent(multiple_tdef)

        single_torrent_id = self.tdb.getTorrentID(s_infohash)
        multiple_torrent_id = self.tdb.getTorrentID(m_infohash)

        self.assertEqual(self.tdb.getInfohash(single_torrent_id), s_infohash)

        single_name = 'Tribler_4.1.7_src.zip'
        multiple_name = 'Tribler_4.1.7_src'

        self.assertEqual(self.tdb.size(), old_size + 2)
        new_tracker_table_size = self.tdb._db.size('TrackerInfo')
        self.assertLess(old_tracker_size, new_tracker_table_size)

        sname = self.tdb.getOne('name', torrent_id=single_torrent_id)
        self.assertEqual(sname, single_name)
        mname = self.tdb.getOne('name', torrent_id=multiple_torrent_id)
        self.assertEqual(mname, multiple_name)

        s_size = self.tdb.getOne('length', torrent_id=single_torrent_id)
        self.assertEqual(s_size, 1583233)
        m_size = self.tdb.getOne('length', torrent_id=multiple_torrent_id)
        self.assertEqual(m_size, 5358560)

        cat = self.tdb.getOne('category', torrent_id=multiple_torrent_id)
        self.assertEqual(cat, u'xxx')

        s_status = self.tdb.getOne('status', torrent_id=single_torrent_id)
        self.assertEqual(s_status, u'unknown')

        m_comment = self.tdb.getOne('comment', torrent_id=multiple_torrent_id)
        comments = 'www.tribler.org'
        self.assertGreater(m_comment.find(comments), -1)
        comments = 'something not inside'
        self.assertEqual(m_comment.find(comments), -1)

        m_trackers = self.tdb.getTrackerListByInfohash(m_infohash)
        self.assertEqual(len(m_trackers), 8)
        self.assertIn('http://tpb.tracker.thepiratebay.org/announce', m_trackers)

        s_torrent = self.tdb.getTorrent(s_infohash)
        m_torrent = self.tdb.getTorrent(m_infohash)
        self.assertEqual(s_torrent['name'], 'Tribler_4.1.7_src.zip')
        self.assertEqual(m_torrent['name'], 'Tribler_4.1.7_src')
        self.assertEqual(m_torrent['last_tracker_check'], 0)

    @blocking_call_on_reactor_thread
    def updateTorrent(self):
        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')
        self.tdb.updateTorrent(m_infohash, relevance=3.1415926, category=u'Videoclips',
                               status=u'good', seeder=123, leecher=321,
                               last_tracker_check=1234567,
                               other_key1='abcd', other_key2=123)
        multiple_torrent_id = self.tdb.getTorrentID(m_infohash)
        category = self.tdb.getOne('category', torrent_id=multiple_torrent_id)
        self.assertEqual(category, u'Videoclips')
        status = self.tdb.getOne('status', torrent_id=multiple_torrent_id)
        self.assertEqual(status, u'good')
        seeder = self.tdb.getOne('num_seeders', torrent_id=multiple_torrent_id)
        self.assertEqual(seeder, 123)
        leecher = self.tdb.getOne('num_leechers', torrent_id=multiple_torrent_id)
        self.assertEqual(leecher, 321)
        last_tracker_check = self.tdb.getOne('last_tracker_check', torrent_id=multiple_torrent_id)
        self.assertEqual(last_tracker_check, 1234567)

    @blocking_call_on_reactor_thread
    def test_add_external_torrent_no_def_existing(self):
        infohash = str2bin('AA8cTG7ZuPsyblbRE7CyxsrKUCg=')
        self.tdb.addExternalTorrentNoDef(infohash, "test torrent", [], [], 1234)
        self.assertTrue(self.tdb.hasTorrent(infohash))

    @blocking_call_on_reactor_thread
    def test_add_external_torrent_no_def_no_files(self):
        infohash = unhexlify('48865489ac16e2f34ea0cd3043cfd970cc24ec09')
        self.tdb.addExternalTorrentNoDef(infohash, "test torrent", [], [], 1234)
        self.assertFalse(self.tdb.hasTorrent(infohash))

    @blocking_call_on_reactor_thread
    def test_add_external_torrent_no_def_one_file(self):
        infohash = unhexlify('49865489ac16e2f34ea0cd3043cfd970cc24ec09')
        self.tdb.addExternalTorrentNoDef(infohash, "test torrent", [("file1", 42)],
                                         ['http://localhost/announce'], 1234)
        self.assertTrue(self.tdb.getTorrentID(infohash))

    @blocking_call_on_reactor_thread
    def test_add_external_torrent_no_def_more_files(self):
        infohash = unhexlify('50865489ac16e2f34ea0cd3043cfd970cc24ec09')
        self.tdb.addExternalTorrentNoDef(infohash, "test torrent", [("file1", 42), ("file2", 43)],
                                         [], 1234, extra_info={"seeder": 2, "leecher": 3})
        self.assertTrue(self.tdb.getTorrentID(infohash))

    @blocking_call_on_reactor_thread
    def test_add_external_torrent_no_def_invalid(self):
        infohash = unhexlify('50865489ac16e2f34ea0cd3043cfd970cc24ec09')
        self.tdb.addExternalTorrentNoDef(infohash, "test torrent", [("file1", {}), ("file2", 43)],
                                         [], 1234)
        self.assertFalse(self.tdb.getTorrentID(infohash))

    @blocking_call_on_reactor_thread
    def test_add_get_torrent_id(self):
        infohash = str2bin('AA8cTG7ZuPsyblbRE7CyxsrKUCg=')
        self.assertEqual(self.tdb.addOrGetTorrentID(infohash), 1)

        new_infohash = unhexlify('50865489ac16e2f34ea0cd3043cfd970cc24ec09')
        self.assertEqual(self.tdb.addOrGetTorrentID(new_infohash), 4849)

    @blocking_call_on_reactor_thread
    def test_add_get_torrent_ids_return(self):
        infohash = str2bin('AA8cTG7ZuPsyblbRE7CyxsrKUCg=')
        new_infohash = unhexlify('50865489ac16e2f34ea0cd3043cfd970cc24ec09')
        tids, inserted = self.tdb.addOrGetTorrentIDSReturn([infohash, new_infohash])
        self.assertEqual(tids, [1, 4849])
        self.assertEqual(len(inserted), 1)

    @blocking_call_on_reactor_thread
    def test_index_torrent_existing(self):
        self.tdb._indexTorrent(1, "test", [])

    @blocking_call_on_reactor_thread
    def test_getCollectedTorrentHashes(self):
        res = self.tdb.getNumberCollectedTorrents()
        self.assertEqual(res, 4847)

    @blocking_call_on_reactor_thread
    def test_freeSpace(self):
        # Manually set the torrent store because register is not called.
        self.session.lm.torrent_store = LevelDbStore(self.session.get_torrent_store_dir())
        old_res = self.tdb.getNumberCollectedTorrents()
        self.tdb.freeSpace(20)
        res = self.tdb.getNumberCollectedTorrents()
        self.session.lm.torrent_store.close()
        self.assertEqual(res, old_res-20)

    @blocking_call_on_reactor_thread
    def test_get_search_suggestions(self):
        self.assertEqual(self.tdb.getSearchSuggestion(["content", "cont"]), ["Content 1"])

    @blocking_call_on_reactor_thread
    def test_get_autocomplete_terms(self):
        self.assertEqual(len(self.tdb.getAutoCompleteTerms("content", 100)), 0)

    @blocking_call_on_reactor_thread
    def test_get_recently_randomly_collected_torrents(self):
        self.assertEqual(len(self.tdb.getRecentlyCollectedTorrents(limit=10)), 10)
        self.assertEqual(len(self.tdb.getRandomlyCollectedTorrents(100000000, limit=10)), 3)

    @blocking_call_on_reactor_thread
    def test_select_torrents_to_collect(self):
        infohash = str2bin('AA8cTG7ZuPsyblbRE7CyxsrKUCg=')
        self.assertEqual(len(self.tdb.select_torrents_to_collect(infohash)), 0)

    @blocking_call_on_reactor_thread
    def test_get_torrents_stats(self):
        self.assertEqual(self.tdb.getTorrentsStats(), (4847, 6519179841442, 187195))

    @blocking_call_on_reactor_thread
    def test_get_library_torrents(self):
        self.assertEqual(len(self.tdb.getLibraryTorrents(['infohash'])), 12)
