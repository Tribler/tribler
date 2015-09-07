import os
import unittest
from binascii import unhexlify
from shutil import copy as copyFile
from time import time
from unittest.case import skip

from twisted.internet import reactor

from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.SqliteCacheDBHandler import (TorrentDBHandler, MyPreferenceDBHandler, BasicDBHandler,
                                                       PeerDBHandler)
from Tribler.Core.CacheDB.sqlitecachedb import str2bin, SQLiteCacheDB
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.bak_tribler_sdb import TESTS_DATA_DIR, init_bak_tribler_sdb
from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.util import blocking_call_on_reactor_thread


S_TORRENT_PATH_BACKUP = os.path.join(TESTS_DATA_DIR, 'bak_single.torrent')
M_TORRENT_PATH_BACKUP = os.path.join(TESTS_DATA_DIR, 'bak_multiple.torrent')

BUSYTIMEOUT = 5000
DEBUG = False

# ------------------------------------------------------------
# The global teardown that will only be called once.
# We add this to delete the Session.
# ------------------------------------------------------------


@blocking_call_on_reactor_thread
def teardown():
    if Session.has_instance():
        Session.del_instance()


class AbstractDB(AbstractServer):

    def setUp(self):
        super(AbstractDB, self).setUp()

        # dummy session
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
        self.session = Session(self.config, ignore_singleton=True)

        dbpath = init_bak_tribler_sdb('bak_new_tribler.sdb', destination_path=self.getStateDir(), overwrite=True)
        self.sqlitedb = SQLiteCacheDB(self.session, busytimeout=BUSYTIMEOUT)
        self.sqlitedb.initialize(dbpath)
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
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'

        self.pdb = PeerDBHandler(self.session)

        hp = self.pdb.hasPeer(fake_permid_x)
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
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid': fake_permid_x, 'name': 'fake peer x'}
        oldsize = self.pdb.size()
        self.pdb.addPeer(fake_permid_x, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)

        p = self.pdb.getPeer(fake_permid_x)
        assert p['name'] == 'fake peer x'

        self.pdb.deletePeer(fake_permid_x)
        p = self.pdb.getPeer(fake_permid_x)
        assert p is None
        assert self.pdb.size() == oldsize

    @blocking_call_on_reactor_thread
    def test_aa_hasPeer(self):
        assert self.pdb.hasPeer(self.p1)
        assert self.pdb.hasPeer(self.p2)
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        assert not self.pdb.hasPeer(fake_permid_x)

    @blocking_call_on_reactor_thread
    def test_deletePeer(self):
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid': fake_permid_x, 'name': 'fake peer x'}
        oldsize = self.pdb.size()
        p = self.pdb.getPeer(fake_permid_x)
        assert p is None, p

        self.pdb.addPeer(fake_permid_x, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)
        assert self.pdb.hasPeer(fake_permid_x)
        p = self.pdb.getPeer(fake_permid_x)
        assert p is not None

        self.pdb.deletePeer(fake_permid_x)
        assert not self.pdb.hasPeer(fake_permid_x)
        assert self.pdb.size() == oldsize

        p = self.pdb.getPeer(fake_permid_x)
        assert p is None


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
        self.tdb.category = Category.getInstance(self.session)
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
        assert self.tdb.hasTorrent(infohash)
        fake_infoahsh = 'fake_infohash_100000'
        assert self.tdb.hasTorrent(fake_infoahsh) == False

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
    def test_getCollectedTorrentHashes(self):
        res = self.tdb.getNumberCollectedTorrents()
        assert res == 4848, res

    @unittest.skip("TODO, the database thingie shouldn't be deleting files from the FS.")
    @blocking_call_on_reactor_thread
    def test_freeSpace(self):
        old_res = self.tdb.getNumberCollectedTorrents()
        self.tdb.freeSpace(20)
        res = self.tdb.getNumberCollectedTorrents()
        assert old_res - res == 20


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

    @skip("We are going to rewrite the whole database thing, so its not worth the trouble fixing this now")
    @blocking_call_on_reactor_thread
    def test_addMyPreference_deletePreference(self):
        p = self.mdb.getOne(('torrent_id', 'destination_path', 'creation_time'), torrent_id=126)
        torrent_id = p[0]
        infohash = self.tdb.getInfohash(torrent_id)
        destpath = p[1]
        creation_time = p[2]
        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 22
        assert infohash not in pl

        data = {'destination_path': destpath}
        self.mdb.addMyPreference(torrent_id, data)
        p2 = self.mdb.getOne(('torrent_id', 'destination_path', 'creation_time'), torrent_id=126)
        assert p2[0] == p[0] and p2[1] == p[1] and time() - p2[2] < 10, p2

        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 22
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
