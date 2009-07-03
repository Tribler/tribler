# Written by Jie Yang
# see LICENSE.txt for license information

# Arno, pychecker-ing: the addTarget and getTarget methods of JobQueue are
# no longer there, this code needs to be updated.

# 2008-06-24: add OverlayBridge equiv to DataHandler() constructor calls.

import os
import sys
import unittest
from shutil import copy as copyFile

if os.path.exists('test_buddycast.py'):
    BASE_DIR = os.path.join('..', '..')
elif os.path.exists('LICENSE.txt'):
    BASE_DIR = '..'
elif os.path.exists('clean.bat'):
    BASE_DIR = '.'

sys.path.insert(1, os.path.abspath(BASE_DIR))
    
from Tribler.__init__ import LIBRARYNAME    
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, str2bin
from Tribler.Core.CacheDB.SqliteCacheDBHandler import *
from Tribler.Core.BuddyCast.buddycast import DataHandler

DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = None
FILES_DIR = os.path.abspath(os.path.join(BASE_DIR, LIBRARYNAME,'Test','extend_db_dir'))
TRIBLER_DB_PATH = os.path.join(FILES_DIR, 'tribler.sdb')
TRIBLER_DB_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_tribler.sdb')

LIB = 0
AUTOCOMMIT = 0
BUSYTIMEOUT = 5000

def init():
    if not os.path.isfile(TRIBLER_DB_PATH_BACKUP):
        print >> sys.stderr, "Please download bak_tribler.sdb from http://www.st.ewi.tudelft.nl/~jyang/donotremove/bak_tribler.sdb and save it as", os.path.abspath(TRIBLER_DB_PATH_BACKUP)
        sys.exit(1)
    if os.path.isfile(TRIBLER_DB_PATH_BACKUP):
        copyFile(TRIBLER_DB_PATH_BACKUP, TRIBLER_DB_PATH)
        #print "refresh sqlite db", TRIBLER_DB_PATH

SQLiteCacheDB.DEBUG = False

class Session:
    def __init__(self):
        self.sessconfig = {}
    
    def get_permid(self):
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        return fake_permid_x
    

class FakeLaunchmany:
    
    def __init__(self, db):
        self.peer_db = PeerDBHandler.getInstance()
        self.superpeer_db = SuperPeerDBHandler.getInstance()
        self.torrent_db = TorrentDBHandler.getInstance()
        self.mypref_db = MyPreferenceDBHandler.getInstance()
        self.pref_db = PreferenceDBHandler.getInstance()
        self.friend_db =  FriendDBHandler.getInstance()
        self.listen_port = 6881
        self.session = Session()

    def get_ext_ip(self):
        return '127.0.0.1'

class FakeOverlayBridge:
    def add_task(self, foo, sec=0):
        foo()

class TestBuddyCastDataHandler(unittest.TestCase):
    
    def setUp(self):
        db_path = TRIBLER_DB_PATH
        db = SQLiteCacheDB.getInstance()
        db.initDB(db_path, busytimeout=BUSYTIMEOUT)
        launchmany = FakeLaunchmany(db)
        overlay_bridge = FakeOverlayBridge()
        self.datahandler = DataHandler(launchmany,overlay_bridge)
                
    def tearDown(self):
        SQLiteCacheDB.getInstance().close()
        self.datahandler.peers = None
        del self.datahandler
            
    def loadData(self, npeers = 2500):
        self.datahandler.updateMyPreferences()
        self.datahandler.loadAllPeers(npeers)
        self.datahandler.loadAllPrefs(npeers)
                    
    def test_updateMyPreferences(self):
        self.datahandler.updateMyPreferences()
        assert self.datahandler.myprefs == [126, 400, 562, 1074, 1279, 1772, 1812, 2271, 2457, 2484, 3359, 3950]
        
        self.datahandler.updateMyPreferences(10)
        assert self.datahandler.myprefs == [126, 400, 562, 1074, 1279, 1772, 1812, 2271, 2457, 3359]
            
        assert len(self.datahandler.owners[3359]) == 21
        assert len(self.datahandler.owners[2484]) == 0
        assert len(self.datahandler.owners[400]) == 8
            
    def test_updateAllPeers_Prefs(self):
        self.datahandler.loadAllPeers()
        for p in self.datahandler.peers:
            assert len(self.datahandler.peers[p][2]) == 0
        assert len(self.datahandler.peers) == 3995
        
        npeers = 2500
        self.datahandler.peers = None
        self.datahandler.loadAllPeers(npeers)
        for p in self.datahandler.peers:
            assert len(self.datahandler.peers[p][2]) == 0
        assert len(self.datahandler.peers) == npeers
        
        # Statistics: loadAllPeers takes 0.015 sec on test db
        #                                0.5 sec on Johan's db
        #                                0.03 second on loading 2500 peers from Johan's db

    def test_updateAllPrefs(self):
        self.loadData(2500)
        n = 0
        for p in self.datahandler.peers:
            assert len(self.datahandler.peers[p]) == 3
            n += len(self.datahandler.peers[p][2])
        assert n == self.datahandler.nprefs

        self.datahandler.peers = None
        self.loadData(None)
        n = 0
        for p in self.datahandler.peers:
            assert len(self.datahandler.peers[p]) == 3
            n += len(self.datahandler.peers[p][2])
        assert n == self.datahandler.nprefs
            
#        Statistics: 2500 peers preferences covers 91% of all preferences
#        self.datahandler.peers = None
#        for i in range(100, 4000, 100):
#            self.datahandler.loadAllPrefs(i)
#            print i, self.datahandler.nprefs, '%.2d%%'%(100*self.datahandler.nprefs/60634)

    """        Statistics of memory usage (KB)
                    Full Test DB     Full Johan's DB     2000 peers from Johan's DB
            Init:    11,520            12,912            12,912
        LoadPeers:   12,656            23,324            12,532
        LoadPrefs:   17,792            50,820            18,380
    """
        
    def test_updateAllSim(self):
        init()
        self.loadData(2500)
        pid = 3582
        oldsim = self.datahandler.peer_db.getOne('similarity', peer_id=pid)
        assert abs(oldsim-21.941432788)<1e-4, oldsim
        n_updates = self.datahandler.updateAllSim()    # 0.296 second for Johan's db, 0. 188 second for test db
        assert n_updates == 2166
        sim = self.datahandler.peer_db.getOne('similarity', peer_id=pid)
        assert abs(sim-17.9844112279)<1e-4, sim
        
    def test_adddelMyPref(self):
        self.datahandler.overlay_bridge = FakeOverlayBridge()
        self.loadData()
        pid = 3582
        self.datahandler.updateAllSim()
        oldsim = self.datahandler.peer_db.getOne('similarity', peer_id=pid)
        tids = sample(range(4000),10)
        for tid in tids:
            infohash = self.datahandler.torrent_db.getInfohash(tid)
            
            self.datahandler.addMyPref(infohash)
            torrents = self.datahandler.pref_db._getTorrentOwnersID(tid)
            assert self.datahandler.owners[tid] == set(torrents), (self.datahandler.owners[tid], set(torrents))
            assert tid in self.datahandler.myprefs
            sim = self.datahandler.peer_db.getOne('similarity', peer_id=pid)
            assert abs(sim-oldsim)>1e-4, (sim, oldsim)
            
            self.datahandler.delMyPref(infohash)
            assert tid not in self.datahandler.owners.keys()
            assert tid not in self.datahandler.myprefs
            sim = self.datahandler.peer_db.getOne('similarity', peer_id=pid)
            assert abs(sim-oldsim)<1e-4, (sim, oldsim)
            
            oldsim = sim
            
    def test_get_dns_from_peerdb(self):
        permid_str_id_1 = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAA6SYI4NHxwQ8P7P8QXgWAP+v8SaMVzF5+fSUHdAMrs6NvL5Epe1nCNSdlBHIjNjEiC5iiwSFZhRLsr'
        permid = str2bin(permid_str_id_1)
        self.loadData(2500)
        assert self.datahandler.get_dns_from_peerdb(permid) == ('68.108.115.221', 6881)
        
    def test_numbers(self):
        self.loadData(2500)
        npeers = self.datahandler.get_npeers()
        ntorrents = self.datahandler.get_ntorrents()
        nmyprefs = self.datahandler.get_nmyprefs()
        assert npeers == 2500
        assert ntorrents == 4483
        assert nmyprefs == 12
        
        
def test_suite():
    init()
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCastDataHandler))
    return suite

def main():
    unittest.main(defaultTest='test_suite')

if __name__ == '__main__':
    main()
    
    