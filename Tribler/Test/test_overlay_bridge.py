# Written by Arno Bakker
# see LICENSE.txt for license information
#

import sys
import unittest
import time
import tempfile
import os

import Tribler.Core.CacheDB.sqlitecachedb as sqlitecachedb
from Tribler.Test.test_secure_overlay import TestSecureOverlay,Peer
from Tribler.Core.Overlay.SecureOverlay import SecureOverlay
from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.Utilities.utilities import show_permid_short

class TestOverlayThreadingBridge(TestSecureOverlay):

    def setUp(self):

        print >>sys.stderr,"test: TestOverlayThreadingBridge.setUp()"

        self.config_path = tempfile.mkdtemp()
        config = {}
        config['state_dir'] = self.config_path
        config['torrent_collecting_dir'] = self.config_path
        config['install_dir'] = os.path.join('..','..')
        config['peer_icon_path'] = os.path.join(self.config_path,'peer_icons')
        config['superpeer'] = False
        sqlitecachedb.init(config, self.rawserver_fatalerrorfunc)

        secover1 = SecureOverlay.getInstance()
        secover1.resetSingleton()
        secover2 = SecureOverlay.getInstance()
        secover2.resetSingleton()

        overbridge1 = OverlayThreadingBridge()
        overbridge1.register_bridge(secover1,None)
        overbridge1.resetSingleton()

        overbridge2 = OverlayThreadingBridge()
        overbridge2.register_bridge(secover2,None)
        overbridge2.resetSingleton()


        self.peer1 = Peer(self,1234,overbridge1)
        self.peer2 = Peer(self,5678,overbridge2)
        self.peer1.start()
        self.peer2.start()
        self.wanted = False
        self.wanted2 = False
        self.got = False
        self.got2 = False
        self.first = True

        print >>sys.stderr,"test: setUp: peer1 permid is",show_permid_short(self.peer1.my_permid)
        print >>sys.stderr,"test: setUp: peer2 permid is",show_permid_short(self.peer2.my_permid)

        time.sleep(2) # let server threads start


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_overlay_bridge.py <method name>"
    else:
        suite.addTest(TestOverlayThreadingBridge(sys.argv[1]))

    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
