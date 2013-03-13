import os
import sys
import unittest

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, str2bin, CURRENT_MAIN_DB_VERSION
from Tribler.Core.CacheDB.SqliteCacheDBHandler import PreferenceDBHandler, MyPreferenceDBHandler
from Tribler.Core.BuddyCast.TorrentCollecting import SimpleTorrentCollecting
from bak_tribler_sdb import *
    
CREATE_SQL_FILE = os.path.join('..',"schema_sdb_v"+str(CURRENT_MAIN_DB_VERSION)+".sql")
assert os.path.isfile(CREATE_SQL_FILE)

def init():
    init_bak_tribler_sdb()


SQLiteCacheDB.DEBUG = False

class TestTorrentCollecting(unittest.TestCase):
        
    def setUp(self):
        self.db = SQLiteCacheDB.getInstance()
        self.db.initDB(TRIBLER_DB_PATH_BACKUP)
        
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
        tc = SimpleTorrentCollecting(None,None)
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
    init()
    unittest.main(defaultTest='test_suite')

    
if __name__ == '__main__':
    main()    
            
                    
