import os, sys
import tempfile
import unittest
from sets import Set
import base64

if os.path.exists('test_sqlitecachedb.py'):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE.txt'):
    BASE_DIR = '.'

from Core.CacheDB.cachedb import SQLiteCacheDB
from Core.CacheDB.CacheDBHandler import SuperPeerDBHandler, PeerDBHandler

CREATE_SQL_FILE = os.path.join(BASE_DIR, 'tribler_sdb_v1.sql')
assert os.path.isfile(CREATE_SQL_FILE)
    

lines = [
'superpeer1.das2.ewi.tudelft.nl, 7001, MG0CAQEEHR/bQNvwga7Ury5+8vg/DTGgmMpGCz35Zs/2iz7coAcGBSuBBAAaoUADPgAEAL2I5yVc1+dWVEx3nbriRKJmOSlQePZ9LU7yYQoGABMvU1uGHvqnT9t+53eaCGziV12MZ1g2p0GLmZP9, superpeer1@TUD\n',
'superpeer1.das2.ewi.tudelft.nl, 7004, MG0CAQEEHVPNzNfHzGgIIrpUyNC1NYQpaoeNov0jovmEuwtCoAcGBSuBBAAaoUADPgIEAZNX5NBOuGH4j2kumv/9WkPLrJPVkOr5oVImhcp8AC7w7ww9eZwUF7S/Q96If4UmVX+L6HMKSOTLPoPk, superpeer2@TUD\n',
'superpeer1.das2.ewi.tudelft.nl, 7003, MG0CAQEEHWDBJrkzilKmoOBWZHu19gaabapqJIAeSLhffluLoAcGBSuBBAAaoUADPgAEAQaLGR940aKktbAJNm6vYOTSN2P8z1P9EiQ48kJNAdrDl7oBkyrERZOq+IMMKIpu4ocsz5hxZHMTy2Fh, superpeer3@TUD\n',
]

class TestSuperPeerList(unittest.TestCase):
    
    def setUp(self):
        self.file_path = tempfile.mktemp()
        self.db_path = tempfile.mktemp()
        
        self.writeSuperPeers()
        head,tail = os.path.split(self.file_path)
        self.config = {'install_dir':head, 'superpeer_file':tail}
        
        self.db = SQLiteCacheDB.getInstance()
        self.db.initDB(self.db_path, CREATE_SQL_FILE, check_version=False)
        self.splist = SuperPeerDBHandler.getInstance()
        
#        cur = SQLiteCacheDB.getCursor()
#        print cur, cur.connection
        
    def tearDown(self):
        self.db.close(clean=True)
        for path in [self.file_path, self.db_path]:
            try:
                os.remove(path)
            except Exception, msg:
                pass

    def writeSuperPeers(self):
        tf = open(self.file_path, "w")
        tf.writelines(lines)
        tf.close()
            
    def test_readSuperPeerList(self):
        res = self.splist.readSuperPeerList(self.file_path)
        assert len(res) == 3, len(res)

    def test_loadSuperPeer(self):
        """ The SuperPeerDBHandler constructor writes the superpeers to the PeerDB """
        
        self.splist.loadSuperPeers(self.config, True)
        assert self.splist.size() == 3, self.splist.size()
        
        self.peer_db = PeerDBHandler.getInstance()
        # Arno: must be 3, as there is a duplicate PermID in the lines list
        assert self.peer_db.size() == 3, self.peer_db.size()
        
    def test_getSuperPeers(self):
        self.splist.loadSuperPeers(self.config, True)
        superpeers = self.splist.getSuperPeers()
        assert len(superpeers) == 3, superpeers


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSuperPeerList))
    
    return suite

        
def main():
    unittest.main(defaultTest='test_suite')

    
if __name__ == '__main__':
    main()        