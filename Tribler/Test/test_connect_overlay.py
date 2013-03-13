# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Test whether Tribler tries to establish an overlay connection when it meets
# another Tribler peer in a swarm.
#
# Like test_secure_overlay, we start a new python interpreter for each test.
# Although we don't have the singleton problem here, we do need to do this as the
# HTTPServer that MyTracker uses won't relinquish the listen socket, causing
# "address in use" errors in the next test. This is probably due to the fact that
# MyTracker has a thread mixed in, as a listensocket.close() normally releases it
# (according to lsof).
#

import unittest
import os
import sys
import time
from traceback import print_exc
import socket
import thread
import BaseHTTPServer
from SocketServer import ThreadingMixIn

from Tribler.Test.test_as_server import TestAsServer
from btconn import BTConnection
from olconn import OLConnection
from Tribler.Core.TorrentDef import *
from Tribler.Core.DownloadConfig import *
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.MessageID import *

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
            print_exc()



class TestConnectOverlay(TestAsServer):
    """
    Testing download helping
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >>sys.stderr,"test: Giving MyLaunchMany time to startup"
        time.sleep(5)
        print >>sys.stderr,"test: MyLaunchMany should have started up"

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)

        # Start our server side, to with Tribler will try to connect
        self.mylistenport = 4810
        self.myss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.myss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.myss.bind(('', self.mylistenport))
        self.myss.listen(1)

        # Must be changed in test/extend_hs_dir/dummydata.merkle.torrent as well
        self.mytrackerport = 4901
        self.myid = 'R410-----HgUyPu56789'
        self.mytracker = MyTracker(self.mytrackerport,self.myid,'127.0.0.1',self.mylistenport)
        self.mytracker.background_serve()

        self.myid2 = 'R410-----56789HuGyx0'


    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())

        # This is the infohash of the torrent in test/extend_hs_dir
        self.infohash = '\xccg\x07\xe2\x9e!]\x16\xae{\xb8\x10?\xf9\xa5\xf9\x07\xfdBk'
        self.torrentfile = os.path.join('extend_hs_dir','dummydata.merkle.torrent')

        # Let Tribler start downloading an non-functioning torrent, so
        # we can talk to a normal download engine.

        tdef = TorrentDef.load(self.torrentfile)

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(self.config_path)

        self.session.start_download(tdef,dscfg)


    def tearDown(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: *** TEARDOWN"
        TestAsServer.tearDown(self)
        self.mytracker.shutdown()
        self.myss.close()


    #
    #
    def singtest_connect_overlay(self):
        """
        """
        # 1. Accept the data connection Tribler wants to establish with us
        self.myss.settimeout(10.0)
        conn, addr = self.myss.accept()
        s = BTConnection('',0,conn,user_infohash=self.infohash,myid=self.myid)
        s.read_handshake_medium_rare()

        extmsg = self.create_good_tribler_extend_hs()
        s.send(extmsg)
        resp = s.recv()
        self.assert_(len(resp) > 0)
        print >> sys.stderr,"test: Data conn replies",getMessageName(resp[0])

        # 2. Tribler should now try to establish an overlay connection with us
        self.myss.settimeout(10.0)
        conn, addr = self.myss.accept()
        options = '\x00\x00\x00\x00\x00\x00\x00\x00'
        s2 = OLConnection(self.my_keypair,'',0,conn,mylistenport=self.mylistenport)

        # Desired behaviour is that the accept() succeeds. If not it will time
        # out, and throw an exception, causing this test to fail.
        time.sleep(3)

        s.close()
        s2.close()


    def create_good_tribler_extend_hs(self,pex_id=1):
        d = {}
        d['m'] = {'Tr_OVERLAYSWARM':253,'ut_pex':pex_id}
        d['p'] = self.mylistenport
        d['v'] = 'Tribler 3.5.1'
        d['e'] = 0
        bd = bencode(d)
        return EXTEND+chr(0)+bd


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_connect_overlay.py <method name>"
    else:
        suite.addTest(TestConnectOverlay(sys.argv[1]))

    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
