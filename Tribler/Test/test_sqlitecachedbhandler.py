import os
import sys
import unittest

from time import time
from binascii import unhexlify, hexlify
from shutil import copy as copyFile

from Tribler.Core.Session import Session
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from bak_tribler_sdb import *

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler, BasicDBHandler, PeerDBHandler, \
    VoteCastDBHandler, ChannelCastDBHandler, NetworkBuzzDBHandler
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Test.test_as_server import AbstractServer

S_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_single.torrent')
M_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_multiple.torrent')

BUSYTIMEOUT = 5000
SQLiteCacheDB.DEBUG = False
DEBUG = False

# ------------------------------------------------------------
# The global teardown that will only be called once.
# We add this to delete the Session.
# ------------------------------------------------------------
def teardown():
    if Session.has_instance():
        Session.del_instance()

class AbstractDB(AbstractServer):

    def setUp(self):
        self.setUpCleanup()

        dbpath = init_bak_tribler_sdb('bak_new_tribler.sdb', destination_path=self.getStateDir(), overwrite=True)
        self.sqlitedb = SQLiteCacheDB.getInstance()
        self.sqlitedb.initDB(dbpath, busytimeout=BUSYTIMEOUT)
        self.sqlitedb.waitForUpdateComplete()

    def tearDown(self):
        if SQLiteCacheDB.hasInstance():
            SQLiteCacheDB.getInstance().close_all()
            SQLiteCacheDB.delInstance()

        self.tearDownCleanup()


class TestSqliteBasicDBHandler(AbstractDB):

    def setUp(self):
        AbstractDB.setUp(self)
        self.db = BasicDBHandler(self.sqlitedb, 'Peer')

    def test_size(self):
        size = self.db.size()  # there are 3995 peers in the table, however the upgrade scripts remove 8 superpeers
        assert size == 3987, size


class TestSqlitePeerDBHandler(AbstractDB):

    def setUp(self):
        AbstractDB.setUp(self)

        self.p1 = str2bin('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAA6SYI4NHxwQ8P7P8QXgWAP+v8SaMVzF5+fSUHdAMrs6NvL5Epe1nCNSdlBHIjNjEiC5iiwSFZhRLsr')
        self.p2 = str2bin('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAABo69alKy95H7RHzvDCsolAurKyrVvtDdT9/DzNAGvky6YejcK4GWQXBkIoQGQgxVEgIn8dwaR9B+3U')
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'

        self.pdb = PeerDBHandler.getInstance()

        hp = self.pdb.hasPeerByPermid(fake_permid_x)
        assert not hp

    def tearDown(self):
        PeerDBHandler.delInstance()
        AbstractDB.tearDown(self)

    def test_getList(self):
        p1 = self.pdb.getPeer(self.p1)
        p2 = self.pdb.getPeer(self.p2)
        assert isinstance(p1, dict)
        assert isinstance(p2, dict)
        if DEBUG:
            print >> sys.stderr, "singtest_GETLIST P1", repr(p1)
            print >> sys.stderr, "singtest_GETLIST P2", repr(p2)

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
        assert p == None
        assert self.pdb.size() == oldsize

    def test_aa_hasPeer(self):
        assert self.pdb.hasPeerByPermid(self.p1)
        assert self.pdb.hasPeerByPermid(self.p2)
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        assert not self.pdb.hasPeerByPermid(fake_permid_x)

    def test_deletePeer(self):
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid': fake_permid_x, 'name': 'fake peer x'}
        oldsize = self.pdb.size()
        p = self.pdb.getPeer(fake_permid_x)
        assert p == None, p

        self.pdb.addPeer(fake_permid_x, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)
        assert self.pdb.hasPeerByPermid(fake_permid_x)
        p = self.pdb.getPeer(fake_permid_x)
        assert p is not None

        self.pdb.deletePeer(fake_permid_x)
        assert not self.pdb.hasPeerByPermid(fake_permid_x)

        self.pdb.deletePeer(fake_permid_x)
        assert self.pdb.size() == oldsize
        assert not self.pdb.hasPeerByPermid(fake_permid_x)

        self.pdb.deletePeer(fake_permid_x)
        assert self.pdb.size() == oldsize

        p = self.pdb.getPeer(fake_permid_x)
        assert p is None, p

        self.pdb.deletePeer(fake_permid_x)
        assert self.pdb.size() == oldsize


class TestTorrentDBHandler(AbstractDB):

    def setUp(self):
        AbstractDB.setUp(self)

        self.tdb = TorrentDBHandler.getInstance()
        self.tdb.torrent_dir = FILES_DIR
        self.tdb.mypref_db = MyPreferenceDBHandler.getInstance()
        self.tdb._nb = NetworkBuzzDBHandler.getInstance()

    def tearDown(self):
        TorrentDBHandler.delInstance()
        MyPreferenceDBHandler.delInstance()
        NetworkBuzzDBHandler.delInstance()

        AbstractDB.tearDown(self)

    def test_hasTorrent(self):
        infohash_str = 'AA8cTG7ZuPsyblbRE7CyxsrKUCg='
        infohash = str2bin(infohash_str)
        assert self.tdb.hasTorrent(infohash) == True
        assert self.tdb.hasMetaData(infohash) == True
        fake_infoahsh = 'fake_infohash_100000'
        assert self.tdb.hasTorrent(fake_infoahsh) == False
        assert self.tdb.hasMetaData(fake_infoahsh) == False

    def test_add_update_delete_Torrent(self):
        self.addTorrent()
        self.updateTorrent()
        self.deleteTorrent()

    def addTorrent(self):
        old_size = self.tdb.size()
        old_src_size = self.tdb._db.size('TorrentSource')
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
        src = 'http://www.rss.com/torrent.xml'
        multiple_tdef = TorrentDef.load(multiple_torrent_file_path)
        assert m_infohash == multiple_tdef.get_infohash()

        self.tdb.addExternalTorrent(single_tdef, extra_info={'filename': single_torrent_file_path})
        self.tdb.addExternalTorrent(multiple_tdef, source=src, extra_info={'filename': multiple_torrent_file_path})

        single_torrent_id = self.tdb.getTorrentID(s_infohash)
        multiple_torrent_id = self.tdb.getTorrentID(m_infohash)

        assert self.tdb.getInfohash(single_torrent_id) == s_infohash

        single_name = 'Tribler_4.1.7_src.zip'
        multiple_name = 'Tribler_4.1.7_src'

        assert self.tdb.size() == old_size + 2, old_size - self.tdb.size()
        assert old_src_size + 1 == self.tdb._db.size('TorrentSource')
        new_tracker_table_size = self.tdb._db.size('TrackerInfo')
        assert old_tracker_size < new_tracker_table_size, new_tracker_table_size - old_tracker_size

        torrent = self.tdb.getTorrentById(keys=(u'name',), torrent_id=single_torrent_id)
        sname = torrent[u'name']
        assert sname == single_name, (sname, single_name)
        torrent = self.tdb.getTorrentById(keys=(u'name',), torrent_id=multiple_torrent_id)
        mname = torrent[u'name']
        assert mname == multiple_name, (mname, multiple_name)

        torrent = self.tdb.getTorrentById(keys=(u'length',), torrent_id=single_torrent_id)
        s_size = torrent[u'length']
        assert s_size == 1583233, s_size
        torrent = self.tdb.getTorrentById(keys=(u'length',), torrent_id=multiple_torrent_id)
        m_size = torrent[u'length']
        assert m_size == 5358560, m_size

        sid = self.tdb._db.getOne('TorrentSource', 'source_id', name=src)
        assert sid > 1

        torrent = self.tdb.getTorrentById(keys=(u'source_id',), torrent_id=multiple_torrent_id)
        m_sid = torrent[u'source_id']
        assert sid == m_sid

        torrent = self.tdb.getTorrentById(keys=(u'source_id',), torrent_id=single_torrent_id)
        s_sid = torrent[u'source_id']
        assert 1 == s_sid

        torrent = self.tdb.getTorrentById(keys=(u'comment',), torrent_id=multiple_torrent_id)
        m_comment = torrent[u'comment']
        comments = 'www.tribler.org'
        assert m_comment.find(comments) > -1

        comments = 'something not inside'
        assert m_comment.find(comments) == -1

        m_trackers = self.tdb.getTrackerListByInfohash(m_infohash)
        assert len(m_trackers) == 8
        assert 'http://tpb.tracker.thepiratebay.org:80/announce' in m_trackers, m_trackers

        s_torrent = self.tdb.getTorrent(s_infohash)
        m_torrent = self.tdb.getTorrent(m_infohash)
        assert s_torrent['name'] == 'Tribler_4.1.7_src.zip', s_torrent['name']
        assert m_torrent['name'] == 'Tribler_4.1.7_src', m_torrent['name']
        assert m_torrent['last_check_time'] == 0

    def updateTorrent(self):
        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')
        self.tdb.updateTorrent(m_infohash, relevance=3.1415926, category=['Videoclips'],
                         status='good', seeder=123, leecher=321,
                         last_check_time=1234567,
                         other_key1='abcd', other_key2=123)
        multiple_torrent_id = self.tdb.getTorrentID(m_infohash)

        key_tuple = (u'status_id', u'num_seeders', u'num_leechers', u'last_tracker_check')
        torrent = self.tdb.getTorrentById(keys=key_tuple, torrent_id=multiple_torrent_id)

        sid = torrent[u'status_id']
        assert sid == 1

        seeder = torrent[u'num_seeders']
        assert seeder == 123

        leecher = torrent[u'num_leechers']
        assert leecher == 321

        last_check_time = torrent[u'last_tracker_check']
        assert last_check_time == 1234567, last_check_time

    def deleteTorrent(self):
        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')

        assert self.tdb.deleteTorrent(s_infohash, delete_file=True)
        assert self.tdb.deleteTorrent(m_infohash)

        assert not self.tdb.hasTorrent(s_infohash)
        assert not self.tdb.hasTorrent(m_infohash)
        assert not os.path.isfile(os.path.join(self.getStateDir(), 'single.torrent'))
        m_trackers = self.tdb.getTrackerListByInfohash(m_infohash)
        assert len(m_trackers) == 0

        # fake_infoahsh = 'fake_infohash_1'+'0R0\x10\x00\x07*\x86H\xce=\x02'
        # 02/02/10 Boudewijn: infohashes must be 20 bytes long
        fake_infoahsh = 'fake_infohash_1' + '0R0\x10\x00'
        assert not self.tdb.deleteTorrent(fake_infoahsh)

        my_infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        my_infohash = str2bin(my_infohash_str_126)
        assert not self.tdb.deleteTorrent(my_infohash)

    def test_getCollectedTorrentHashes(self):
        res = self.tdb.getNumberCollectedTorrents()
        assert res == 4848, res

    @unittest.skip("TODO, the database thingie shouldn't be deleting files from the FS.")
    def test_freeSpace(self):
        old_res = self.tdb.getNumberCollectedTorrents()
        self.tdb.freeSpace(20)
        res = self.tdb.getNumberCollectedTorrents()
        assert old_res - res == 20


class TestMyPreferenceDBHandler(AbstractDB):

    def setUp(self):
        AbstractDB.setUp(self)

        self.mdb = MyPreferenceDBHandler.getInstance()
        self.mdb.loadData()
        self.tdb = TorrentDBHandler.getInstance()

    def tearDown(self):
        MyPreferenceDBHandler.delInstance()
        TorrentDBHandler.delInstance()

        AbstractDB.tearDown(self)

    def test_getPrefList(self):
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 24

    def test_getRecentLivePrefList(self):
        pl = self.mdb.getRecentLivePrefList()
        assert len(pl) == 11, (len(pl), pl)
        infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        assert bin2str(pl[0]) == infohash_str_126
        infohash_str_1279 = 'R+grUhp884MnFkt6NuLnnauZFsc='
        assert bin2str(pl[1]) == infohash_str_1279

        pl = self.mdb.getRecentLivePrefList(8)
        assert len(pl) == 8, (len(pl), pl)
        assert bin2str(pl[0]) == infohash_str_126
        assert bin2str(pl[1]) == infohash_str_1279

    def test_hasMyPreference(self):
        assert self.mdb.hasMyPreference(126)
        assert self.mdb.hasMyPreference(1279)
        assert not self.mdb.hasMyPreference(1)

    def test_addMyPreference_deletePreference(self):
        keys = [u'torrent_id', u'creation_time', u'progress', u'destination_path']

        torrent_id=126
        my_pref_stats = self.mdb.getMyPrefStats(torrent_id=126)
        p = { u'torrent_id' : torrent_id,
            u'creation_time' : my_pref_stats[torrent_id][0],
            u'progress' : my_pref_stats[torrent_id][1],
            u'destination_path' : my_pref_stats[torrent_id][2],
            }

        torrent_id = p[u'torrent_id']
        infohash = self.tdb.getInfohash(torrent_id)
        destpath = p[u'destination_path']
        progress = p[u'progress']
        creation_time = p[u'creation_time']
        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 22
        assert infohash not in pl

        data = {u'destination_path': destpath}
        self.mdb.addMyPreference(torrent_id, data)
        my_pref_stats = self.mdb.getMyPrefStats(torrent_id=126)
        p2 = { u'torrent_id' : torrent_id,
            u'creation_time' : my_pref_stats[torrent_id][0],
            u'progress' : my_pref_stats[torrent_id][1],
            u'destination_path' : my_pref_stats[torrent_id][2],
            }
        assert p2[u'torrent_id'] == p[u'torrent_id']\
            and p2[u'destination_path'] == p[u'destination_path']\
            and p2[u'progress'] == 0\
            and time() - p2[u'creation_time'] < 10, p2

        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 22
        assert infohash not in pl

        data = {u'destination_path': destpath, u'progress': progress, u'creation_time': creation_time}
        self.mdb.addMyPreference(torrent_id, data)
        my_pref_stats = self.mdb.getMyPrefStats(torrent_id=126)
        p3 = { u'torrent_id' : torrent_id,
            u'creation_time' : my_pref_stats[torrent_id][0],
            u'progress' : my_pref_stats[torrent_id][1],
            u'destination_path' : my_pref_stats[torrent_id][2],
            }
        assert p3 == p, p3

    def test_updateProgress(self):
        infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        infohash = str2bin(infohash_str_126)
        torrent_id = self.tdb.getTorrentID(infohash)
        assert torrent_id == 126
        assert self.mdb.hasMyPreference(torrent_id)
        self.mdb.updateProgress(torrent_id, 3.14)
        my_pref_stats = self.mdb.getMyPrefStats(torrent_id=126)
        p = { u'torrent_id' : torrent_id,
            u'creation_time' : my_pref_stats[torrent_id][0],
            u'progress' : my_pref_stats[torrent_id][1],
            u'destination_path' : my_pref_stats[torrent_id][2],
            }
        assert p[u'progress'] == 3.14

    def test_getMyPrefListInfohash(self):
        preflist = self.mdb.getMyPrefListInfohash()
        for p in preflist:
            assert not p or len(p) == 20, len(p)
        assert len(preflist) == 24

    def test_getMyPrefStats(self):
        res = self.mdb.getMyPrefStats()
        assert len(res) == 12
        for k in res:
            data = res[k]
            assert len(data) == 3
