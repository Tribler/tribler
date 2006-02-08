import os
import unittest
import tempfile
from sets import Set

from BitTornado.bencode import bencode, bdecode
from Tribler.BuddyCast.buddycast2 import BuddyCastFactory
from Tribler.CacheDB.cachedb import *
from Tribler.utilities import print_prefxchg_msg

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
        self.buddycast = BuddyCastFactory.getInstance(db_dir=self.tmpdirpath)
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
        self.buddycast.name = self.mydata['name']
        for p in self.prefs:
            self.buddycast.addMyPref(p)
                
        self.my_db = MyDB.getInstance(db_dir=db_dir)
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)    
        
#        for pref in self.prefs:
#            self.mypref_db.updateItem(pref)
        
    def tearDown(self):
        self.buddycast.data_handler.clear()
        self.buddycast.data_handler.sync()
        
    def test_updateDB(self):
        msg = self.prefxchg_msgs[0].strip()
        self.buddycast.gotBuddycastMsg(msg)
        assert self.peer_db._size() == 21, self.peer_db._data.keys()
        assert self.torrent_db._size() == 132, self.torrent_db._size()
        assert self.pref_db._size() == 11, self.pref_db._size()
        assert self.owner_db._size() == 132, self.owner_db._size()
        assert self.mypref_db._size() == 50, self.mypref_db._size()

    def preload(self):
        for i in xrange(144,149):    #self.np
            if i == self.myid:
                continue
            msg = self.prefxchg_msgs[i].strip()
            self.buddycast.gotBuddycastMsg(msg)
        
    def xxtest_gotPrefxchg(self):
        self.preload()
        assert self.peer_db._size() == 80
        assert self.torrent_db._size() == 317
        assert self.pref_db._size() == 40
        assert self.torrent_db._size() == self.owner_db._size()
        
    def xxtest_getMyPrefxchg(self):
        self.preload()
        my_prefxchg = self.buddycast.getMyPrefxchg()
        assert self.buddycast.validPrefxchg(my_prefxchg)
        print_prefxchg_msg(my_prefxchg)
        
    def xxtest_addMyPref(self):
        self.preload()
        items = self.owner_db._items()
#        for item in items:
#            if len(item[1]) > 7 and not self.mypref_db._has_key(item[0]):
#                print item[0], len(item[1]), item[1]
        new_item = '1651'
        assert self.peer_db.getItem('peer_145')['similarity'] == 100
        assert self.peer_db.getItem('peer_83')['similarity'] == 0
#        owners = self.owner_db.getItem(new_item)
#        for o in owners:
#            print o, self.peer_db.getItem(o)
        self.buddycast.addMyPref(new_item)
        assert self.peer_db.getItem('peer_145')['similarity'] == 118
        assert self.peer_db.getItem('peer_83')['similarity'] == 44
#        print
#        for o in owners:
#            print o, self.peer_db.getItem(o)
    
    
def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCast))
    
    return suite

    