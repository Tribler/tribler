# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import os
from traceback import print_exc

from triblerAPI import TorrentDef
from BitTornado.bencode import bencode
from Tribler.utilities import isValidTorrentFile

DEBUG = False

TRACKER = 'http://www.tribler.org/announce'

class TestTorrentDef(unittest.TestCase):
    """ 
    Testing TorrentDef version 0
    """
    
    def setUp(self):
        pass
        
    def tearDown(self):
        pass

    def xtest_add_content_file(self):
        t = TorrentDef()
        t.set_create_merkle_torrent(False)
        fn = os.path.join(os.getcwd(),"file.wmv")
        t.add_content(fn)
        t.set_tracker(TRACKER)
        t.finalize()
        
        s = os.path.getsize("file.wmv")
        
        metainfo = t.get_metainfo()
        self.assert_(isValidTorrentFile(metainfo))
        self.assert_(metainfo['announce'] == TRACKER)
        self.assert_(metainfo['info']['name'] == "file.wmv")
        self.assert_(metainfo['info']['length'] == s)
        
        """
        bdata = bencode(t.get_metainfo())
        f = open("gen.torrent","wb")
        f.write(bdata)
        f.close()
        """

    def test_add_content_dir(self):
        t = TorrentDef()
        t.set_create_merkle_torrent(False)
        dn = os.path.join(os.getcwd(),"contentdir")
        t.add_content(dn,"dirintorrent")
        t.set_tracker(TRACKER)
        t.finalize()

        exps = 0L
        for f in os.listdir("contentdir"):
            p = os.path.join("contentdir",f)
            exps += os.path.getsize(p) 

        metainfo = t.get_metainfo()
        self.assert_(isValidTorrentFile(metainfo))
        self.assert_(metainfo['announce'] == TRACKER)
        
        self.assert_(metainfo['info']['name'] == 'dirintorrent')
        reals = 0L
        for file in metainfo['info']['files']:
            reals += file['length']
        self.assert_(exps == reals)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestTorrentDef))
    
    return suite

if __name__ == "__main__":
    unittest.main()
