import os
import sys
import unittest

if os.path.exists('test_sqlitecachedb.py'):
    BASE_DIR = '..'
elif os.path.exists('LICENSE.txt'):
    BASE_DIR = '.'
sys.path.insert(1, os.path.abspath(os.path.join('..',BASE_DIR)))
    
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, str2bin
from Tribler.Core.CacheDB.SqliteCacheDBHandler import PreferenceDBHandler, MyPreferenceDBHandler
from Tribler.Core.BuddyCast.TorrentCollecting import SimpleTorrentCollecting
    
CREATE_SQL_FILE = os.path.join(BASE_DIR, 'schema_sdb_v1.sql')
assert os.path.isfile(CREATE_SQL_FILE)
DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = None
FILES_DIR = os.path.join(BASE_DIR, 'Test/extend_db_dir/')
TRIBLER_DB_PATH = os.path.join(FILES_DIR, 'tribler.sdb')
TRIBLER_DB_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_tribler.sdb')
if not os.path.isfile(TRIBLER_DB_PATH_BACKUP):
    print >> sys.stderr, "Please download bak_tribler.sdb from http://www.st.ewi.tudelft.nl/~jyang/donotremove/bak_tribler.sdb and save it as", os.path.abspath(TRIBLER_DB_PATH_BACKUP)
    sys.exit(1)
if os.path.isfile(TRIBLER_DB_PATH_BACKUP):
    from shutil import copy as copyFile
    copyFile(TRIBLER_DB_PATH_BACKUP, TRIBLER_DB_PATH)
    #print "refresh sqlite db", TRIBLER_DB_PATH


SQLiteCacheDB.DEBUG = False

class TestTorrentCollecting(unittest.TestCase):
        
    def setUp(self):
        self.db = SQLiteCacheDB.getInstance()
        self.db.initDB(TRIBLER_DB_PATH_BACKUP, lib=0)
        permid = {}
        permid[3127] = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAcPezgQ13k1MSOaUrCPisWRhYuNT7Tm+q5rUgHFvAWd9b+BcSut6TCniEgHYHDnQ6TH/vxQBqtY8Loag'
        permid[994] = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAJUNmwvDaigRaM4cj7cE2O7lessqnnFEQsan7df9AZS8xeNmVsP/XXVrEt4t7e2TNicYmjn34st/sx2P'
        permid[19] = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAJv2YLuIWa4QEdOEs4CPRxQZDwZphKd/xK/tgbcALG198nNdT10znJ2sZYl+OJIvj7YfYp75PrrnWNX'
        permid[5] = 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAAB0XbUrw5b8CrTrMZST1SPyrzjgSzIE6ynALtlZASGAb+figVXRRGpKW6MSal3KnEm1/q0P3JPWrhCE'
        self.permid = permid
        
        db = MyPreferenceDBHandler.getInstance()
        db.loadData()
        
    def tearDown(self):
        self.db.close()
    
    def test_selecteTorrentToCollect(self):
        db = PreferenceDBHandler.getInstance()
        tc = SimpleTorrentCollecting(None)
        truth = {3127:235, 994:20, 19:1, 5:0}
        
        for pid in truth:
            pl = db.getPrefList(str2bin(self.permid[pid]))
            assert len(pl) == truth[pid], [pid, len(pl)]
            # test random selection
            infohash = tc.selecteTorrentToCollect(pl, True)    
            if pid == 994 or pid == 3127:
                assert len(infohash) == 20, infohash
            else:
                assert infohash is None, infohash
        
        #tc.updateAllCooccurrence()
        for pid in truth:
            pl = db.getPrefList(str2bin(self.permid[pid]))
            assert len(pl) == truth[pid], [pid, len(pl)]
            # test selecting most relevant torrent
            infohash = tc.selecteTorrentToCollect(pl, False)    
            if pid == 994:
                tid = tc.torrent_db.getTorrentID(infohash)
                assert tid == 8979
                
                permid = self.permid[pid]
                infohash = tc.updatePreferences(permid, pl)
                tid = tc.torrent_db.getTorrentID(infohash)
                assert tid == 8979
            elif pid == 3127:
                tid = tc.torrent_db.getTorrentID(infohash)
                assert tid == 9170
                
                permid = self.permid[pid]
                infohash = tc.updatePreferences(permid, pl)
                tid = tc.torrent_db.getTorrentID(infohash)
                assert tid == 9170
            else:
                assert infohash is None, infohash
                

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestTorrentCollecting))
    
    return suite
        
def main():
    unittest.main(defaultTest='test_suite')

    
if __name__ == '__main__':
    main()    
            
                    