import os
import tempfile
import unittest
from random import randint
from sets import Set

from Tribler.CacheDB.CacheDBHandler import *

test_peers = [('permid1', {'ip':'1.2.3.4', 'port':1234, 'name':'peer1'}),
              ('permid2', {'ip':'2.2.3.4', 'port':2234, 'name':'peer2'}),
              ('permid3', {'ip':'3.2.3.4', 'port':3234, 'name':'peer3'}),
              ('permid2', {'ip':'22.2.3.4', 'port':22342, 'name':'peer22'}),
              ('permid4', {'ip':'3.2.3.4', 'port':1234, 'name':'peer22'}), 
             ]  
             
test_prefs = [('torrent1', {'name':'File 1'}),
              ('torrent2', {'name':'File 22'}), 
              ('torrent3', {'name':'File 3'}), 
              ('torrent2', {'name':'File 2'}), 
               ]
               
test_prefs2 = [('torrent1', {'name':'File 1'}),
              ('torrent2', {'name':'File 22'}), 
              ('torrent3', {'name':'File 3'}), 
              ('torrent2', {'name':'File 2'}), 
               ]


class TestPeerDBHandler(unittest.TestCase):
    
    def setUp(self):
        self.tmpdirpath = os.path.join(tempfile.mkdtemp(), 'testdb')
        self.peer_db = PeerDBHandler(db_dir=self.tmpdirpath)
        self.peer_db.clear()
        
    def tearDown(self):
        self.peer_db.clear()

    def test_all(self):
        for permid, value in test_peers:
            self.peer_db.addPeer(permid, value)
        peers = self.peer_db.getPeers(['permid2', 'permid4'], ['ip', 'name'])
        assert len(peers) == 2
        assert len(peers[1].keys()) == 2
        #print self.peer_db.peer_db._data
        assert self.peer_db.hasPeer('permid2')
        assert len(self.peer_db) == 4
        res = self.peer_db.findPeers('permid', 'permid2')
        assert len(res) == 1, len(res)
        # Arno: 'last_seen' is set automatically these days :-(
        res[0]['last_seen'] = 0
        expected = {'permid':'permid2', 'ip':'22.2.3.4', 'port':22342, 'name':'peer22', 'similarity':0, 'last_seen':0,'buddycast_times':0,'tried_times':0,'connected_times':0}
        assert res[0] == expected, res
        res = self.peer_db.findPeers('ip', '3.2.3.4')
        assert len(res) == 2, len(res)
        res = self.peer_db.findPeers('port', 1234)
        assert len(res) == 2, len(res)
        res = self.peer_db.findPeers('name', 'peer22')
        assert len(res) == 2, len(res)
        res = self.peer_db.findPeers('port', '1234')
        assert len(res) == 0, len(res)
        res = self.peer_db.findPeers('nokey', 'abcd')
        assert len(res) == 0, len(res)
        self.peer_db.updatePeerIPPort('permid1', '4.3.2.1', 4321)
        x = self.peer_db.getPeer('permid1')
        assert x['ip'] == '4.3.2.1', x
        assert x['port'] == 4321


class TestMyPreferenceDBHandler(unittest.TestCase):
    
    def setUp(self):
        self.tmpdirpath = os.path.join(tempfile.gettempdir(), 'testdb')
        self.mypref_db = MyPreferenceDBHandler(db_dir=self.tmpdirpath)
        self.mypref_db.clear()
        
    def tearDown(self):
        self.mypref_db.clear()
        self.mypref_db.sync()

    def test_all(self):
        for infohash, data in test_prefs:
            self.mypref_db.addPreference(infohash, data)
        assert self.mypref_db.size() == 3, self.mypref_db.size()        
        if 0:
            print self.mypref_db.getPreferences()
            print self.mypref_db.getPreferences('name')
            print self.mypref_db.getRecentPrefs(2)
            print self.mypref_db.getRecentPrefList(2)

    def test_removeFakeTorrents(self):
        torrents = []
        for i in range(10):
            torrent = (str(i), )

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPeerDBHandler))
    suite.addTest(unittest.makeSuite(TestMyPreferenceDBHandler))
    
    return suite
    