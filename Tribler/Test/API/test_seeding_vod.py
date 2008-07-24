# Written by Arno Bakker
# see LICENSE.txt for license information
#

import unittest
import os
import sys
import time
import socket
import tempfile
from traceback import print_exc

from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.btconn import BTConnection
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.TorrentDef import *
from Tribler.Core.DownloadConfig import *
from Tribler.Core.Session import *
from Tribler.Core.simpledefs import *

DEBUG=True

class TestSeeding(TestAsServer):
    """ 
    Testing seeding via new tribler API:
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >>sys.stderr,"test: Giving Session time to startup"
        time.sleep(5)
        print >>sys.stderr,"test: Session should have started up"
        self.vod_started = False
    
    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        
        self.config.set_overlay(False)
        self.config.set_internal_tracker(True)
        
        self.mylistenport = 4810

    def setUpPostSession(self):
        pass
    
    def tearDown(self):
        TestAsServer.tearDown(self)
        self.assert_(self.vod_started)
    
    def setup_seeder(self,merkle):
        self.tdef = TorrentDef()
        self.sourcefn = os.path.join(os.getcwd(),"file2.wmv")
        self.tdef.add_content(self.sourcefn,playtime='1:00') # 60 secs
        self.tdef.set_create_merkle_torrent(merkle)
        self.tdef.set_tracker(self.session.get_internal_tracker_url())
        self.tdef.finalize()

        self.torrentfn = os.path.join(self.session.get_state_dir(),"gen.torrent")
        self.tdef.save(self.torrentfn)
        
        print >>sys.stderr,"test: setup_seeder: name is",self.tdef.metainfo['info']['name']

        self.dscfg = DownloadStartupConfig()
        self.dscfg.set_dest_dir(os.getcwd())
        d = self.session.start_download(self.tdef,self.dscfg)
        
        d.set_state_callback(self.seeder_state_callback)
        
    def seeder_state_callback(self,ds):
        d = ds.get_download()
        print >>sys.stderr,"test: seeder:",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress()
        return (1.0,False)


    def test_normal_torrent(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        self.setup_seeder(False)
        #self.subtest_is_seeding()
        self.subtest_download()

    def test_merkle_torrent(self):
        self.setup_seeder(True)
        self.subtest_is_seeding()
        self.subtest_download()

    def subtest_is_seeding(self):
        infohash = self.tdef.get_infohash()
        s = BTConnection('localhost',self.hisport,user_infohash=infohash)
        s.read_handshake_medium_rare()
        
        s.send(CHOKE)
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            self.assert_(resp[0] == EXTEND)
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, peer didn't reply"
            self.assert_(False)
        s.close()
        
        
    def subtest_download(self):
        """ Now download the file via another Session """
        
        self.config2 = self.config.copy() # not really necess
        self.config_path2 = tempfile.mkdtemp()
        self.config2.set_state_dir(self.config_path2)
        self.config2.set_listen_port(self.mylistenport)
        self.session2 = Session(self.config2,ignore_singleton=True)
        
        # Allow session2 to start
        print >>sys.stderr,"test: Sleeping 3 secs to let Session2 start"
        time.sleep(3)
        
        tdef2 = TorrentDef.load(self.torrentfn)

        dscfg2 = DownloadStartupConfig()
        dscfg2.set_dest_dir(self.config_path2)
        dscfg2.set_video_event_callback(self.downloader_vod_ready_callback)
        
        d = self.session2.start_download(tdef2,dscfg2)
        d.set_state_callback(self.downloader_state_callback)
        time.sleep(20)
    
    def downloader_state_callback(self,ds):
        d = ds.get_download()
        print >>sys.stderr,"test: download:",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress()
        
        return (1.0,False)

    def downloader_vod_ready_callback(self,d,event,params):
        if event == VODEVENT_START:
            self.vod_started = True

        
def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_seeding.py <method name>"
    else:
        suite.addTest(TestSeeding(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
