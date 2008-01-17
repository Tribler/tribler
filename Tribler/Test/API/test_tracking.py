# Written by Arno Bakker
# see LICENSE.txt for license information
#

import unittest
import os
import sys
import time
from urllib2 import urlopen # urllib blocks on reading, HTTP/1.1 persist conn problem?
from traceback import print_exc

from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.btconn import BTConnection
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.API import *

DEBUG=True

class TestTracking(TestAsServer):
    """ 
    Testing seeding via new tribler API:
    """

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        
        self.config.set_overlay(False)
        self.config.set_internal_tracker(True)
        
    def test_add_remove_torrent(self):
        tdef = TorrentDef()
        sourcefn = os.path.join(os.getcwd(),"file.wmv")
        tdef.add_content(sourcefn)
        tdef.set_tracker(self.session.get_internal_tracker_url())
        tdef.finalize()

        torrentfn = os.path.join(self.session.get_state_dir(),"gen.torrent")
        tdef.save(torrentfn)
        infohash = tdef.get_infohash()
        
        self.session.add_to_internal_tracker(tdef)

        self.check_presence(infohash,True)
        
        self.session.remove_from_internal_tracker(tdef)
        print >> sys.stderr,"test: Give network thread running tracker time to detect we removed the torrent file"
        time.sleep(2)
        
        self.check_presence(infohash,False)

    def check_presence(self,infohash,present):
        hexinfohash = binascii.hexlify(infohash)
        print >> sys.stderr,"test: infohash is",hexinfohash
        
        url = 'http://127.0.0.1:'+str(self.session.get_listen_port())+'/'
        print >> sys.stderr,"test: tracker lives at",url
        f = urlopen(url)
        data = f.read()
        f.close()
        
        # WARNING: this test depends on the output of the tracker. If that
        # is changed, also change this.
        print >> sys.stderr,"test: tracker returned:",data
        if present:
            self.assert_(data.find(hexinfohash) != -1)
        else:
            self.assert_(data.find(hexinfohash) == -1)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestTracking))
    
    return suite

if __name__ == "__main__":
    unittest.main()

