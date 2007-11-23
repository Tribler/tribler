import os
import tempfile
import unittest
from sets import Set
import base64

from Tribler.Core.CacheDB.CacheDBHandler import SuperPeerDBHandler
from Tribler.Core.CacheDB.cachedb import PeerDB

lines = [
'superpeer1.das2.ewi.tudelft.nl, 7001, MG0CAQEEHR/bQNvwga7Ury5+8vg/DTGgmMpGCz35Zs/2iz7coAcGBSuBBAAaoUADPgAEAL2I5yVc1+dWVEx3nbriRKJmOSlQePZ9LU7yYQoGABMvU1uGHvqnT9t+53eaCGziV12MZ1g2p0GLmZP9, superpeer1@TUD\n',
'superpeer1.das2.ewi.tudelft.nl, 7004, MG0CAQEEHVPNzNfHzGgIIrpUyNC1NYQpaoeNov0jovmEuwtCoAcGBSuBBAAaoUADPgIEAZNX5NBOuGH4j2kumv/9WkPLrJPVkOr5oVImhcp8AC7w7ww9eZwUF7S/Q96If4UmVX+L6HMKSOTLPoPk, superpeer2@TUD\n',
'superpeer1.das2.ewi.tudelft.nl, 7003, MG0CAQEEHWDBJrkzilKmoOBWZHu19gaabapqJIAeSLhffluLoAcGBSuBBAAaoUADPgAEAQaLGR940aKktbAJNm6vYOTSN2P8z1P9EiQ48kJNAdrDl7oBkyrERZOq+IMMKIpu4ocsz5hxZHMTy2Fh, superpeer3@TUD\n',
'superpeer1.das2.ewi.tudelft.nl, 7002, MG0CAQEEHVPNzNfHzGgIIrpUyNC1NYQpaoeNov0jovmEuwtCoAcGBSuBBAAaoUADPgIEAZNX5NBOuGH4j2kumv/9WkPLrJPVkOr5oVImhcp8AC7w7ww9eZwUF7S/Q96If4UmVX+L6HMKSOTLPoPk, superpeer2@TUD\n',
]

class TestSuperPeerList(unittest.TestCase):
    
    def setUp(self):
        tuple = tempfile.mkstemp()
        os.close(tuple[0])
        self.tmpfilepath = tuple[1]
        self.tmpdirpath = os.path.join(tempfile.mkdtemp(), 'testdb')
        self.writeSuperPeers()
        print "test: Temp database path",self.tmpdirpath
        (head,tail) = os.path.split(self.tmpfilepath)
        config = {}
        config['install_dir'] = head
        config['superpeer_file'] = tail
        self.splist = SuperPeerDBHandler(config, db_dir=self.tmpdirpath)
        
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
        res = self.splist.readSuperPeerList(self.tmpfilepath)
        self.assert_(len(res) == 4)

    def test_updatePeerDB(self):
        """ The SuperPeerDBHandler constructor writes the superpeers to the PeerDB """
        self.peer_db = PeerDB.getInstance()
        # Arno: must be 3, as there is a duplicate PermID in the lines list
        self.assert_(self.peer_db._size() == 3)
        
    def test_getSuperPeers(self):
        superpeers = self.splist.getSuperPeers()
        self.assert_(len(superpeers) == 4)

    def xxtest_normal(self):
        splist = SuperPeerList()
        splist.updateSuperPeerList()
        superpeers = splist.getSuperPeers()
        print superpeers

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSuperPeerList))
    
    return suite
    