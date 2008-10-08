# Written by Arno Bakker
# see LICENSE.txt for license information
#

import unittest
import os
import sys
import time
import socket
from sha import sha
from traceback import print_exc
from types import DictType,StringType,IntType

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from btconn import BTConnection
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.DownloadConfig import *
from Tribler.Core.Utilities.utilities import isValidIP

DEBUG=True
G2G_ID = 235

class TestG2G(TestAsServer):
    """ 
    Testing EXTEND G2G message V2:

    See BitTornado/BT1/Connecter.py
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >>sys.stderr,"test: Giving MyLaunchMany time to startup"
        time.sleep(3)
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
        dscfg.set_video_event_callback(self.vod_ready_callback)
        
        self.d = self.session.start_download(tdef,dscfg)
        
        # This is the infohash of the torrent in test/extend_hs_dir
        self.infohash = '\xccg\x07\xe2\x9e!]\x16\xae{\xb8\x10?\xf9\xa5\xf9\x07\xfdBk'
        self.mylistenport = 4810

    def vod_ready_callback(self,d,event,params):
        pass

    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        self.subtest_good_tribler_g2g_v2()
        self.subtest_bad_g2g_v2()

    #
    # Good g2g_v2 message
    #
    def subtest_good_tribler_g2g_v2(self):
        self._test_good(self.create_good_tribler_extend_hs_v2,infohash=self.infohash)
        
        # We've said we're a Tribler peer, and we initiated the connection, so 
        # now *we* should now try to establish an overlay-swarm connection.
        s = OLConnection(self.my_keypair,'localhost',self.hisport,mylistenport=self.mylistenport)
        # the connection should be intact, so this should not throw an
        # exception:
        time.sleep(5)
        s.send('bla')
        s.close()

    def _test_good(self,msg_gen_func,options=None,infohash=None,g2g_id=G2G_ID):
        if options is None and infohash is None:
            s = BTConnection('localhost',self.hisport)
        elif options is None:
            s = BTConnection('localhost',self.hisport,user_infohash=infohash)
        elif infohash is None:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options)
        else:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=infohash)
            
        if DEBUG:
            print "test: Creating test HS message",msg_gen_func,"g2g_id",g2g_id
        msg = msg_gen_func(g2g_id=g2g_id)
        s.send(msg)
        s.read_handshake_medium_rare()

        # Send our g2g_v2 message to Tribler
        msg = self.create_good_g2g_v2(g2g_id=g2g_id)
        s.send(msg)
        
        time.sleep(5)

        # Tribler should send an EXTEND HS message back
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            self.assert_(resp[0] == EXTEND)
            self.check_tribler_extend_hs_v2(resp[1:])
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with EXTEND HS message"
            self.assert_(False)

        # Tribler should send an g2g_v2 message after a while
        print "test: Setting 60 second timeout to see if Tribler sends periodic g2g_v2"
        
        # Extreme h4xor
        connlist = self.d.sd.dow.connecter.connections.values()[:]
        piece = '\xab' * (2 ** 14)
        for conn in connlist:
            conn.queue_g2g_piece_xfer(0,0,piece)
        
        try:
            s.s.settimeout(70.0)
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print "test: Tribler returns",getMessageName(resp[0])
                if resp[0] == EXTEND:
                    self.check_g2g_v2(resp[1:],g2g_id=g2g_id)
                    s.close()
                    break
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with EXTEND g2g_v2 message"
            self.assert_(False)

        
    def create_good_tribler_extend_hs_v2(self,g2g_id=G2G_ID):
        d = {}
        d['m'] = {'Tr_OVERLAYSWARM':253,'Tr_G2G_v2':g2g_id}
        d['p'] = self.mylistenport
        d['v'] = 'Tribler 4.2.0'
        d['e'] = 0
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def check_tribler_extend_hs_v2(self,data):
        self.assert_(data[0] == chr(0))
        d = bdecode(data[1:])
        self.assert_(type(d) == DictType)
        self.assert_('m' in d.keys())
        m = d['m']
        self.assert_(type(m) == DictType)
        self.assert_('Tr_OVERLAYSWARM' in m.keys())
        val = m['Tr_OVERLAYSWARM']
        self.assert_(type(val) == IntType)
        self.assert_(val == 253)
        self.assert_('Tr_G2G_v2' in m.keys())
        val = m['Tr_G2G_v2']
        self.assert_(type(val) == IntType)
        self.assert_(val == G2G_ID)

    def create_good_g2g_v2(self,g2g_id=G2G_ID):
        d = {'0':'d','1':'b'}
        bd = bencode(d)
        return EXTEND+chr(g2g_id)+bd

    def check_g2g_v2(self,data,g2g_id):
        self.assert_(data[0] == chr(g2g_id))
        d = bdecode(data[1:])
        
        print >>sys.stderr,"test: l is",`d`
        
        self.assert_(type(d) == DictType)
        for k,v in d.iteritems():
            self.assert_(type(k) == StringType)
            self.assert_(type(v) == StringType)
            self.assert_(ord(k) > 0)
            self.assert_(ord(v) <= 100)
            
    #
    # Bad EXTEND handshake message
    #    
    def subtest_bad_g2g_v2(self):
        methods = [self.create_empty,
            self.create_ext_id_not_byte,
            self.create_not_bdecodable,
            self.create_not_dict1,
            self.create_not_dict2,
            self.create_key_not_int,
            self.create_val_not_str,
            self.create_val_too_big]

        for m in methods:
            self._test_bad(m)

    #
    # Main test code for bad EXTEND g2g_v2 messages
    #
    def _test_bad(self,gen_drequest_func):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=self.infohash)
        print >> sys.stderr,"\ntest: ",gen_drequest_func
        
        hsmsg = self.create_good_tribler_extend_hs_v2()
        s.send(hsmsg)
        
        msg = gen_drequest_func()
        s.send(msg)
        time.sleep(5)
        
        # the other side should not like this and close the connection
        try:
            s.s.settimeout(10.0)
            s.read_handshake_medium_rare(close_ok = True)
            while True:
                resp = s.recv()
                if len(resp) > 0:
                    print >>sys.stderr,"test: Got",getMessageName(resp[0]),"from peer"
                    self.assert_(resp[0] == EXTEND or resp[0]==UNCHOKE)
                else:
                    self.assert_(len(resp)==0)
                    s.close()
                    break
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't close connection"
            self.assert_(False)

    #
    # Bad message creators
    # 
    def create_empty(self):
        return EXTEND+chr(G2G_ID)

    def create_ext_id_not_byte(self):
        return EXTEND+'Hallo kijkbuiskinderen'
    
    def create_not_bdecodable(self):
        return EXTEND+chr(G2G_ID)+"bla"

    def create_not_dict1(self):
        d = 481
        bd = bencode(d)
        return EXTEND+chr(G2G_ID)+bd

    def create_not_dict2(self):
        d = []
        bd = bencode(d)
        return EXTEND+chr(G2G_ID)+bd

    def create_key_not_int(self):
        d = {'hallo':'d'}
        bd = bencode(d)
        return EXTEND+chr(G2G_ID)+bd
        
    def create_val_not_str(self):
        d = {'481':481}
        bd = bencode(d)
        return EXTEND+chr(G2G_ID)+bd

    def create_val_too_big(self):
        d = {'481':chr(129)}
        bd = bencode(d)
        return EXTEND+chr(G2G_ID)+bd


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestG2G))
    
    return suite

if __name__ == "__main__":
    unittest.main()

