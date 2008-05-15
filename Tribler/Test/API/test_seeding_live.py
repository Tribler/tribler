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
from Tribler.Core.BitTornado.bitfield import Bitfield

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
    
    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        
        self.config.set_overlay(False)
        self.config.set_internal_tracker(True)
        
        self.mylistenport = 4810

    def setUpPostSession(self):
        pass


    def test_live_torrent(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        self.setup_seeder()
        time.sleep(10)
        #self.subtest_connect2downloader()
        self.subtest_download()

    
    def setup_seeder(self):
        self.tdef = TorrentDef()
        # semi automatic
        self.bitrate = 6144
        piecesize = 32768
        self.npieces = 12
        playtime = ((self.npieces-1)*piecesize)/self.bitrate
        playtimestr = '0:'+str(playtime) # DON'T WORK IF > 60 secs
        self.tdef.create_live("Test Live",self.bitrate,playtimestr)
        self.tdef.set_tracker(self.session.get_internal_tracker_url())
        self.tdef.set_piece_length(piecesize)
        self.tdef.finalize()

        self.torrentfn = os.path.join(self.session.get_state_dir(),"gen.torrent")
        self.tdef.save(self.torrentfn)
        
        print >>sys.stderr,"test: setup_seeder: name is",self.tdef.metainfo['info']['name']

        self.dscfg = DownloadStartupConfig()
        self.dscfg.set_dest_dir(os.getcwd())
        
        # File source
        source = InfiniteSource(piecesize)
        self.dscfg.set_video_ratelimit(self.bitrate)
        self.dscfg.set_video_source(source)
        
        d = self.session.start_download(self.tdef,self.dscfg)
        
        d.set_state_callback(self.seeder_state_callback)
        
    def seeder_state_callback(self,ds):
        d = ds.get_download()
        print >>sys.stderr,"test: seeder:",dlstatus_strings[ds.get_status()],ds.get_progress()
        return (1.0,False)

        
    def subtest_download(self):
        """ Now download the file via another Session """
        
        self.config2 = self.config.copy() # not really necess
        self.config_path2 = tempfile.mkdtemp()
        self.config2.set_state_dir(self.config_path2)
        self.config2.set_listen_port(self.mylistenport)
        self.session2 = Session(self.config2,ignore_singleton=True)
        
        # Allow session2 to start
        print >>sys.stderr,"test: downloader: Sleeping 3 secs to let Session2 start"
        time.sleep(3)
        
        tdef2 = TorrentDef.load(self.torrentfn)

        dscfg2 = DownloadStartupConfig()
        dscfg2.set_dest_dir(self.config_path2)
        dscfg2.set_video_start_callback(self.downloader_vod_ready_callback)
        
        d = self.session2.start_download(tdef2,dscfg2)
        d.set_state_callback(self.downloader_state_callback)
        
        time.sleep(40)
        # To test if BITFIELD is indeed wrapping around.
        self.subtest_connect2downloader()
        time.sleep(80)
    
    def downloader_state_callback(self,ds):
        d = ds.get_download()
        print >>sys.stderr,"test: download:",dlstatus_strings[ds.get_status()],ds.get_progress()
        
        return (1.0,False)

    def downloader_vod_ready_callback(self,d,mimetype,stream,filename):
        """ Called by SessionThread """
        while True:
            # Fake video playback
            data = stream.read(self.bitrate)
            if len(data) == 0:
                break
            time.sleep(1)


    def subtest_connect2downloader(self):
        
        print >> sys.stderr,"test: verifier: Connecting to seeder to check bitfield"
        
        infohash = self.tdef.get_infohash()
        s = BTConnection('localhost',self.mylistenport,user_infohash=infohash)
        s.read_handshake_medium_rare()
        
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            print >> sys.stderr,"test: verifier: Got message",getMessageName(resp[0])
            self.assert_(resp[0] == EXTEND)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            print >> sys.stderr,"test: verifier: Got 2nd message",getMessageName(resp[0])
            self.assert_(resp[0] == BITFIELD)
            b = Bitfield(self.npieces,resp[1:])
            print >> sys.stderr,"test: verifier: Bitfield is",`b.toboollist()`

            b2 = Bitfield(self.npieces)
            b2[0] = True
            msg = BITFIELD+b2.tostring()
            s.send(msg)
            
            time.sleep(5)
            
        except socket.timeout:
            print >> sys.stderr,"test: verifier: Timeout, peer didn't reply"
            self.assert_(False)
        s.close()
        
        
class InfiniteSource:
    def __init__(self, piece_length):
        self.emptypiece = " " * piece_length

    def read(self,len):
        return self.emptypiece[:len]

    def close(self):
        pass


        
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
