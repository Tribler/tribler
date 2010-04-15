# Written by Arno Bakker
# see LICENSE.txt for license information
#

import unittest
import os
import sys
import time
from urllib2 import urlopen # urllib blocks on reading, HTTP/1.1 persist conn problem?
from traceback import print_exc

from Tribler.Core.simpledefs import STATEDIR_ITRACKER_DIR
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
        
        self.config.set_megacache(False)
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
        hexinfohash = binascii.hexlify(infohash)
        
        self.session.add_to_internal_tracker(tdef)

        self.check_http_presence(hexinfohash,True)
        
        self.session.remove_from_internal_tracker(tdef)
        print >> sys.stderr,"test: Give network thread running tracker time to detect we removed the torrent file"
        time.sleep(2)
        
        self.check_http_presence(hexinfohash,False)
        self.check_disk_presence(hexinfohash,False)

    def check_http_presence(self,hexinfohash,present):
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

    def check_disk_presence(self,hexinfohash,present):
        itrackerdir = os.path.join(self.session.get_state_dir(),STATEDIR_ITRACKER_DIR)
        for filename in os.listdir(itrackerdir):
            if filename.startswith(hexinfohash):
                if present:
                    self.assert_(True)
                else:
                    self.assert_(False)
            

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestTracking))
    
    return suite

if __name__ == "__main__":
    unittest.main()

