# Written by Arno Bakker
# see LICENSE.txt for license information
#

import unittest
import os
import sys
import time
import socket
import thread
from sha import sha
from traceback import print_exc
from types import DictType,StringType,IntType
import BaseHTTPServer
from SocketServer import ThreadingMixIn,BaseServer

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from btconn import BTConnection
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.Utilities.utilities import isValidIP

DEBUG=True

class MyTracker(ThreadingMixIn,BaseHTTPServer.HTTPServer):
    
    def __init__(self,trackport,myid,myip,myport):
        self.myid = myid
        self.myip = myip
        self.myport = myport
        BaseHTTPServer.HTTPServer.__init__( self, ("",trackport), SimpleServer )
        self.daemon_threads = True
        
    def background_serve( self ):
        thread.start_new_thread( self.serve_forever, () )

    def shutdown(self):
        self.socket.close()


class SimpleServer(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):
        
        print >>sys.stderr,"test: tracker: Got GET request",self.path

        p = []
        p1 = {'peer id':self.server.myid,'ip':self.server.myip,'port':self.server.myport}
        p.append(p1)
        d = {}
        d['interval'] = 1800
        d['peers'] = p
        bd = bencode(d)
        size = len(bd)

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", size)
        self.end_headers()
        
        try:
            self.wfile.write(bd)
        except Exception,e:
            print_exc(file=sys.stderr)



class TestExtendHandshakeT350(TestAsServer):
    """ 
    Testing EXTEND handshake message: How Tribler reacts to a Tribler <= 3.5.0
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >>sys.stderr,"test: Giving MyLaunchMany time to startup"
        time.sleep(5)
        print >>sys.stderr,"test: MyLaunchMany should have started up"
    
    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        # Let Tribler start downloading an non-functioning torrent, so
        # we can talk to a normal download engine.
        
        self.torrentfn = os.path.join('extend_hs_dir','dummydata.merkle.torrent')
        tdef = TorrentDef.load(self.torrentfn)

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(self.config_path)
        
        self.session.start_download(tdef,dscfg)

        # This is the infohash of the torrent in test/extend_hs_dir
        self.infohash = '\xccg\x07\xe2\x9e!]\x16\xae{\xb8\x10?\xf9\xa5\xf9\x07\xfdBk'

        self.setUpMyListenSocket()
        
        # Must be changed in test/extend_hs_dir/dummydata.merkle.torrent as well
        self.mytrackerport = 4901
        # Must be Tribler version <= 3.5.0. Changing this to 351 makes this test
        # fail, so it's a good test.
        self.myid = 'R350-----HgUyPu56789'
        self.mytracker = MyTracker(self.mytrackerport,self.myid,'127.0.0.1',self.mylistenport)
        self.mytracker.background_serve()

        print >>sys.stderr,"test: Giving MyTracker and myself time to start"
        time.sleep(5)

    def setUpMyListenSocket(self):
        # Start our server side, to with Tribler will try to connect
        self.mylistenport = 4810
        self.myss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.myss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.myss.bind(('', self.mylistenport))
        self.myss.listen(1)

    def tearDown(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: *** TEARDOWN"
        TestAsServer.tearDown(self)
        self.tearDownMyListenSocket()

    def tearDownMyListenSocket(self):
        self.myss.close()


    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        self.subtest_old_tribler()


    #
    # Good DIALBACK_REQUEST
    #
    def subtest_old_tribler(self):
        # The tracker gives Tribler
        try:
            self.myss.settimeout(10.0)
            conn, addr = self.myss.accept()
            options = '\x00\x00\x00\x00\x00\x10\x00\x00'
            s = BTConnection('',0,conn,user_option_pattern=options,user_infohash=self.infohash,myid=self.myid)
            s.read_handshake_medium_rare()
            
            # Seeing that we're an T<=3.5.0 peer, he should directly 
            # initiate an overlay conn with us
            conn2, addr2 = self.myss.accept()
            s2 = OLConnection(self.my_keypair,'',0,conn2,self.mylistenport)
    
            time.sleep(5)
            # the other side should not have closed the connection, as
            # this is all valid, so this should not throw an exception:
            s.send('bla')
            s.close()
            s2.send('bla')
            s2.close()
            print >> sys.stderr,"test: Good, Tribler made overlay conn with us"
        except socket.timeout:
            print >> sys.stderr,"test: Bad, Tribler did not attempt to start an overlay conn with us"
            self.assert_(False)



def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestExtendHandshakeT350))
    
    return suite

if __name__ == "__main__":
    unittest.main()

