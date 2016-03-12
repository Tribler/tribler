import os
from time import sleep
import unittest
from binascii import unhexlify
from shutil import copy as copyFile

from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.SqliteCacheDBHandler import (TorrentDBHandler, MyPreferenceDBHandler, BasicDBHandler,
                                                       PeerDBHandler, LimitedOrderedDict, VoteCastDBHandler,
                                                       ChannelCastDBHandler)
from Tribler.Core.CacheDB.sqlitecachedb import str2bin, SQLiteCacheDB, DB_SCRIPT_RELATIVE_PATH
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.bak_tribler_sdb import TESTS_DATA_DIR, init_bak_tribler_sdb
from Tribler.dispersy.util import blocking_call_on_reactor_thread


S_TORRENT_PATH_BACKUP = os.path.join(TESTS_DATA_DIR, 'bak_single.torrent')
M_TORRENT_PATH_BACKUP = os.path.join(TESTS_DATA_DIR, 'bak_multiple.torrent')

FAKE_PERMID_X = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'

BUSYTIMEOUT = 5000


class TestLimitedOrderedDict(TriblerCoreTest):

    def test_limited_ordered_dict(self):
        od = LimitedOrderedDict(3)
        od['foo'] = 'bar'
        od['bar'] = 'foo'
        od['foobar'] = 'foobar'
        self.assertEqual(len(od), 3)
        od['another'] = 'another'
        self.assertEqual(len(od), 3)


class AbstractDB(TriblerCoreTest):

    def setUpPreSession(self):
        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(False)
        self.config.set_dispersy(False)
        self.config.set_mainline_dht(False)
        self.config.set_torrent_collecting(False)
        self.config.set_libtorrent(False)
        self.config.set_dht_torrent_collecting(False)
        self.config.set_videoplayer(False)
        self.config.set_torrent_store(False)

    def setUp(self):
        super(AbstractDB, self).setUp()

        self.setUpPreSession()
        self.session = Session(self.config, ignore_singleton=True)

        db_path = init_bak_tribler_sdb('bak_new_tribler.sdb', destination_path=self.getStateDir(), overwrite=True)
        db_script_path = os.path.join(self.session.get_install_dir(), DB_SCRIPT_RELATIVE_PATH)

        self.sqlitedb = SQLiteCacheDB(db_path, db_script_path, busytimeout=BUSYTIMEOUT)
        self.sqlitedb.initialize()
        self.session.sqlite_db = self.sqlitedb

    @blocking_call_on_reactor_thread
    def tearDown(self):
        self.sqlitedb.close()
        self.sqlitedb = None
        self.session.del_instance()
        self.session = None

        super(AbstractDB, self).tearDown(self)


class TestSqliteBasicDBHandler(AbstractDB):

    def setUp(self):
        super(TestSqliteBasicDBHandler, self).setUp()
        self.db = BasicDBHandler(self.session, u"Peer")

    @blocking_call_on_reactor_thread
    def test_size(self):
        size = self.db.size()  # there are 3995 peers in the table, however the upgrade scripts remove 8 superpeers
        assert size == 3987, size


class TestSqlitePeerDBHandler(AbstractDB):

    def setUp(self):
        super(TestSqlitePeerDBHandler, self).setUp()

        self.p1 = str2bin(
            'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAA6SYI4NHxwQ8P7P8QXgWAP+v8SaMVzF5+fSUHdAMrs6NvL5Epe1nCNSdlBHIjNjEiC5iiwSFZhRLsr')
        self.p2 = str2bin(
            'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAABo69alKy95H7RHzvDCsolAurKyrVvtDdT9/DzNAGvky6YejcK4GWQXBkIoQGQgxVEgIn8dwaR9B+3U')

        self.pdb = PeerDBHandler(self.session)

        hp = self.pdb.hasPeer(FAKE_PERMID_X)
        assert not hp

    @blocking_call_on_reactor_thread
    def tearDown(self):
        self.pdb.close()
        self.pdb = None
        super(TestSqlitePeerDBHandler, self).tearDown()

    @blocking_call_on_reactor_thread
    def test_getList(self):
        peer1 = self.pdb.getPeer(self.p1)
        peer2 = self.pdb.getPeer(self.p2)
        assert isinstance(peer1, dict)
        assert isinstance(peer2, dict)
        assert peer1[u'peer_id'] == 1, peer1
        assert peer2[u'peer_id'] == 2, peer2

    @blocking_call_on_reactor_thread
    def test_addPeer(self):
        peer_x = {'permid': FAKE_PERMID_X, 'name': 'fake peer x'}
        oldsize = self.pdb.size()
        self.pdb.addPeer(FAKE_PERMID_X, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)

        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p['name'] == 'fake peer x'

        self.assertEqual(self.pdb.getPeer(FAKE_PERMID_X, 'name'), 'fake peer x')

        self.pdb.deletePeer(FAKE_PERMID_X)
        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p is None
        assert self.pdb.size() == oldsize

        self.pdb.addPeer(FAKE_PERMID_X, peer_x)
        self.pdb.addPeer(FAKE_PERMID_X, {'permid': FAKE_PERMID_X, 'name': 'faka peer x'})
        p = self.pdb.getPeer(FAKE_PERMID_X)
        self.assertEqual(p['name'], 'faka peer x')

    @blocking_call_on_reactor_thread
    def test_aa_hasPeer(self):
        assert self.pdb.hasPeer(self.p1)
        assert self.pdb.hasPeer(self.p1, check_db=True)
        assert self.pdb.hasPeer(self.p2)
        assert not self.pdb.hasPeer(FAKE_PERMID_X)

    @blocking_call_on_reactor_thread
    def test_deletePeer(self):
        peer_x = {'permid': FAKE_PERMID_X, 'name': 'fake peer x'}
        oldsize = self.pdb.size()
        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p is None, p

        self.pdb.addPeer(FAKE_PERMID_X, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)
        assert self.pdb.hasPeer(FAKE_PERMID_X)
        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p is not None

        self.pdb.deletePeer(FAKE_PERMID_X)
        assert not self.pdb.hasPeer(FAKE_PERMID_X)
        assert self.pdb.size() == oldsize

        p = self.pdb.getPeer(FAKE_PERMID_X)
        assert p is None

        self.assertFalse(self.pdb.deletePeer(FAKE_PERMID_X))

    @blocking_call_on_reactor_thread
    def test_add_or_get_peer(self):
        self.assertIsInstance(self.pdb.addOrGetPeerID(FAKE_PERMID_X), int)
        self.assertIsInstance(self.pdb.addOrGetPeerID(FAKE_PERMID_X), int)

    @blocking_call_on_reactor_thread
    def test_get_peer_by_id(self):
        self.assertEqual(self.pdb.getPeerById(1, ['name']), 'Peer 1')
        p = self.pdb.getPeerById(1)
        self.assertEqual(p['name'], 'Peer 1')
        self.assertFalse(self.pdb.getPeerById(1234567))


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

    @blocking_call_on_reactor_thread
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

        copyFile(S_TORRENT_PATH_BACKUP, single_torrent_file_path)
        copyFile(M_TORRENT_PATH_BACKUP, multiple_torrent_file_path)

        single_tdef = TorrentDef.load(single_torrent_file_path)
        assert s_infohash == single_tdef.get_infohash()
        multiple_tdef = TorrentDef.load(multiple_torrent_file_path)
        assert m_infohash == multiple_tdef.get_infohash()

        self.tdb.addExternalTorrent(single_tdef)
        self.tdb.addExternalTorrent(multiple_tdef)

        single_torrent_id = self.tdb.getTorrentID(s_infohash)
        multiple_torrent_id = self.tdb.getTorrentID(m_infohash)

        assert self.tdb.getInfohash(single_torrent_id) == s_infohash

        single_name = 'Tribler_4.1.7_src.zip'
        multiple_name = 'Tribler_4.1.7_src'

        assert self.tdb.size() == old_size + 2, old_size - self.tdb.size()
        new_tracker_table_size = self.tdb._db.size('TrackerInfo')
        assert old_tracker_size < new_tracker_table_size, new_tracker_table_size - old_tracker_size

        sname = self.tdb.getOne('name', torrent_id=single_torrent_id)
        assert sname == single_name, (sname, single_name)
        mname = self.tdb.getOne('name', torrent_id=multiple_torrent_id)
        assert mname == multiple_name, (mname, multiple_name)

        s_size = self.tdb.getOne('length', torrent_id=single_torrent_id)
        assert s_size == 1583233, s_size
        m_size = self.tdb.getOne('length', torrent_id=multiple_torrent_id)
        assert m_size == 5358560, m_size

        cat = self.tdb.getOne('category', torrent_id=multiple_torrent_id)
        assert cat == u'xxx', cat

        s_status = self.tdb.getOne('status', torrent_id=single_torrent_id)
        assert s_status == u'unknown', s_status

        m_comment = self.tdb.getOne('comment', torrent_id=multiple_torrent_id)
        comments = 'www.tribler.org'
        assert m_comment.find(comments) > -1
        comments = 'something not inside'
        assert m_comment.find(comments) == -1

        m_trackers = self.tdb.getTrackerListByInfohash(m_infohash)
        assert len(m_trackers) == 8
        assert 'http://tpb.tracker.thepiratebay.org/announce' in m_trackers, m_trackers

        s_torrent = self.tdb.getTorrent(s_infohash)
        m_torrent = self.tdb.getTorrent(m_infohash)
        assert s_torrent['name'] == 'Tribler_4.1.7_src.zip', s_torrent['name']
        assert m_torrent['name'] == 'Tribler_4.1.7_src', m_torrent['name']
        assert m_torrent['last_tracker_check'] == 0

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
        assert category == u'Videoclips', category
        status = self.tdb.getOne('status', torrent_id=multiple_torrent_id)
        assert status == u'good', status
        seeder = self.tdb.getOne('num_seeders', torrent_id=multiple_torrent_id)
        assert seeder == 123
        leecher = self.tdb.getOne('num_leechers', torrent_id=multiple_torrent_id)
        assert leecher == 321
        last_tracker_check = self.tdb.getOne('last_tracker_check', torrent_id=multiple_torrent_id)
        assert last_tracker_check == 1234567, last_tracker_check

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
        assert res == 4848, res

    @blocking_call_on_reactor_thread
    def test_freeSpace(self):
        old_res = self.tdb.getNumberCollectedTorrents()
        self.tdb.freeSpace(20)
        res = self.tdb.getNumberCollectedTorrents()
        self.assertEqual(old_res, res)

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
        self.assertEqual(self.tdb.getTorrentsStats(), (4848, 6519195438919, 187200))

    @blocking_call_on_reactor_thread
    def test_get_library_torrents(self):
        self.assertEqual(len(self.tdb.getLibraryTorrents(['infohash'])), 12)


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
