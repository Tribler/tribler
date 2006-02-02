import os
import tempfile
import unittest
from sets import Set

from Tribler.CacheDB.superpeers import SuperPeerList
from Tribler.CacheDB.cachedb import MyDB, PeerDB

lines = [
'superpeer1.das2.ewi.tudelft.nl, 7001, MG0CAQEEHR/bQNvwga7Ury5+8vg/DTGgmMpGCz35Zs/2iz7coAcGBSuBBAAaoUADPgAEAL2I5yVc1+dWVEx3nbriRKJmOSlQePZ9LU7yYQoGABMvU1uGHvqnT9t+53eaCGziV12MZ1g2p0GLmZP9, superpeer1@TUD\n',
'superpeer0.das2.ewi.tudelft.nl, 7004, MG0CAQEEHVPNzNfHzGgIIrpUyNC1NYQpaoeNov0jovmEuwtCoAcGBSuBBAAaoUADPgIEAZNX5NBOuGH4j2kumv/9WkPLrJPVkOr5oVImhcp8AC7w7ww9eZwUF7S/Q96If4UmVX+L6HMKSOTLPoPk, superpeer2@TUD\n',
'superpeer3.das2.ewi.tudelft.nl, 7003, MG0CAQEEHWDBJrkzilKmoOBWZHu19gaabapqJIAeSLhffluLoAcGBSuBBAAaoUADPgAEAQaLGR940aKktbAJNm6vYOTSN2P8z1P9EiQ48kJNAdrDl7oBkyrERZOq+IMMKIpu4ocsz5hxZHMTy2Fh, superpeer3@TUD\n',
'superpeer2.das2.ewi.tudelft.nl, 7002, MG0CAQEEHVPNzNfHzGgIIrpUyNC1NYQpaoeNov0jovmEuwtCoAcGBSuBBAAaoUADPgIEAZNX5NBOuGH4j2kumv/9WkPLrJPVkOr5oVImhcp8AC7w7ww9eZwUF7S/Q96If4UmVX+L6HMKSOTLPoPk, superpeer2@TUD\n',
]

class TestSuperPeerList(unittest.TestCase):
    
    def setUp(self):
        self.tmpfilepath = tempfile.mktemp()
        self.tmpdirpath = os.path.join(tempfile.gettempdir(), 'testdb')
        self.splist = SuperPeerList(friend_file=self.tmpfilepath, db_dir=self.tmpdirpath)
        
    def tearDown(self):
        self.splist.clear()
        try:
            os.remove(self.tmpfilepath)
        except Exception, msg:
            pass

    def writeSuperPeers(self):
        tf = open(self.tmpfilepath, "w")
        tf.writelines(lines)
        tf.close()
            
    def test_readSuperPeerList(self):
        self.writeSuperPeers()
        res = self.splist.readSuperPeerList(self.tmpfilepath)
        assert len(res) == 3, res

        
    def test_updateDB(self):
        self.writeSuperPeers()
        res = self.splist.readSuperPeerList()
        self.splist.updateDB(res)
        self.db_is_ok()
        
    def test_updateSuperPeerList(self):
        self.writeSuperPeers()
        self.splist.updateSuperPeerList()
        self.db_is_ok()
        assert not os.access(self.tmpfilepath, os.F_OK), "tmp file not removed"
        
    def db_is_ok(self):
        self.my_db = MyDB.getInstance()
        self.peer_db = PeerDB.getInstance()
        assert Set(self.my_db._get('superpeers')) == Set([
        'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAc6ebdH+dmvvgKiE7oOZuQba5I4msyuTJmVpJQVPAT+R9Pg8zsLsuJPV6RjU30RKHnCiaJvjtFW6pLXo',
        'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAWAiRwei5Kw9b2he6qmwh5Hr5fNR3FlgHQ1WhXY0AC4w8RQD59rp4Jbo2NdjyXUGb5y1BCeMCGoRCaFy'
        ]), self.my_db._get('superpeers')
        assert self.peer_db._size() == 2
        
    def test_getSuperPeers(self):
        self.writeSuperPeers()
        self.splist.updateSuperPeerList()
        superpeers = self.splist.getSuperPeers()
        answer = [
                   {'permid':'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAWAiRwei5Kw9b2he6qmwh5Hr5fNR3FlgHQ1WhXY0AC4w8RQD59rp4Jbo2NdjyXUGb5y1BCeMCGoRCaFy',
                   'name':'Arno Bakker',
                   'ip':'130.37.193.64', 
                   'port':6881,
                   'similarity':0,
                   'last_seen':0,
                   },
                   {'permid':'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAc6ebdH+dmvvgKiE7oOZuQba5I4msyuTJmVpJQVPAT+R9Pg8zsLsuJPV6RjU30RKHnCiaJvjtFW6pLXo',
                   'name':'Jie Yang',
                   'ip':'130.161.158.51',
                   'port':3966,
                   'similarity':0,
                   'last_seen':0,
                   },
                   ]
        assert len(superpeers) == 2, len(superpeers)
        assert superpeers == answer or (superpeers[0] == answer[1] and superpeers[1] == answer[0]), superpeers

    def xxtest_normal(self):
        splist = SuperPeerList()
        splist.updateSuperPeerList()
        superpeers = splist.getSuperPeers()
        print superpeers

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSuperPeerList))
    
    return suite
    