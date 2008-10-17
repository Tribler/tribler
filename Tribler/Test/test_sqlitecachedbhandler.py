import os
import sys
import unittest
import tempfile
from traceback import print_exc
import thread, threading
from time import time
from binascii import unhexlify
from shutil import copy as copyFile, move

if os.path.exists(__file__):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE.txt'):
    BASE_DIR = '.'
    
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin
from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler, MyDBHandler, BasicDBHandler, PeerDBHandler, PreferenceDBHandler, SuperPeerDBHandler, FriendDBHandler
from Tribler.Category.Category import Category

def extract_db_files(file_dir, file_name):
    try:
        import tarfile
        tar=tarfile.open(os.path.join(file_dir, file_name), 'r|gz')
        for member in tar:
            print "extract file", member
            tar.extract(member)
            dest = os.path.join(file_dir,member.name)
            dest_dir = os.path.dirname(dest)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            move(member.name, dest)
        tar.close()
        return True
    except:
        print_exc()
        return False

DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = None
FILES_DIR = os.path.abspath(os.path.join(BASE_DIR, 'Test/extend_db_dir/'))
TRIBLER_DB_PATH = os.path.join(FILES_DIR, 'tribler.sdb')
STATE_FILE_NAME_PATH = os.path.join(FILES_DIR, 'tribler.sdb-journal')
TRIBLER_DB_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_tribler.sdb')

S_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_single.torrent')
S_TORRENT_PATH = os.path.join(FILES_DIR, 'single.torrent')

M_TORRENT_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_multiple.torrent')    
M_TORRENT_PATH = os.path.join(FILES_DIR, 'multiple.torrent')    

BUSYTIMEOUT = 5000
SHOW_NOT_TESTED_FUNCTIONS = False    # Enable this to show the functions not tested yet

def init():
    if not os.path.isfile(TRIBLER_DB_PATH_BACKUP):
        got = extract_db_files(FILES_DIR, 'bak_tribler.tar.gz')
        if not got:
            print >> sys.stderr, "Please download bak_tribler.sdb from http://www.st.ewi.tudelft.nl/~jyang/donotremove/bak_tribler.sdb and save it as", os.path.abspath(TRIBLER_DB_PATH_BACKUP)
            sys.exit(1)
    if os.path.isfile(TRIBLER_DB_PATH_BACKUP):
        copyFile(TRIBLER_DB_PATH_BACKUP, TRIBLER_DB_PATH)
        #print "refresh sqlite db", TRIBLER_DB_PATH
        if os.path.exists(STATE_FILE_NAME_PATH):
            os.remove(STATE_FILE_NAME_PATH)
            print "remove journal file"
    SQLiteCacheDB.getInstance().initDB(TRIBLER_DB_PATH, busytimeout=BUSYTIMEOUT)
    TorrentDBHandler.getInstance().register(Category.getInstance(os.path.join(BASE_DIR, '..')),'.')

def getFuncs2Test(calss_name):
    return filter(lambda s:s != 'lock' and not s.startswith('__') and s not in dir(BasicDBHandler), dir(calss_name))
            
SQLiteCacheDB.DEBUG = False

class TestSqliteBasicDBHandler(unittest.TestCase):
    
    def setUp(self):
        db_path = TRIBLER_DB_PATH
        self.sqlitedb = SQLiteCacheDB.getInstance()
        self.sqlitedb.initDB(db_path, busytimeout=BUSYTIMEOUT)
        
    def tearDown(self):
        SQLiteCacheDB.getInstance().close()
            
    def test_size(self):
        table_name = 'Peer'
        db = BasicDBHandler(self.sqlitedb,table_name)
        size = db.size()
        assert size == 3995,size

    def test_getOne(self):
        table_name = 'Peer'
        db = BasicDBHandler(self.sqlitedb,table_name)
        
        ip = db.getOne('ip', peer_id=1)
        assert ip == '68.108.115.221', ip
        
        pid = db.getOne('peer_id', ip='68.108.115.221')
        assert pid == 1, pid
        
        name = db.getOne('name', ip='68.108.115.221', port=6881)
        assert name == 'Thomas-PC', name
        
        name = db.getOne('name', ip='68.108.115.221', port=6882)
        assert name == None, name
        
        tid = db.getOne('peer_id', conj='OR', ip='68.108.115.221', name='Thomas-PC')
        assert tid == 1, tid
        
        tid = db.getOne('peer_id', conj='OR', ip='68.108.115.221', name='asdfasfasfXXXXXXxx...')
        assert tid == 1, tid

        tid = db.getOne('peer_id', conj='OR', ip='1.1.1.123', name='Thomas-PC')
        assert tid == 1, tid

        lbt = db.getOne('last_buddycast', peer_id=1)
        assert lbt == 1193379432, lbt
        
        name, ip, lbt = db.getOne(('name','ip','last_buddycast'), peer_id=1)
        assert name == 'Thomas-PC' and ip == '68.108.115.221' and lbt == 1193379432, (name, ip, lbt)
        
        values = db.getOne('*', peer_id=1)
        results = (1, u'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAA6SYI4NHxwQ8P7P8QXgWAP+v8SaMVzF5+fSUHdAMrs6NvL5Epe1nCNSdlBHIjNjEiC5iiwSFZhRLsr', u'Thomas-PC', u'68.108.115.221', 6881, None, 2, 12.537961593122299, 0, 0, 1194966306, 1193379769, 1193379432, 1, 1, 0, 0, 0, 0)
        for i in range(len(values)):
            assert values[i] == results[i], (i, values[i], results[i])
        
    def test_getAll(self):
        table_name = 'Peer'
        db = BasicDBHandler(self.sqlitedb,table_name)
        
        ips = db.getAll('ip')
        assert len(ips) == 3995, len(ips)
        
        ips = db.getAll('distinct ip')
        assert len(ips) == 3492, len(ips)
        
        ips = db.getAll('ip', "ip like '130.%'")
        assert len(ips) == 26, len(ips)
        
        ids = db.getAll('peer_id', 'thumbnail is NULL')
        assert len(ids) == 3995, len(ids)
        
        ips = db.getAll('ip', "ip like '88.%'", port=7762, conj='or')
        assert len(ips) == 495, len(ips)
        
        ips = db.getAll('ip', "ip like '88.%'", port=7762, order_by='ip')
        assert len(ips) == 6, len(ips)
        assert ips[0][0] == '88.14.171.194', ips[0]
        
        names = db.getAll('name', "ip like '88.%'", port=7762, order_by='ip', limit=4, offset=1)
        assert len(names) == 4
        assert names[2][0] == 'mb48', names
        # select name from Peer where ip like '88.%' and port==7762 order by ip limit 4 offset 3
        
        ips = db.getAll('count(distinct ip), port', group_by='port')
        # select count(distinct ip), port from Peer group by port 
        for nip, port in ips:
            if port == 6881:
                assert nip == 2842, nip
                break


class TestSqliteMyDBHandler(unittest.TestCase):
    
    def setUp(self):
        db_path = TRIBLER_DB_PATH
        db = SQLiteCacheDB.getInstance()
        db.openDB(db_path, busytimeout=BUSYTIMEOUT)
        
    def tearDown(self):
        SQLiteCacheDB.getInstance().close()
            
    def test_get(self):
        db = MyDBHandler.getInstance()
        value = db.get('version')
        assert value == '1', value
        
    def test_put(self):
        db = MyDBHandler.getInstance()
        new_ip = '127.0.0.1'
        db.put('ip', new_ip)
        value = db.get('ip')
        assert value == new_ip, value

        new_ip = ''
        db.put('ip', new_ip)
        value = db.get('ip')
        assert value == new_ip, (value, new_ip)
        
class TestSuperPeerDBHandler(unittest.TestCase):
    
    def setUp(self):
        db_path = TRIBLER_DB_PATH
        db = SQLiteCacheDB.getInstance()
        db.openDB(db_path, busytimeout=BUSYTIMEOUT)
        self.sp1 = '0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04\x00\\\xdfXv\xffX\xf2\xfe\x96\xe1_]\xf5\x1b\xb4\x91\x91\xa5I\xf0nl\x81\xd2A\xfb\xb7u)\x01T\xa9*)r\x9b\x81s\xb7j\xd2\xecrSg$;\xc8"7s\xecSF\xd3\x0bgK\x1c'
        self.sp2 = '0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04\x01\xdb\x80+O\xd9N7`\xfc\xd3\xdd\xf0 \xfdC^\xc9\xd7@\x97\xaa\x91r\x1c\xdeL\xf2n\x9f\x00U\xc1A\xf9Ae?\xd8t}_c\x08\xb3G\xf8g@N! \xa0\x90M\xfb\xca\xcfZ@'
        
    def tearDown(self):
        s = SQLiteCacheDB.getInstance()
        s.close()
            
    def _test_size(self):
        db = SuperPeerDBHandler.getInstance()
        size = db.size()
        assert size == 8, size
        
    def _test_getSuperPeerList(self):
        db = SuperPeerDBHandler.getInstance()
        sps = db.getSuperPeers()
        assert self.sp1 in sps
        assert self.sp2 in sps
        
    def test_setSuperPeer(self):
        db = SuperPeerDBHandler.getInstance()
        
        sps = db.getSuperPeers()
        assert len(sps) == 8, len(sps)
        
        db.peer_db_handler.addPeer(self.sp1, {'superpeer':0})
        sps = db.getSuperPeers()
        assert self.sp1 not in sps
        assert len(sps) == 7, len(sps)
        
        db.peer_db_handler.addPeer(self.sp1, {'superpeer':0})
        sps = db.getSuperPeers()
        assert self.sp1 not in sps
        assert len(sps) == 7

        db.peer_db_handler.addPeer(self.sp1, {'superpeer':1})
        sps = db.getSuperPeers()
        assert self.sp1 in sps
        assert len(sps) == 8
        
        db.peer_db_handler.addPeer(self.sp1, {'superpeer':1})
        sps = db.getSuperPeers()
        assert self.sp1 in sps
        assert len(sps) == 8
        
    def test_addExternalSuperPeer(self):
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 'name':'fake peer x'}
        db = SuperPeerDBHandler.getInstance()
        db.addExternalSuperPeer(peer_x)
        sps = db.getSuperPeers()
        assert fake_permid_x in sps
        assert len(sps) == 9, len(sps)
        
        db.addExternalSuperPeer(peer_x)
        sps = db.getSuperPeers()
        assert fake_permid_x in sps
        assert len(sps) == 9, len(sps)

        db._db.deletePeer(fake_permid_x, force=True)
        sps = db.getSuperPeers()
        assert fake_permid_x not in sps
        assert len(sps) == 8, len(sps)

        db._db.deletePeer(fake_permid_x, force=True)
        sps = db.getSuperPeers()
        assert fake_permid_x not in sps
        assert len(sps) == 8, len(sps)
        
class TestFriendDBHandler(unittest.TestCase):
    
    def setUp(self):
        db_path = TRIBLER_DB_PATH
        db = SQLiteCacheDB.getInstance()
        db.openDB(db_path, busytimeout=BUSYTIMEOUT)
        self.sp1 = '0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04\x00\\\xdfXv\xffX\xf2\xfe\x96\xe1_]\xf5\x1b\xb4\x91\x91\xa5I\xf0nl\x81\xd2A\xfb\xb7u)\x01T\xa9*)r\x9b\x81s\xb7j\xd2\xecrSg$;\xc8"7s\xecSF\xd3\x0bgK\x1c'
        self.sp2 = '0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04\x01\xdb\x80+O\xd9N7`\xfc\xd3\xdd\xf0 \xfdC^\xc9\xd7@\x97\xaa\x91r\x1c\xdeL\xf2n\x9f\x00U\xc1A\xf9Ae?\xd8t}_c\x08\xb3G\xf8g@N! \xa0\x90M\xfb\xca\xcfZ@'
        self.fr1 = str2bin('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAL/l2IyVa6lc3KAqQyEnR++rIzi+AamnbzXHCxOFAFy67COiBhrC79PLzzUiURbHDx21QA4p8w3UDHLA')
        
    def tearDown(self):
        SQLiteCacheDB.getInstance().close()
            
    def test_size(self):
        db = FriendDBHandler.getInstance()
        size = db.size()
        assert size == 2, size
        
    def test_getFriends(self):
        db = FriendDBHandler.getInstance()
        friends = db.getFriends()
        assert self.sp1 not in friends
        assert self.fr1 in friends
        
    def test_setFriendState(self):
        db = FriendDBHandler.getInstance()
        db.setFriendState(self.sp1)
        assert db.getFriendState(self.sp1)
        sps = db.getFriends()
        assert self.sp1 in sps
        assert len(sps) == 3
        
        db.setFriendState(self.sp1)
        assert db.getFriendState(self.sp1)
        sps = db.getFriends()
        assert self.sp1 in sps
        assert len(sps) == 3
        
        db.deleteFriend(self.sp1)
        assert not db.getFriendState(self.sp1)
        sps = db.getFriends()
        assert self.sp1 not in sps
        assert len(sps) == 2
        
        db.deleteFriend(self.sp1)
        assert not db.getFriendState(self.sp1)
        sps = db.getFriends()
        assert self.sp1 not in sps
        assert len(sps) == 2
        
    def test_addExternalFriend(self):
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 'name':'fake peer x'}
        db = FriendDBHandler.getInstance()
        db.addExternalFriend(peer_x)
        sps = db.getFriends()
        assert fake_permid_x in sps
        assert len(sps) == 3, len(sps)
        
        db.addExternalFriend(peer_x)
        sps = db.getFriends()
        assert fake_permid_x in sps
        assert len(sps) == 3, len(sps)

        db._db.deletePeer(fake_permid_x, force=True)
        sps = db.getFriends()
        assert fake_permid_x not in sps
        assert len(sps) == 2, len(sps)
        
        db._db.deletePeer(fake_permid_x, force=True)
        sps = db.getFriends()
        assert fake_permid_x not in sps
        assert len(sps) == 2, len(sps)
        
        
class TestSqlitePeerDBHandler(unittest.TestCase):
    
    def setUp(self):
        db_path = TRIBLER_DB_PATH
        db = SQLiteCacheDB.getInstance()
        db.openDB(db_path, busytimeout=BUSYTIMEOUT)
        self.sp1 = '0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04\x00\\\xdfXv\xffX\xf2\xfe\x96\xe1_]\xf5\x1b\xb4\x91\x91\xa5I\xf0nl\x81\xd2A\xfb\xb7u)\x01T\xa9*)r\x9b\x81s\xb7j\xd2\xecrSg$;\xc8"7s\xecSF\xd3\x0bgK\x1c'
        self.sp2 = '0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04\x01\xdb\x80+O\xd9N7`\xfc\xd3\xdd\xf0 \xfdC^\xc9\xd7@\x97\xaa\x91r\x1c\xdeL\xf2n\x9f\x00U\xc1A\xf9Ae?\xd8t}_c\x08\xb3G\xf8g@N! \xa0\x90M\xfb\xca\xcfZ@'
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        hp = db.hasPeer(fake_permid_x)
        assert not hp
        
    def tearDown(self):
        SQLiteCacheDB.getInstance().close()
        
    def test_getList(self):
        db = PeerDBHandler.getInstance()
        sp1 = db.getPeer(self.sp1)
        sp2 = db.getPeer(self.sp2)
        assert isinstance(sp1, dict)
        assert isinstance(sp2, dict)
        assert sp1['port'] == 7007
        assert sp2['port'] == 7004

    def test_getPeerSim(self):
        db = PeerDBHandler.getInstance()
        permid_str = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEACPJqLjmKeMNRwkCNKkPH51gjQ5e7u4s2vWv9I/AALXtpf+bFPtY8cyFv6OCzisYDo+brgqOxAtuNZwP'
        permid = str2bin(permid_str)
        sim = db.getPeerSim(permid)
        assert sim == 5.82119645394964
        
        permid_str = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAB0XbUrw5b8CrTrMZST1SPyrzjgSzIE6ynALtlZASGAb+figVXRRGpKW6MSal3KnEm1/q0P3JPWrhCE'
        permid = str2bin(permid_str)
        sim = db.getPeerSim(permid)
        assert sim == 0
        
    def test_getPeerList(self):
        db = PeerDBHandler.getInstance()
        peerlist = db.getPeerList()
        assert len(peerlist) == 3995
        peerlist.sort()
        assert bin2str(peerlist[345]) == 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEACxVRvG/Gr19EAPJru2Z5gjctEzv973/PJCQIua2ATMP6euq+Kf4gYpdKbsB/PWqJnfY/wSKPHHfIByV'

    def test_getPeers(self):
        db = PeerDBHandler.getInstance()
        peerlist = db.getPeerList()
        peerlist.sort()
        pl = peerlist[:10]
        peers = db.getPeers(pl, ['permid', 'peer_id', 'ip', 'port', 'name'])
        #for p in peers: print p
        assert peers[7]['name'] == 'vasinc2006', peers[8]['name']
        assert peers[1]['ip'] == '68.108.115.221'
        assert peers[3]['peer_id'] == 3
        
    def test_addPeer(self):
        db = PeerDBHandler.getInstance()
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 
                  'name':'fake peer x', 'last_seen':12345}
        oldsize = db.size()
        db.addPeer(fake_permid_x, peer_x)
        assert db.size() == oldsize+1, (db.size(), oldsize+1)
        #db.addPeer(fake_permid_x, peer_x)
        #assert db.size() == oldsize+1
        p = db.getPeer(fake_permid_x)
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
        db.addPeer(fake_permid_x, peer_x, update_dns=False)
        p = db.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.4'
        assert p['port'] == 234
        assert p['last_seen'] == 1234567, p['last_seen']

        peer_x['ip'] = '4.3.2.1'
        peer_x['port'] = 432
        peer_x['last_seen'] = 12345
        db.addPeer(fake_permid_x, peer_x, update_dns=True)
        p = db.getPeer(fake_permid_x)
        assert p['ip'] == '4.3.2.1'
        assert p['port'] == 432
        assert p['last_seen'] == 12345

        peer_x['ip'] = '1.2.3.1'
        peer_x['port'] = 234
        db.addPeer(fake_permid_x, peer_x, update_dns=False)
        p = db.getPeer(fake_permid_x)
        assert p['ip'] == '4.3.2.1'
        assert p['port'] == 432
        assert p['last_seen'] == 12345

        peer_x['ip'] = '1.2.3.4'
        peer_x['port'] = 234
        peer_x['last_seen'] = 1234569
        db.addPeer(fake_permid_x, peer_x, update_dns=True)
        p = db.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.4'
        assert p['port'] == 234
        assert p['last_seen'] == 1234569

        peer_x['ip'] = '1.2.3.5'
        peer_x['port'] = 236
        db.addPeer(fake_permid_x, peer_x, update_dns=True)
        p = db.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.5'
        assert p['port'] == 236

        db._db.deletePeer(fake_permid_x, force=True)
        p = db.getPeer(fake_permid_x)
        assert p == None
        assert db.size() == oldsize

    def test_aa_hasPeer(self):
        db = PeerDBHandler.getInstance()
        assert db.hasPeer(self.sp1)
        assert db.hasPeer(self.sp2)
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        assert not db.hasPeer(fake_permid_x)
        
    def test_findPeers(self):
        db = PeerDBHandler.getInstance()
        find_list = db.findPeers('ip', '130.161.211.199')
        assert len(find_list) == 3
        
        find_list = db.findPeers('ip', '1.2.3.4')
        assert len(find_list) == 0
        
        db = PeerDBHandler.getInstance()
        find_list = db.findPeers('permid', self.sp1)
        assert len(find_list) == 1 and find_list[0]['permid'] == self.sp1
        #assert len(find_list) == 3 and 901 in find_list
    
    def test_updatePeer(self):
        db = PeerDBHandler.getInstance()
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 
                  'name':'fake peer x', 'last_seen':12345}
        oldsize = db.size()
        db.addPeer(fake_permid_x, peer_x)
        assert db.size() == oldsize+1, (db.size(), oldsize+1)
        p = db.getPeer(fake_permid_x)
        assert p['ip'] == '1.2.3.4'
        assert p['port'] == 234
        assert p['name'] == 'fake peer x'
        
        db.updatePeer(fake_permid_x, ip='4.3.2.1')
        db.updatePeer(fake_permid_x, port=432)
        db.updatePeer(fake_permid_x, last_seen=1234567)
        p = db.getPeer(fake_permid_x)
        assert p['ip'] == '4.3.2.1'
        assert p['port'] == 432
        assert p['last_seen'] == 1234567

        db._db.deletePeer(fake_permid_x, force=True)
        p = db.getPeer(fake_permid_x)
        assert p == None
        assert db.size() == oldsize

    def test_deletePeer(self):
        db = PeerDBHandler.getInstance()
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 
                  'name':'fake peer x', 'last_seen':12345, 'friend':1, 'superpeer':0}
        oldsize = db.size()
        p = db.getPeer(fake_permid_x)
        assert p == None, p
        
        db.addPeer(fake_permid_x, peer_x)
        assert db.size() == oldsize+1, (db.size(), oldsize+1)
        assert db.hasPeer(fake_permid_x)
        p = db.getPeer(fake_permid_x)
        assert p != None
        
        db.deletePeer(fake_permid_x, force=False)
        assert db.hasPeer(fake_permid_x)
        
        db.deletePeer(fake_permid_x, force=True)
        assert db.size() == oldsize
        assert not db.hasPeer(fake_permid_x)
        
        p = db.getPeer(fake_permid_x)
        assert p == None
        
        db.deletePeer(fake_permid_x, force=True)
        assert db.size() == oldsize
        
        p = db.getPeer(fake_permid_x)
        assert p == None, p
        
        db.deletePeer(fake_permid_x, force=True)
        assert db.size() == oldsize
        
    def test_updateTimes(self):
        db = PeerDBHandler.getInstance()
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 
                  'name':'fake peer x', 'last_seen':12345, 'connected_times':3}
        oldsize = db.size()
        p = db.getPeer(fake_permid_x)
        assert p == None, p
        
        db.addPeer(fake_permid_x, peer_x)
        assert db.hasPeer(fake_permid_x)
        assert db.size() == oldsize+1, (db.size(), oldsize+1)
        
        db.updateTimes(fake_permid_x, 'connected_times')
        sql = 'select connected_times from Peer where permid='+repr(bin2str(fake_permid_x))
        ct = db._db.fetchone(sql)
        assert ct == 4, ct
        
        db.updateTimes(fake_permid_x, 'buddycast_times')
        sql = 'select buddycast_times from Peer where permid='+repr(bin2str(fake_permid_x))
        ct = db._db.fetchone(sql)
        assert ct == 1, ct
        
        db.updateTimes(fake_permid_x, 'buddycast_times', 3)
        sql = 'select buddycast_times from Peer where permid='+repr(bin2str(fake_permid_x))
        ct = db._db.fetchone(sql)
        assert ct == 4, ct
        
        db.deletePeer(fake_permid_x, force=True)
        assert not db.hasPeer(fake_permid_x)
        
    def test_getPermIDByIP(self):
        db = PeerDBHandler.getInstance()
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 
                  'name':'fake peer x', 'last_seen':12345, 'connected_times':3}
        oldsize = db.size()
        p = db.getPeer(fake_permid_x)
        assert p == None, p
        
        db.addPeer(fake_permid_x, peer_x)
        assert db.hasPeer(fake_permid_x)
        assert db.size() == oldsize+1, (db.size(), oldsize+1)
        
        permid = db.getPermIDByIP('1.2.3.4')
        assert bin2str(permid) == bin2str(fake_permid_x)
        
        db.deletePeer(fake_permid_x, force=True)
        assert not db.hasPeer(fake_permid_x)
        assert db.size() == oldsize
        
    def test_loadPeers(self):
        db = PeerDBHandler.getInstance()
        peer_size = db.size()
        res = db.getGUIPeers()
        assert len(res) == 1477, len(res)
        data = res[0]
        p = db.getPeer(data['permid'])
        assert p['name'] == data['name']
        assert 70 < len(data['permid']) < 90    # must be binary
        
class TestPreferenceDBHandler(unittest.TestCase):
    
    def setUp(self):
        db_path = TRIBLER_DB_PATH
        db = SQLiteCacheDB.getInstance()
        db.openDB(db_path, busytimeout=BUSYTIMEOUT)
        
    def tearDown(self):
        SQLiteCacheDB.getInstance().close()
    
    def test_getPrefList(self):
        db = PreferenceDBHandler.getInstance()
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        pl = db.getPrefList(fake_permid_x)
        assert pl == [], pl
        
        truth = {3127:235, 994:20, 19:1, 5:0}
        permid = {}
        permid[3127] = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAcPezgQ13k1MSOaUrCPisWRhYuNT7Tm+q5rUgHFvAWd9b+BcSut6TCniEgHYHDnQ6TH/vxQBqtY8Loag'
        permid[994] = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAJUNmwvDaigRaM4cj7cE2O7lessqnnFEQsan7df9AZS8xeNmVsP/XXVrEt4t7e2TNicYmjn34st/sx2P'
        permid[19] = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAJv2YLuIWa4QEdOEs4CPRxQZDwZphKd/xK/tgbcALG198nNdT10znJ2sZYl+OJIvj7YfYp75PrrnWNX'
        permid[5] = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAB0XbUrw5b8CrTrMZST1SPyrzjgSzIE6ynALtlZASGAb+figVXRRGpKW6MSal3KnEm1/q0P3JPWrhCE'
        
        for pid in truth:
            pl = db.getPrefList(str2bin(permid[pid]))
            assert len(pl) == truth[pid], [pid, len(pl)]
        
    def test_addPreference(self):
        db = PeerDBHandler.getInstance()
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 
                  'name':'fake peer x', 'last_seen':12345, 'connected_times':3}
        oldsize = db.size()
        oldinfohash_size = db._db.size('Torrent')
        p = db.getPeer(fake_permid_x)
        assert p == None, p
        
        db.addPeer(fake_permid_x, peer_x)
        assert db.hasPeer(fake_permid_x)
        assert db.size() == oldsize+1, (db.size(), oldsize+1)
        
        fake_infoahsh = 'fake_infohash_1'+'0R0\x10\x00\x07*\x86H\xce=\x02'
        fake_infoahsh2 = 'fake_infohash_2'+'0R0\x10\x00\x07*\x86H\xce=\x02'
        prefdb = PreferenceDBHandler.getInstance()
        oldpref_size = prefdb.size()
        prefdb.addPreference(fake_permid_x, fake_infoahsh)
        prefdb.addPreference(fake_permid_x, fake_infoahsh2)
        assert prefdb.size() == oldpref_size + 2
        assert oldinfohash_size + 2 == db._db.size('Torrent'), (oldinfohash_size + 2, db._db.size('Torrent'))
        
        pl = prefdb.getPrefList(fake_permid_x, return_infohash=True)
        assert len(pl) == 2
        assert fake_infoahsh in pl
        assert fake_infoahsh2 in pl

        pl = prefdb.getPrefList(fake_permid_x, return_infohash=True)
        assert len(pl) == 2, pl
        assert fake_infoahsh in pl
        assert fake_infoahsh2 in pl
        prefdb._deletePeer(fake_permid_x)
        pl = prefdb.getPrefList(fake_permid_x)
        assert pl == []
        assert prefdb.size() == oldpref_size, (prefdb.size(), oldpref_size)
        
        db.deletePeer(fake_permid_x, force=True)
        assert not db.hasPeer(fake_permid_x)
        assert db.size() == oldsize        
        
        # add again
        db.addPeer(fake_permid_x, peer_x)
        assert db.hasPeer(fake_permid_x)
        assert db.size() == oldsize+1
        
        prefdb.addPreference(fake_permid_x, fake_infoahsh)
        prefdb.addPreference(fake_permid_x, fake_infoahsh2)
        assert prefdb.size() == oldpref_size + 2
        assert oldinfohash_size + 2 == db._db.size('Torrent')
        
        pl = prefdb.getPrefList(fake_permid_x, return_infohash=True)
        assert len(pl) == 2
        assert fake_infoahsh in pl
        assert fake_infoahsh2 in pl
        
        db.deletePeer(fake_permid_x, force=True)
        assert not db.hasPeer(fake_permid_x)
        assert db.size() == oldsize      
        pl = prefdb.getPrefList(fake_permid_x)
        assert pl == []
        assert prefdb.size() == oldpref_size, (prefdb.size(), oldpref_size)
                
        db._db.deleteInfohash(fake_infoahsh)
        db._db.deleteInfohash(fake_infoahsh2)
        tid = db._db.getTorrentID(fake_infoahsh)
        assert tid is None
        tid = db._db.getTorrentID(fake_infoahsh2)
        assert tid is None
        assert oldinfohash_size == db._db.size('Torrent'), [oldinfohash_size, db._db.size('Torrent')]

    def test_addPeerPreferences(self):
        db = PeerDBHandler.getInstance()
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x00\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 
                  'name':'fake peer x', 'last_seen':12345, 'connected_times':3}
        oldsize = db.size()
        oldinfohash_size = db._db.size('Torrent')
        p = db.getPeer(fake_permid_x)
        assert p == None, p
        
        db.addPeer(fake_permid_x, peer_x)
        assert db.hasPeer(fake_permid_x)
        assert db.size() == oldsize+1, (db.size(), oldsize+1)
        
        fake_infoahsh = 'fake_infohash_1'+'0R0\x10\x00\x07*\x86H\xce=\x02'
        fake_infoahsh2 = 'fake_infohash_2'+'0R0\x10\x00\x07*\x86H\xce=\x02'
        fi = [fake_infoahsh,fake_infoahsh2]
        prefdb = PreferenceDBHandler.getInstance()
        oldpref_size = prefdb.size()
        prefdb.addPreferences(fake_permid_x, fi)
        assert prefdb.size() == oldpref_size + 2, [prefdb.size(), oldpref_size]
        assert oldinfohash_size + 2 == db._db.size('Torrent')
        
        pl = prefdb.getPrefList(fake_permid_x, return_infohash=True)
        assert len(pl) == 2
        assert fake_infoahsh in pl, (fake_infoahsh, pl)
        assert fake_infoahsh2 in pl, (fake_infoahsh2, pl)

        pl = prefdb.getPrefList(fake_permid_x, return_infohash=True)
        assert len(pl) == 2, pl
        assert fake_infoahsh in pl
        assert fake_infoahsh2 in pl
        prefdb._deletePeer(fake_permid_x)
        pl = prefdb.getPrefList(fake_permid_x, return_infohash=True)
        assert pl == []
        assert prefdb.size() == oldpref_size, (prefdb.size(), oldpref_size)
        
        db.deletePeer(fake_permid_x, force=True)
        assert not db.hasPeer(fake_permid_x)
        assert db.size() == oldsize        
        
        # add again
        db.addPeer(fake_permid_x, peer_x)
        assert db.hasPeer(fake_permid_x)
        assert db.size() == oldsize+1
        
        prefdb.addPreferences(fake_permid_x, fi)
        assert prefdb.size() == oldpref_size + 2
        assert oldinfohash_size + 2 == db._db.size('Torrent')
        
        pl = prefdb.getPrefList(fake_permid_x, return_infohash=True)
        assert len(pl) == 2
        assert fake_infoahsh in pl
        assert fake_infoahsh2 in pl
        
        db.deletePeer(fake_permid_x, force=True)
        assert not db.hasPeer(fake_permid_x)
        assert db.size() == oldsize      
        pl = prefdb.getPrefList(fake_permid_x)
        assert pl == []
        assert prefdb.size() == oldpref_size, (prefdb.size(), oldpref_size)
                
        db._db.deleteInfohash(fake_infoahsh)
        db._db.deleteInfohash(fake_infoahsh2)
        tid = db._db.getTorrentID(fake_infoahsh)
        assert tid is None
        tid = db._db.getTorrentID(fake_infoahsh2)
        assert tid is None
        assert oldinfohash_size == db._db.size('Torrent'), [oldinfohash_size, db._db.size('Torrent')]

        
class TestTorrentDBHandler(unittest.TestCase):

    def setUp(self):
        db_path = TRIBLER_DB_PATH
        db = SQLiteCacheDB.getInstance()
        db.openDB(db_path, busytimeout=BUSYTIMEOUT)
        
    def tearDown(self):
        SQLiteCacheDB.getInstance().close()

    def tested_functions(self):
        if SHOW_NOT_TESTED_FUNCTIONS:
            all_funcs = getFuncs2Test(TorrentDBHandler) 
            tested_funcs = [
                "register",
                "getInstance",
                "hasTorrent",
                "hasMetaData",
                "getNumberTorrents", "_getCategoryID",
                "getTorrents",
                "size",
                "getTorrentID",
                "_addTorrentToDB", "_addTorrentTracker",
                "getOne",
                "getTracker",
                "updateTorrent",
                "updateTorrentRelevance",
                "deleteTorrent", "_deleteTorrent", "eraseTorrentFile",
                "getNumberCollectedTorrents",
                "getTorrent",
                "freeSpace",
                "getInfohash",
            ]
            for func in all_funcs:
                if func not in tested_funcs:
                    print "TestTorrentDBHandler: not test", func
                
#    def test_misc(self):
#        db = TorrentDBHandler.getInstance()
        
    def _test_hasTorrent(self):
        infohash_str = 'AA8cTG7ZuPsyblbRE7CyxsrKUCg='
        infohash = str2bin(infohash_str)
        db = TorrentDBHandler.getInstance()
        assert db.hasTorrent(infohash) == True
        assert db.hasMetaData(infohash) == True
        fake_infoahsh = 'fake_infohash_1'+'0R0\x10\x00\x07*\x86H\xce=\x02'
        assert db.hasTorrent(fake_infoahsh) == False
        assert db.hasMetaData(fake_infoahsh) == False
        
    def test_count(self):
        db = TorrentDBHandler.getInstance()
        start = time()
        num = db.getNumberTorrents()
        assert num == 4483
        
    def test_loadTorrents(self):
        db = TorrentDBHandler.getInstance()
        torrent_size = db._db.size('CollectedTorrent')
        db2 = MyPreferenceDBHandler.getInstance()
        mypref_size = db2.size()
        res = db.getTorrents()
        ### assert len(res) == torrent_size - mypref_size, (len(res), torrent_size - mypref_size)
        res = db.getTorrents()
        len(res) == torrent_size
        data = res[0]
        #print data
        assert data['category'][0] in db.category_table.keys(), data['category']
        assert data['status'] in db.status_table.keys(), data['status']
        assert data['source'] in db.src_table.keys(), data['source']
        assert len(data['infohash']) == 20
                
    def test_add_update_delete_Torrent(self):
        self.addTorrent()
        self.updateTorrent()
        self.deleteTorrent()
        pass
                
    def addTorrent(self):
        copyFile(S_TORRENT_PATH_BACKUP, S_TORRENT_PATH)
        copyFile(M_TORRENT_PATH_BACKUP, M_TORRENT_PATH)
        
        db = TorrentDBHandler.getInstance()
        
        old_size = db.size()
        old_src_size = db._db.size('TorrentSource')
        old_tracker_size = db._db.size('TorrentTracker')
        
        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')
        
        sid = db._db.getTorrentID(s_infohash)
        mid = db._db.getTorrentID(m_infohash)
                
        single_torrent_file_path = os.path.join(FILES_DIR, 'single.torrent')
        multiple_torrent_file_path = os.path.join(FILES_DIR, 'multiple.torrent')
        
        single_infohash, single_torrent = db._readTorrentData(single_torrent_file_path)
        assert s_infohash == single_infohash
        src = 'http://www.rss.com/torrent.xml'
        multiple_infohash, multiple_torrent = db._readTorrentData(multiple_torrent_file_path, src)
        assert m_infohash == multiple_infohash
        
        db._addTorrentToDB(single_infohash, single_torrent)
        db._addTorrentToDB(multiple_infohash, multiple_torrent)
        
        single_torrent_id = db._db.getTorrentID(s_infohash)
        multiple_torrent_id = db._db.getTorrentID(m_infohash)
        
        assert db.getInfohash(single_torrent_id) == s_infohash
        
        single_name = 'Tribler_4.1.7_src.zip'
        multiple_name = 'Tribler_4.1.7_src'
        
        assert db.size() == old_size + 2, old_size - db.size()
        assert old_src_size + 1 == db._db.size('TorrentSource')
        assert old_tracker_size + 2 == db._db.size('TorrentTracker'), db._db.size('TorrentTracker')-old_tracker_size
        
        sname = db.getOne('name', torrent_id=single_torrent_id)
        assert sname == single_name, (sname,single_name)
        mname = db.getOne('name', torrent_id=multiple_torrent_id)
        assert mname == multiple_name, (mname,multiple_name)
        
        s_size = db.getOne('length', torrent_id=single_torrent_id)
        assert s_size == 1583233, s_size
        m_size = db.getOne('length', torrent_id=multiple_torrent_id)
        assert m_size == 5358560, m_size
        
        cat = db.getOne('category_id', torrent_id=multiple_torrent_id)
        assert cat == 7, cat    # other
        sid = db._db.getOne('TorrentSource', 'source_id', name=src)
        assert sid > 1
        m_sid = db.getOne('source_id', torrent_id=multiple_torrent_id)
        assert sid == m_sid
        s_sid = db.getOne('source_id', torrent_id=single_torrent_id)
        assert 1 == s_sid
        s_status = db.getOne('status_id', torrent_id=single_torrent_id)
        assert s_status == 0
        
        m_comment = db.getOne('comment', torrent_id=multiple_torrent_id)
        comments = 'www.tribler.org'
        assert m_comment.find(comments)>-1
        comments = 'something not inside'
        assert m_comment.find(comments)==-1
                
        m_trackers = db.getTracker(m_infohash, 0)    #db._db.getAll('TorrentTracker', 'tracker', 'torrent_id=%d'%multiple_torrent_id)
        assert len(m_trackers) == 1
        assert ('http://tpb.tracker.thepiratebay.org/announce',1) in m_trackers, m_trackers
        
        s_torrent = db.getTorrent(s_infohash)
        m_torrent = db.getTorrent(m_infohash)
        assert s_torrent['name'] == 'Tribler_4.1.7_src.zip'
        assert m_torrent['name'] == 'Tribler_4.1.7_src'
        assert m_torrent['last_check_time'] == 0
        assert len(s_torrent) == 16
        assert len(m_torrent) == 16 
        
    def updateTorrent(self):
        db = TorrentDBHandler.getInstance()
        
        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')
        kw = {}
        db.updateTorrent(m_infohash, relevance=3.1415926, category=['Videoclips'], 
                         status='good', progress=23.5, seeder=123, leecher=321, 
                         last_check_time=1234567, ignore_number=1, retry_number=2, 
                         other_key1='abcd', other_key2=123)
        multiple_torrent_id = db._db.getTorrentID(m_infohash)
        res_r = db.getOne('relevance', torrent_id=multiple_torrent_id)
        ### assert 3.1415926 == res_r
        db.updateTorrentRelevance(m_infohash, 1.41421)
        res_r = db.getOne('relevance', torrent_id=multiple_torrent_id)
        ### assert 1.41421 == res_r
        cid = db.getOne('category_id', torrent_id=multiple_torrent_id)
        ### assert cid == 2, cid
        sid = db.getOne('status_id', torrent_id=multiple_torrent_id)
        assert sid == 1
        p = db.mypref_db.getOne('progress', torrent_id=multiple_torrent_id)
        assert p == None, p
        seeder = db.getOne('num_seeders', torrent_id=multiple_torrent_id)
        assert seeder == 123
        leecher = db.getOne('num_leechers', torrent_id=multiple_torrent_id)
        assert leecher == 321
        last_check_time = db._db.getOne('TorrentTracker', 'last_check', announce_tier=1, torrent_id=multiple_torrent_id)
        assert last_check_time == 1234567, last_check_time
        ignore_number = db._db.getOne('TorrentTracker', 'ignored_times', announce_tier=1, torrent_id=multiple_torrent_id)
        assert ignore_number == 1
        retry_number = db._db.getOne('TorrentTracker', 'retried_times', announce_tier=1, torrent_id=multiple_torrent_id)
        assert retry_number == 2
                
    def deleteTorrent(self):
        db = TorrentDBHandler.getInstance()
        db.torrent_dir = FILES_DIR
        s_infohash = unhexlify('44865489ac16e2f34ea0cd3043cfd970cc24ec09')
        m_infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')
        
        assert db.deleteTorrent(s_infohash, delete_file=True)
        assert db.deleteTorrent(m_infohash)

        assert not db.hasTorrent(s_infohash)
        assert not db.hasTorrent(m_infohash)
        assert not os.path.isfile(S_TORRENT_PATH)
        m_trackers = db.getTracker(m_infohash, 0)
        assert len(m_trackers) == 0
        
        fake_infoahsh = 'fake_infohash_1'+'0R0\x10\x00\x07*\x86H\xce=\x02'
        assert not db.deleteTorrent(fake_infoahsh)
        
        my_infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        my_infohash = str2bin(my_infohash_str_126)
        assert not db.deleteTorrent(my_infohash)
        
    def test_getCollectedTorrentHashes(self):
        db = TorrentDBHandler.getInstance()
        res = db.getNumberCollectedTorrents()
        assert res == 4848, res
        
    def test_freeSpace(self):
        db = TorrentDBHandler.getInstance()
        old_res = db.getNumberCollectedTorrents()
        db.freeSpace(20)
        res = db.getNumberCollectedTorrents()
        assert old_res - res == 20
        init()
        
        
class TestMyPreferenceDBHandler(unittest.TestCase):
    
    def setUp(self):
        db_path = TRIBLER_DB_PATH
        db = SQLiteCacheDB.getInstance()
        db.openDB(db_path, busytimeout=BUSYTIMEOUT)
        mypref_db = MyPreferenceDBHandler.getInstance()
        mypref_db.loadData()
        
    def tearDown(self):
        SQLiteCacheDB.getInstance().close()
    
    def test_getPrefList(self):
        db = MyPreferenceDBHandler.getInstance()
        pl = db.getMyPrefListInfohash()
        assert len(pl) == 12
        
    def test_getCreationTime(self):
        db = MyPreferenceDBHandler.getInstance()
        infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        infohash = str2bin(infohash_str_126)
        ct = db.getCreationTime(infohash)
        assert ct == 1194966300, ct
        
    def test_getRecentLivePrefList(self):
        db = MyPreferenceDBHandler.getInstance()
        pl = db.getRecentLivePrefList()
        assert len(pl) == 11, (len(pl), pl)
        infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        assert bin2str(pl[0]) == infohash_str_126
        infohash_str_1279 = 'R+grUhp884MnFkt6NuLnnauZFsc='
        assert bin2str(pl[1]) == infohash_str_1279
        
        pl = db.getRecentLivePrefList(8)
        assert len(pl) == 8, (len(pl), pl)
        assert bin2str(pl[0]) == infohash_str_126
        assert bin2str(pl[1]) == infohash_str_1279

    def test_hasMyPreference(self):
        infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        infohash_str_1279 = 'R+grUhp884MnFkt6NuLnnauZFsc='
        db = MyPreferenceDBHandler.getInstance()
        assert db.hasMyPreference(str2bin(infohash_str_126))
        assert db.hasMyPreference(str2bin(infohash_str_1279))
        fake_infoahsh = 'fake_infohash_1'+'0R0\x10\x00\x07*\x86H\xce=\x02'
        assert not db.hasMyPreference(fake_infoahsh)
            
    def test_addMyPreference_deletePreference(self):
        db = MyPreferenceDBHandler.getInstance()
        p = db.getOne(('torrent_id', 'destination_path', 'progress', 'creation_time'), torrent_id=126)
        torrent_id = p[0]
        infohash = db._db.getInfohash(torrent_id)
        destpath = p[1]
        progress = p[2]
        creation_time = p[3]
        db.deletePreference(infohash)
        pl = db.getMyPrefListInfohash()
        assert len(pl) == 11
        assert infohash not in pl

        data = {'destination_path':destpath}
        db.addMyPreference(infohash, data)
        p2 = db.getOne(('torrent_id', 'destination_path', 'progress', 'creation_time'), torrent_id=126)
        assert p2[0] == p[0] and p2[1] == p[1] and p2[2] == 0 and time()-p2[3] < 10 , p2
        
        db.deletePreference(infohash)
        pl = db.getMyPrefListInfohash()
        assert len(pl) == 11
        assert infohash not in pl

        data = {'destination_path':destpath, 'progress':progress, 'creation_time':creation_time}
        db.addMyPreference(infohash, data)
        p3 = db.getOne(('torrent_id', 'destination_path', 'progress', 'creation_time'), torrent_id=126)
        assert p3 == p, p3
        
    def test_updateProgress(self):
        infohash_str_126 = 'ByJho7yj9mWY1ORWgCZykLbU1Xc='
        infohash = str2bin(infohash_str_126)
        db = MyPreferenceDBHandler.getInstance()
        assert db.hasMyPreference(infohash)
        torrent_id = db._db.getTorrentID(infohash)
        db.updateProgress(infohash, 3.14)
        p = db.getOne('progress', torrent_id=torrent_id)
        assert p == 3.14

    def test_getMyPrefListInfohash(self):
        db = MyPreferenceDBHandler.getInstance()
        preflist = db.getMyPrefListInfohash()
        for p in preflist:
            assert len(p) == 20
        assert len(preflist) == 12
        
    def test_getMyPrefStats(self):
        db = MyPreferenceDBHandler.getInstance()
        res = db.getMyPrefStats()
        assert len(res)==12
        for k in res:
            data = res[k]
            assert len(data) == 3
        
def test_suite():
    init()
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSqliteBasicDBHandler))
    suite.addTest(unittest.makeSuite(TestSqliteMyDBHandler))
    suite.addTest(unittest.makeSuite(TestSuperPeerDBHandler))
    suite.addTest(unittest.makeSuite(TestFriendDBHandler))
    suite.addTest(unittest.makeSuite(TestSqlitePeerDBHandler))
    suite.addTest(unittest.makeSuite(TestPreferenceDBHandler))
    suite.addTest(unittest.makeSuite(TestTorrentDBHandler))
    suite.addTest(unittest.makeSuite(TestMyPreferenceDBHandler))
    return suite

def main():
    unittest.main(defaultTest='test_suite')

if __name__ == '__main__':
    main()
    
    