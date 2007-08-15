# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
from sha import sha
from random import randint,shuffle
from traceback import print_exc
from types import StringType, ListType, DictType
from threading import Thread
from time import sleep
import socket

from test_as_server import TestAsServer
from btconn import BTConnection
from olconn import OLConnection
from BitTornado.bencode import bencode,bdecode
from BitTornado.bitfield import Bitfield
from BitTornado.BT1.MessageID import *
from BitTornado.BT1.convert import toint
from Tribler.CacheDB.CacheDBHandler import FriendDBHandler
from test.test_extend_hs_t350 import MyTracker

DEBUG=True

class TestDownloadHelp(TestAsServer):
    """ 
    Testing download helping
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >>sys.stderr,"test: Giving MyLaunchMany time to startup"
        time.sleep(5)
        print >>sys.stderr,"test: MyLaunchMany should have started up"

    def setUpPreTriblerInit(self):
        """ override TestAsServer """
        TestAsServer.setUpPreTriblerInit(self)
        
        torrent2dir = os.path.join(self.config_path,'torrent2')
        os.mkdir(torrent2dir)
        
        self.config['torrent_dir'] = torrent2dir
        self.config['saveas_style'] = 1 # must be 1 for security during download helping
        self.config['priority'] = 1
        self.config['display_path'] = 1

        self.setUpMyListenSockets()
        
        # Must be changed in test/extend_hs_dir/dummydata.merkle.torrent as well
        self.mytrackerport = 4901
        self.myid = 'R410-----HgUyPu56789'
        self.mytracker = MyTracker(self.mytrackerport,self.myid,'127.0.0.1',self.mylistenport)
        self.mytracker.background_serve()

        self.myid2 = 'R410-----56789HuGyx0'

        print >>sys.stderr,"test: Giving MyTracker and myself time to start"
        time.sleep(5)

    def setUpMyListenSockets(self):
        # Start our server side, to with Tribler will try to connect
        self.mylistenport = 4810
        self.myss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.myss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.myss.bind(('', self.mylistenport))
        self.myss.listen(1)

        self.mylistenport2 = 481
        self.myss2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.myss2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.myss2.bind(('', self.mylistenport2))
        self.myss2.listen(1)


    def setUpPreLaunchMany(self):
        """ override TestAsServer """
        TestAsServer.setUpPreLaunchMany(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())  
        
        # This is the infohash of the torrent in test/extend_hs_dir
        self.infohash = '\xccg\x07\xe2\x9e!]\x16\xae{\xb8\x10?\xf9\xa5\xf9\x07\xfdBk'
        self.torrentfile = os.path.join('test','extend_hs_dir','dummydata.merkle.torrent')

        # Add us as friend, so he will accept the DOWNLOAD_HELP
        friendsdb = FriendDBHandler()
        friendsdb.addFriend(self.mypermid)      

    def tearDown(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: *** TEARDOWN"
        TestAsServer.tearDown(self)
        self.tearDownMyListenSockets()

    def tearDownMyListenSockets(self):
        self.myss.close()
        self.myss2.close()


    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        # 1. test good DOWNLOAD_HELP
        self.subtest_good_dlhelp()


    #
    # Good DOWNLOAD_HELP
    #
    def subtest_good_dlhelp(self):
        """ 
            test good DOWNLOAD_HELP message
        """
        print >>sys.stderr,"test: good DOWNLOAD_HELP"
        
        # 1. Establish overlay connection to Tribler
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_dlhelp()
        s.send(msg)
        resp = s.recv()
        self.assert_(resp[0] == GET_METADATA)
        self.check_get_metadata(resp[1:])
        print >>sys.stderr,"test: Got GET_METADATA for torrent, good"
        
        msg = self.create_good_metadata()
        s.send(msg)

        # 2. Accept the data connection Tribler wants to establish with us, the coordinator
        self.myss2.settimeout(10.0)
        conn, addr = self.myss2.accept()
        s3 = BTConnection('',0,conn,user_infohash=self.infohash,myid=self.myid2)
        s3.read_handshake_medium_rare()
        
        msg = UNCHOKE
        s3.send(msg)
        print >>sys.stderr,"test: Got data connection to us, as coordinator, good"


        # 3. The tracker says there is another peer (also us) on port 4810
        # Now accept a connection on that port and pretend we're a seeder
        self.myss.settimeout(10.0)
        conn, addr = self.myss.accept()
        options = '\x00\x00\x00\x00\x00\x00\x00\x00'
        s2 = BTConnection('',0,conn,user_option_pattern=options,user_infohash=self.infohash,myid=self.myid)
        s2.read_handshake_medium_rare()
        
        numpieces = 10 # must correspond to the torrent in test/extend_hs_dir
        b = Bitfield(numpieces)
        for i in range(numpieces):
            b[i] = True
        self.assert_(b.complete())
        msg = BITFIELD+b.tostring()
        s2.send(msg)
        msg = UNCHOKE
        s2.send(msg)
        print >>sys.stderr,"test: Got BT connection to us, as fake seeder, good"

        # 4. Await a RESERVE_PIECES message on the overlay connection
        resp = s.recv()
        self.assert_(resp[0] == RESERVE_PIECES)
        pieces = self.check_reserve_pieces(resp[1:])
        print >>sys.stderr,"test: Got RESERVE_PIECES, good"
        
        # 5. Reply with PIECES_RESERVED
        msg = self.create_good_pieces_reserved(pieces)
        s.send(msg)
        
        # 6. Await REQUEST on fake seeder
        while True:
            resp = s2.recv()
            self.assert_(len(resp) > 0)
            print "test: Fake seeder got message",getMessageName(resp[0])
            if resp[0] == REQUEST:
                self.check_request(resp[1:],pieces)
                print >>sys.stderr,"test: Fake seeder got REQUEST for reserved piece, good"
                break
        
        # 5. Reply with STOP_DOWNLOAD_HELP
        msg = self.create_good_stop_dlhelp()
        s.send(msg)
        
        # the other side should close the connection
        resp = s.recv()
        self.assert_(len(resp)==0)
        s.close()
        

    def create_good_dlhelp(self):
        return DOWNLOAD_HELP+self.infohash

    def check_get_metadata(self,data):
        infohash = bdecode(data) # is bencoded for unknown reason, can't change it
        self.assert_(infohash == self.infohash)

    def create_good_metadata(self):
        f = open(self.torrentfile,"rb")
        data = f.read()
        f.close() 
        
        d = {}
        d['torrent_hash'] = self.infohash 
        d['metadata'] = data
        d['leecher'] = 1
        d['seeder'] = 1
        d['last_check_time'] = int(time.time())
        d['status'] = 'good'
        bd = bencode(d)
        return METADATA+bd


    def check_reserve_pieces(self,data):
        # torrent_hash + 1-byte all_or_nothing + bencode([piece num,...])
        self.assert_(len(data) > 21)
        infohash = data[0:20]
        allflag = data[20]
        plist = bdecode(data[21:])
        
        self.assert_(infohash == self.infohash)
        self.assert_(type(plist) == ListType)
        return plist

    def create_good_pieces_reserved(self,pieces):
        payload = self.infohash + bencode(pieces)
        return PIECES_RESERVED + payload

    def check_request(self,data,pieces):
        piece = toint(data[0:4])
        self.assert_(piece in pieces)

    def create_good_stop_dlhelp(self):
        return STOP_DOWNLOAD_HELP+self.infohash


    #
    # Bad DOWNLOAD_HELP
    #    
    def subtest_bad_dlhelp(self):
        self._test_bad(self.create_not_infohash)

    def create_not_infohash(self):
        return DOWNLOAD_HELP+"481"

    def _test_bad(self,gen_soverlap_func):
        print >>sys.stderr,"test: bad DOWNLOAD_HELP",gen_soverlap_func
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = gen_soverlap_func()
        s.send(msg)
        time.sleep(5)
        # the other side should not like this and close the connection
        self.assert_(len(s.recv())==0)
        s.close()



def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestDownloadHelp))
    
    return suite

def sign_data(plaintext,keypair):
    digest = sha(plaintext).digest()
    return keypair.sign_dsa_asn1(digest)

def verify_data(plaintext,permid,blob):
    pubkey = EC.pub_key_from_der(permid)
    digest = sha(plaintext).digest()
    return pubkey.verify_dsa_asn1(digest,blob)


if __name__ == "__main__":
    unittest.main()

