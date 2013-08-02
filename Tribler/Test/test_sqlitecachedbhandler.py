import os
import sys
import unittest

from time import time
from binascii import unhexlify
from shutil import copy as copyFile


from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from bak_tribler_sdb import *

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler, BasicDBHandler, PeerDBHandler,\
    VoteCastDBHandler, ChannelCastDBHandler, NetworkBuzzDBHandler
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Test.test_as_server import AbstractServer

S_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_single.torrent')
M_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_multiple.torrent')

BUSYTIMEOUT = 5000
SQLiteCacheDB.DEBUG = False
DEBUG = False


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

    def test_getOne(self):
        ip = self.db.getOne('ip', peer_id=1)
        assert ip == '1.1.1.1', ip

        pid = self.db.getOne('peer_id', ip='1.1.1.1')
        assert pid == 1, pid

        name = self.db.getOne('name', ip='1.1.1.1', port=1)
        assert name == 'Peer 1', name

        name = self.db.getOne('name', ip='68.108.115.221', port=6882)
        assert name == None, name

        tid = self.db.getOne('peer_id', conj='OR', ip='1.1.1.1', name='Peer 1')
        assert tid == 1, tid

        tid = self.db.getOne('peer_id', conj='OR', ip='1.1.1.1', name='asdfasfasfXXXXXXxx...')
        assert tid == 1, tid

        tid = self.db.getOne('peer_id', conj='OR', ip='1.1.1.123', name='Peer 1')
        assert tid == 1, tid

        lbt = self.db.getOne('last_buddycast', peer_id=1)
        assert lbt == 1193379432, lbt

        name, ip, lbt = self.db.getOne(('name', 'ip', 'last_buddycast'), peer_id=1)
        assert name == 'Peer 1' and ip == '1.1.1.1' and lbt == 1193379432, (name, ip, lbt)

        values = self.db.getOne('*', peer_id=1)
        # 03/02/10 Boudewijn: In contrast to the content of the
        # database, the similarity value is not 12.537961593122299 but
        # 0 because it is reset as the database is upgraded.
        results = (1, u'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAA6SYI4NHxwQ8P7P8QXgWAP+v8SaMVzF5+fSUHdAMrs6NvL5Epe1nCNSdlBHIjNjEiC5iiwSFZhRLsr', u'Peer 1', u'1.1.1.1', 1, None, 2, 0, 0, 0, 1194966306, 1193379769, 1193379432, 1, 1, 0, 0, 0, 0, 0, 0)

        for i in range(len(values)):
            assert values[i] == results[i], (i, values[i], results[i])

    def test_getAll(self):
        ips = self.db.getAll('ip')
        assert len(ips) == 3987, len(ips)

        ips = self.db.getAll('distinct ip')
        assert len(ips) == 256, len(ips)

        ips = self.db.getAll('ip', "ip like '130.%'")
        assert len(ips) == 16, len(ips)

        ids = self.db.getAll('peer_id', 'thumbnail is NULL')
        assert len(ids) == 3987, len(ids)

        ips = self.db.getAll('ip', "ip like '88.%'", port=88, conj='or')
        assert len(ips) == 16, len(ips)

        ips = self.db.getAll('ip', "ip like '88.%'", port=88, order_by='ip')
        assert len(ips) == 1, len(ips)
        assert ips[0][0] == '88.88.88.88', ips[0]

        names = self.db.getAll('name', "ip like '88.%'", order_by='ip', limit=4, offset=1)
        assert len(names) == 4
        assert names[2][0] == 'Peer 856', names
        # select name from Peer where ip like '88.%' and port==7762 order by ip limit 4 offset 3

        ips = self.db.getAll('count(distinct ip), port', group_by='port')
        # select count(distinct ip), port from Peer group by port
        for nip, port in ips:
            if port == 6881:
                assert nip == 2842, nip
                break


class TestSqlitePeerDBHandler(AbstractDB):

    def setUp(self):
        AbstractDB.setUp(self)

        self.p1 = str2bin('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAA6SYI4NHxwQ8P7P8QXgWAP+v8SaMVzF5+fSUHdAMrs6NvL5Epe1nCNSdlBHIjNjEiC5iiwSFZhRLsr')
        self.p2 = str2bin('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAABo69alKy95H7RHzvDCsolAurKyrVvtDdT9/DzNAGvky6YejcK4GWQXBkIoQGQgxVEgIn8dwaR9B+3U')
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        hp = self.sqlitedb.hasPeer(fake_permid_x)
        assert not hp

        self.pdb = PeerDBHandler.getInstance()

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
        assert p1['port'] == 1
        assert p2['port'] == 2

    def test_getPeerSim(self):
        permid_str = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEACPJqLjmKeMNRwkCNKkPH51gjQ5e7u4s2vWv9I/AALXtpf+bFPtY8cyFv6OCzisYDo+brgqOxAtuNZwP'
        permid = str2bin(permid_str)
        sim = self.pdb.getPeerSim(permid)
        # 03/02/10 Boudewijn: In contrast to the content of the
        # database, the similarity value is not 5.82119645394964 but 0
        # because it is reset as the database is upgraded.
        assert sim == 0

        permid_str = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAB0XbUrw5b8CrTrMZST1SPyrzjgSzIE6ynALtlZASGAb+figVXRRGpKW6MSal3KnEm1/q0P3JPWrhCE'
        permid = str2bin(permid_str)
        sim = self.pdb.getPeerSim(permid)
        assert sim == 0

    def test_getPeerList(self):
        peerlist = self.pdb.getPeerList()
        assert len(peerlist) == 3987
        peerlist.sort()
        assert bin2str(peerlist[345]) == 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEACxVRvG/Gr19EAPJru2Z5gjctEzv973/PJCQIua2ATMP6euq+Kf4gYpdKbsB/PWqJnfY/wSKPHHfIByV'

    def test_getPeers(self):
        peerlist = sorted(self.pdb.getPeerList())
        pl = peerlist[:10]
        peers = self.pdb.getPeers(pl, ['permid', 'peer_id', 'ip', 'port', 'name'])
        # for p in peers: print p
        assert peers[7]['name'] == 'Peer 7'
        assert peers[8]['name'] == 'Peer 8'
        assert peers[1]['ip'] == '1.1.1.1'
        assert peers[3]['peer_id'] == 3

    def test_addPeer(self):
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid': fake_permid_x, 'ip': '1.2.3.4', 'port': 234,
                  'name': 'fake peer x', 'last_seen': 12345}
        oldsize = self.pdb.size()
        self.pdb.addPeer(fake_permid_x, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)
        # db.addPeer(fake_permid_x, peer_x)
        # assert db.size() == oldsize+1
        p = self.pdb.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.4'
        assert p['port'] == 234
        assert p['name'] == 'fake peer x'
#        dns = db.getPeer(fake_permid_x, ('ip','port'))
#        assert dns[0] == '1.2.3.4'
#        assert dns[1] == 234
#        dns = db.getPeer(fake_permid_x+'abcd', ('ip','port'))
#        assert dns == None

        peer_x['ip'] = '4.3.2.1'
        peer_x['port'] = 432
        peer_x['last_seen'] = 1234567
        self.pdb.addPeer(fake_permid_x, peer_x, update_dns=False)
        p = self.pdb.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.4'
        assert p['port'] == 234
        assert p['last_seen'] == 1234567, p['last_seen']

        peer_x['ip'] = '4.3.2.1'
        peer_x['port'] = 432
        peer_x['last_seen'] = 12345
        self.pdb.addPeer(fake_permid_x, peer_x, update_dns=True)
        p = self.pdb.getPeer(fake_permid_x)
        assert p['ip'] == '4.3.2.1'
        assert p['port'] == 432
        assert p['last_seen'] == 12345

        peer_x['ip'] = '1.2.3.1'
        peer_x['port'] = 234
        self.pdb.addPeer(fake_permid_x, peer_x, update_dns=False)
        p = self.pdb.getPeer(fake_permid_x)
        assert p['ip'] == '4.3.2.1'
        assert p['port'] == 432
        assert p['last_seen'] == 12345

        peer_x['ip'] = '1.2.3.4'
        peer_x['port'] = 234
        peer_x['last_seen'] = 1234569
        self.pdb.addPeer(fake_permid_x, peer_x, update_dns=True)
        p = self.pdb.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.4'
        assert p['port'] == 234
        assert p['last_seen'] == 1234569

        peer_x['ip'] = '1.2.3.5'
        peer_x['port'] = 236
        self.pdb.addPeer(fake_permid_x, peer_x, update_dns=True)
        p = self.pdb.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.5'
        assert p['port'] == 236

        self.pdb._db.deletePeer(fake_permid_x, force=True)
        p = self.pdb.getPeer(fake_permid_x)
        assert p == None
        assert self.pdb.size() == oldsize

    def test_aa_hasPeer(self):
        assert self.pdb.hasPeer(self.p1)
        assert self.pdb.hasPeer(self.p2)
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        assert not self.pdb.hasPeer(fake_permid_x)

    def test_findPeers(self):
        find_list = self.pdb.findPeers('ip', '88.88.88.88')
        assert len(find_list) == 16

        find_list = self.pdb.findPeers('ip', '1.2.3.4')
        assert len(find_list) == 0

        self.pdb = PeerDBHandler.getInstance()
        find_list = self.pdb.findPeers('permid', self.p1)
        assert len(find_list) == 1 and find_list[0]['permid'] == self.p1

    def test_updatePeer(self):
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid': fake_permid_x, 'ip': '1.2.3.4', 'port': 234,
                  'name': 'fake peer x', 'last_seen': 12345}
        oldsize = self.pdb.size()
        self.pdb.addPeer(fake_permid_x, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)
        p = self.pdb.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.4'
        assert p['port'] == 234
        assert p['name'] == 'fake peer x'

        self.pdb.updatePeer(fake_permid_x, ip='4.3.2.1')
        self.pdb.updatePeer(fake_permid_x, port=432)
        self.pdb.updatePeer(fake_permid_x, last_seen=1234567)
        p = self.pdb.getPeer(fake_permid_x)
        assert p['ip'] == '4.3.2.1'
        assert p['port'] == 432
        assert p['last_seen'] == 1234567

        self.pdb._db.deletePeer(fake_permid_x, force=True)
        p = self.pdb.getPeer(fake_permid_x)
        assert p == None
        assert self.pdb.size() == oldsize

    def test_deletePeer(self):
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid': fake_permid_x, 'ip': '1.2.3.4', 'port': 234,
                  'name': 'fake peer x', 'last_seen': 12345, 'friend': 1, 'superpeer': 0}
        oldsize = self.pdb.size()
        p = self.pdb.getPeer(fake_permid_x)
        assert p == None, p

        self.pdb.addPeer(fake_permid_x, peer_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)
        assert self.pdb.hasPeer(fake_permid_x)
        p = self.pdb.getPeer(fake_permid_x)
        assert p != None

        self.pdb.deletePeer(fake_permid_x, force=False)
        assert self.pdb.hasPeer(fake_permid_x)

        self.pdb.deletePeer(fake_permid_x, force=True)
        assert self.pdb.size() == oldsize
        assert not self.pdb.hasPeer(fake_permid_x)

        p = self.pdb.getPeer(fake_permid_x)
        assert p == None

        self.pdb.deletePeer(fake_permid_x, force=True)
        assert self.pdb.size() == oldsize

        p = self.pdb.getPeer(fake_permid_x)
        assert p == None, p

        self.pdb.deletePeer(fake_permid_x, force=True)
        assert self.pdb.size() == oldsize

    def test_updateTimes(self):
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid': fake_permid_x, 'ip': '1.2.3.4', 'port': 234,
                  'name': 'fake peer x', 'last_seen': 12345, 'connected_times': 3}
        oldsize = self.pdb.size()
        p = self.pdb.getPeer(fake_permid_x)
        assert p == None, p

        self.pdb.addPeer(fake_permid_x, peer_x)
        assert self.pdb.hasPeer(fake_permid_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)

        self.pdb.updateTimes(fake_permid_x, 'connected_times')
        sql = 'select connected_times from Peer where permid=' + repr(bin2str(fake_permid_x))
        ct = self.pdb._db.fetchone(sql)
        assert ct == 4, ct

        self.pdb.updateTimes(fake_permid_x, 'buddycast_times')
        sql = 'select buddycast_times from Peer where permid=' + repr(bin2str(fake_permid_x))
        ct = self.pdb._db.fetchone(sql)
        assert ct == 1, ct

        self.pdb.updateTimes(fake_permid_x, 'buddycast_times', 3)
        sql = 'select buddycast_times from Peer where permid=' + repr(bin2str(fake_permid_x))
        ct = self.pdb._db.fetchone(sql)
        assert ct == 4, ct

        self.pdb.deletePeer(fake_permid_x, force=True)
        assert not self.pdb.hasPeer(fake_permid_x)

    def test_getPermIDByIP(self):
        fake_permid_x = 'fake_permid_x' + '0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid': fake_permid_x, 'ip': '1.2.3.4', 'port': 234,
                  'name': 'fake peer x', 'last_seen': 12345, 'connected_times': 3}
        oldsize = self.pdb.size()
        p = self.pdb.getPeer(fake_permid_x)
        assert p == None, p

        self.pdb.addPeer(fake_permid_x, peer_x)
        assert self.pdb.hasPeer(fake_permid_x)
        assert self.pdb.size() == oldsize + 1, (self.pdb.size(), oldsize + 1)

        permid = self.pdb.getPermIDByIP('1.2.3.4')
        assert bin2str(permid) == bin2str(fake_permid_x)

        self.pdb.deletePeer(fake_permid_x, force=True)
        assert not self.pdb.hasPeer(fake_permid_x)
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

    def test_count(self):
        num = self.tdb.getNumberTorrents()
        assert num == 4483, num

    def test_loadTorrents(self):
        torrent_size = self.tdb.getNumberTorrents()
        res = self.tdb.getTorrents()  # only returns good torrents

        assert len(res) == torrent_size, (len(res), torrent_size)
        data = res[0]
        # print data
        assert data['category'][0] in self.tdb.category_table.keys(), data['category']
        assert data['status'] in self.tdb.status_table.keys(), data['status']
        assert data['source'] in self.tdb.src_table.keys(), data['source']
        assert len(data['infohash']) == 20

    def test_add_update_delete_Torrent(self):
        self.addTorrent()
        self.updateTorrent()
        self.deleteTorrent()

    def addTorrent(self):
        old_size = self.tdb.size()
        old_src_size = self.tdb._db.size('TorrentSource')
        old_tracker_size = self.tdb._db.size('TorrentTracker')

        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')

        sid = self.tdb._db.getTorrentID(s_infohash)
        mid = self.tdb._db.getTorrentID(m_infohash)

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

        single_torrent_id = self.tdb._db.getTorrentID(s_infohash)
        multiple_torrent_id = self.tdb._db.getTorrentID(m_infohash)

        assert self.tdb.getInfohash(single_torrent_id) == s_infohash

        single_name = 'Tribler_4.1.7_src.zip'
        multiple_name = 'Tribler_4.1.7_src'

        assert self.tdb.size() == old_size + 2, old_size - self.tdb.size()
        assert old_src_size + 1 == self.tdb._db.size('TorrentSource')
        assert old_tracker_size + 2 == self.tdb._db.size('TorrentTracker'), self.tdb._db.size('TorrentTracker') - old_tracker_size

        sname = self.tdb.getOne('name', torrent_id=single_torrent_id)
        assert sname == single_name, (sname, single_name)
        mname = self.tdb.getOne('name', torrent_id=multiple_torrent_id)
        assert mname == multiple_name, (mname, multiple_name)

        s_size = self.tdb.getOne('length', torrent_id=single_torrent_id)
        assert s_size == 1583233, s_size
        m_size = self.tdb.getOne('length', torrent_id=multiple_torrent_id)
        assert m_size == 5358560, m_size

        # TODO: action is flagged as XXX causing this torrent to be XXX instead of other
        cat = self.tdb.getOne('category_id', torrent_id=multiple_torrent_id)
        # assert cat == 8, cat  # other

        sid = self.tdb._db.getOne('TorrentSource', 'source_id', name=src)
        assert sid > 1
        m_sid = self.tdb.getOne('source_id', torrent_id=multiple_torrent_id)
        assert sid == m_sid
        s_sid = self.tdb.getOne('source_id', torrent_id=single_torrent_id)
        assert 1 == s_sid
        s_status = self.tdb.getOne('status_id', torrent_id=single_torrent_id)
        assert s_status == 0

        m_comment = self.tdb.getOne('comment', torrent_id=multiple_torrent_id)
        comments = 'www.tribler.org'
        assert m_comment.find(comments) > -1
        comments = 'something not inside'
        assert m_comment.find(comments) == -1

        m_trackers = self.tdb.getTracker(m_infohash, 0)  # db._db.getAll('TorrentTracker', 'tracker', 'torrent_id=%d'%multiple_torrent_id)
        assert len(m_trackers) == 1
        assert ('http://tpb.tracker.thepiratebay.org/announce', 1) in m_trackers, m_trackers

        s_torrent = self.tdb.getTorrent(s_infohash)
        m_torrent = self.tdb.getTorrent(m_infohash)
        assert s_torrent['name'] == 'Tribler_4.1.7_src.zip', s_torrent['name']
        assert m_torrent['name'] == 'Tribler_4.1.7_src', m_torrent['name']
        assert m_torrent['last_check_time'] == 0

    def updateTorrent(self):
        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')
        self.tdb.updateTorrent(m_infohash, relevance=3.1415926, category=['Videoclips'],
                         status='good', progress=23.5, seeder=123, leecher=321,
                         last_check_time=1234567, ignore_number=1, retry_number=2,
                         other_key1='abcd', other_key2=123)
        multiple_torrent_id = self.tdb._db.getTorrentID(m_infohash)
        res_r = self.tdb.getOne('relevance', torrent_id=multiple_torrent_id)
        # assert 3.1415926 == res_r
        self.tdb.updateTorrentRelevance(m_infohash, 1.41421)
        res_r = self.tdb.getOne('relevance', torrent_id=multiple_torrent_id)
        # assert 1.41421 == res_r
        cid = self.tdb.getOne('category_id', torrent_id=multiple_torrent_id)
        # assert cid == 2, cid
        sid = self.tdb.getOne('status_id', torrent_id=multiple_torrent_id)
        assert sid == 1
        p = self.tdb.mypref_db.getOne('progress', torrent_id=multiple_torrent_id)
        assert p == None, p
        seeder = self.tdb.getOne('num_seeders', torrent_id=multiple_torrent_id)
        assert seeder == 123
        leecher = self.tdb.getOne('num_leechers', torrent_id=multiple_torrent_id)
        assert leecher == 321
        last_check_time = self.tdb._db.getOne('TorrentTracker', 'last_check', announce_tier=1, torrent_id=multiple_torrent_id)
        assert last_check_time == 1234567, last_check_time
        ignore_number = self.tdb._db.getOne('TorrentTracker', 'ignored_times', announce_tier=1, torrent_id=multiple_torrent_id)
        assert ignore_number == 1
        retry_number = self.tdb._db.getOne('TorrentTracker', 'retried_times', announce_tier=1, torrent_id=multiple_torrent_id)
        assert retry_number == 2

    def deleteTorrent(self):
        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')

        assert self.tdb.deleteTorrent(s_infohash, delete_file=True)
        assert self.tdb.deleteTorrent(m_infohash)

        assert not self.tdb.hasTorrent(s_infohash)
        assert not self.tdb.hasTorrent(m_infohash)
        assert not os.path.isfile(os.path.join(self.getStateDir(), 'single.torrent'))
        m_trackers = self.tdb.getTracker(m_infohash, 0)
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

    def tearDown(self):
        MyPreferenceDBHandler.delInstance()

        AbstractDB.tearDown(self)

    def test_getPrefList(self):
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 24

    def test_getCreationTime(self):
        infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        infohash = str2bin(infohash_str_126)
        ct = self.mdb.getCreationTime(infohash)
        assert ct == 1194966300, ct

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
        p = self.mdb.getOne(('torrent_id', 'destination_path', 'progress', 'creation_time'), torrent_id=126)
        torrent_id = p[0]
        infohash = self.mdb._db.getInfohash(torrent_id)
        destpath = p[1]
        progress = p[2]
        creation_time = p[3]
        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 22
        assert infohash not in pl

        data = {'destination_path': destpath}
        self.mdb.addMyPreference(torrent_id, data)
        p2 = self.mdb.getOne(('torrent_id', 'destination_path', 'progress', 'creation_time'), torrent_id=126)
        assert p2[0] == p[0] and p2[1] == p[1] and p2[2] == 0 and time() - p2[3] < 10, p2

        self.mdb.deletePreference(torrent_id)
        pl = self.mdb.getMyPrefListInfohash()
        assert len(pl) == 22
        assert infohash not in pl

        data = {'destination_path': destpath, 'progress': progress, 'creation_time': creation_time}
        self.mdb.addMyPreference(torrent_id, data)
        p3 = self.mdb.getOne(('torrent_id', 'destination_path', 'progress', 'creation_time'), torrent_id=126)
        assert p3 == p, p3

    def test_updateProgress(self):
        infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        infohash = str2bin(infohash_str_126)
        torrent_id = self.mdb._db.getTorrentID(infohash)
        assert torrent_id == 126
        assert self.mdb.hasMyPreference(torrent_id)
        self.mdb.updateProgress(torrent_id, 3.14)
        p = self.mdb.getOne('progress', torrent_id=torrent_id)
        assert p == 3.14

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
