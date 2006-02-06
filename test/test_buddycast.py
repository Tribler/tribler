import os
import unittest
import tempfile
from sets import Set

from BitTornado.bencode import bencode, bdecode
from Tribler.BuddyCast.buddycast2 import BuddyCast
from Tribler.CacheDB.cachedb import *

testdata_file = 'test/testdata.txt'
myid = 147

class TestBuddyCast(unittest.TestCase):
    """ 
    Testing buddycast includes two steps:
        1. Test buddycast algorithm
        2. Test buddycast communication functionalities
    Here we can only test step 1.
    """
    
    def setUp(self):
        self.tmpdirpath = db_dir = os.path.join(tempfile.gettempdir(), 'testdb')
        self.buddycast = BuddyCast.getInstance(db_dir=self.tmpdirpath)
        testdata = open(testdata_file, 'r')
        self.prefxchg_msgs = testdata.readlines()
        testdata.close()
        self.np = len(self.prefxchg_msgs)
        self.myid = myid
        msg = self.prefxchg_msgs[self.myid-1].strip()
        self.mydata = bdecode(msg)
        self.prefs = self.mydata['preferences']
        self.buddycast.ip = self.mydata['ip']
        self.buddycast.port = self.mydata['port']
        self.buddycast.permid = self.mydata['permid']
                
        self.my_db = MyDB.getInstance(db_dir=db_dir)
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)    
        
#        for pref in self.prefs:
#            self.mypref_db.updateItem(pref)
        
    def tearDown(self):
        self.buddycast.clear()
        self.buddycast.sync()
        
    def test_updateDB(self):
        msg = self.prefxchg_msgs[0].strip()
        self.buddycast.gotPrefxchg(msg)
        assert self.peer_db._size() == 21, self.peer_db._data.keys()
        assert self.torrent_db._size() == 132, self.torrent_db._size()
        assert self.pref_db._size() == 11, self.pref_db._size()
        assert self.owner_db._size() == 132, self.owner_db._size()

    def test_gotPrefxchg(self):
        for i in xrange(1,1000):    #self.np
            if i == self.myid:
                continue
            msg = self.prefxchg_msgs[i].strip()
            self.buddycast.gotPrefxchg(msg)
            print self.peer_db._size(), self.torrent_db._size(), self.pref_db._size()
        
    def test_getMyPrefxchg(self):
        my_prefxchg = self.buddycast.getMyPrefxchg()
        #print my_prefxchg
        
        
    
def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCast))
    
    return suite

    