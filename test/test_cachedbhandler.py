import os
import tempfile
import unittest
from sets import Set

from Tribler.CacheDB.CacheDBHandler import PeerDBHandler

test_peers = [('permid1', {'ip':'1.2.3.4', 'port':1234, 'name':'peer1'}),
              ('permid2', {'ip':'2.2.3.4', 'port':2234, 'name':'peer2'}),
              ('permid3', {'ip':'3.2.3.4', 'port':3234, 'name':'peer3'}),
              ('permid2', {'ip':'22.2.3.4', 'port':22342, 'name':'peer22'}),
              ('permid4', {'ip':'3.2.3.4', 'port':1234, 'name':'peer22'}), 
             ]  

class TestPeerDBHandler(unittest.TestCase):
    
    def setUp(self):
        self.tmpdirpath = os.path.join(tempfile.gettempdir(), 'testdb')
        self.peer_db = PeerDBHandler(db_dir=self.tmpdirpath)
        self.peer_db.clear()
        
    def tearDown(self):
        self.peer_db.clear()

    def test_all(self):
        for permid, value in test_peers:
            self.peer_db.addPeer(permid, value)
        #print self.peer_db.peer_db._data
        assert self.peer_db.hasPeer('permid2')
        assert len(self.peer_db) == 4
        res = self.peer_db.findPeers('permid', 'permid2')
        assert len(res) == 1, len(res)
        assert res[0] == {'permid':'permid2', 'ip':'22.2.3.4', 'port':22342, 'name':'peer22', 'similarity':0, 'last_seen':0}, res
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

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPeerDBHandler))
    
    return suite
    