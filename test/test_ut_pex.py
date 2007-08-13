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

from test_as_server import TestAsServer
from olconn import OLConnection
from btconn import BTConnection
from BitTornado.bencode import bencode,bdecode
from BitTornado.BT1.MessageID import *

from Tribler.utilities import isValidIP

DEBUG=True

class TestUTorrentPeerExchange(TestAsServer):
    """ 
    Testing EXTEND uTorrent Peer Exchange message:

    See BitTornado/BT1/Connecter.py and Tribler/DecentralizedTracking/ut_pex.py
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

        # Let Tribler start downloading an non-functioning torrent, so
        # we can talk to a normal download engine.
        self.config['torrent_dir'] = os.path.join('test','extend_hs_dir')
        self.config['parse_dir_interval'] = 60
        self.config['saveas_style'] = 1
        self.config['priority'] = 1
        self.config['display_path'] = 1
        
        # This is the infohash of the torrent in test/extend_hs_dir
        self.infohash = '\xccg\x07\xe2\x9e!]\x16\xae{\xb8\x10?\xf9\xa5\xf9\x07\xfdBk'
        self.mylistenport = 4810

    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        # Create a fake other client, so the EXTEND ut_pex won't be empty
        msg2 = self.create_good_nontribler_extend_hs(listenport=4321)
        s2 = BTConnection('localhost',self.hisport,mylistenport=4321,user_option_pattern='\x00\x00\x00\x00\x00\x10\x00\x00',user_infohash=self.infohash)
        s2.read_handshake_medium_rare()
        s2.send(msg2)

        self.subtest_good_nontribler_ut_pex()
        self.subtest_good_nontribler_ut_pex_diff_id()
        self.subtest_good_tribler_ut_pex()
        self.subtest_bad_ut_pex()


    #
    # Good ut_pex message
    #
    def subtest_good_nontribler_ut_pex(self):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        self._test_good(self.create_good_nontribler_extend_hs,options=options,infohash=self.infohash,pex_id=1)

    def subtest_good_nontribler_ut_pex_diff_id(self):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        self._test_good(self.create_good_nontribler_extend_hs,options=options,infohash=self.infohash,pex_id=134)

    def subtest_good_tribler_ut_pex(self):
        self._test_good(self.create_good_tribler_extend_hs,infohash=self.infohash)
        
        # We've said we're a Tribler peer, and we initiated the connection, so 
        # now *we* should now try to establish an overlay-swarm connection.
        s = OLConnection(self.my_keypair,'localhost',self.hisport,mylistenport=self.mylistenport)
        # the connection should be intact, so this should not throw an
        # exception:
        time.sleep(5)
        s.send('bla')
        s.close()

    def _test_good(self,msg_gen_func,options=None,infohash=None,pex_id=1):
        if options is None and infohash is None:
            s = BTConnection('localhost',self.hisport)
        elif options is None:
            s = BTConnection('localhost',self.hisport,user_infohash=infohash)
        elif infohash is None:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options)
        else:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=infohash)
            
        if DEBUG:
            print "test: Creating test HS message",msg_gen_func,"pex_id",pex_id
        msg = msg_gen_func(pex_id=pex_id)
        s.send(msg)
        s.read_handshake_medium_rare()

        # Send our ut_pex message to Tribler
        msg = self.create_good_ut_pex(pex_id=pex_id)
        s.send(msg)
        
        time.sleep(5)

        # Tribler should send an EXTEND HS message back
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            self.assert_(resp[0] == EXTEND)
            self.check_tribler_extend_hs(resp[1:])
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with EXTEND HS message"
            self.assert_(False)

        # Tribler should send an ut_pex message after a while
        try:
            s.s.settimeout(70.0)
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print "test: Tribler returns",getMessageName(resp[0])
                if resp[0] == EXTEND:
                    self.check_ut_pex(resp[1:],pex_id=pex_id)
                    s.close()
                    break
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with EXTEND ut_pex message"
            self.assert_(False)

        

    def create_good_nontribler_extend_hs(self,listenport=None,pex_id=1):
        d = {}
        d['m'] = {'ut_pex':pex_id, 'dag':255 }
        if listenport is None:
            d['p'] = self.mylistenport
        else:
            d['p'] = listenport
        d['v'] = 'TestSweet 1.2.3.4'
        d['e'] = 0
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_good_tribler_extend_hs(self,pex_id=1):
        d = {}
        d['m'] = {'Tr_OVERLAYSWARM':253,'ut_pex':pex_id}
        d['p'] = self.mylistenport
        d['v'] = 'Tribler 3.5.1'
        d['e'] = 0
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def check_tribler_extend_hs(self,data):
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
        self.assert_('ut_pex' in m.keys())
        val = m['ut_pex']
        self.assert_(type(val) == IntType)
        self.assert_(val == 1)

    def create_good_ut_pex(self,pex_id=1):
        d = {}
        d['added'] = ''
        d['added.f'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(pex_id)+bd

    def check_ut_pex(self,data,pex_id):
        self.assert_(data[0] == chr(pex_id))
        d = bdecode(data[1:])
        self.assert_(type(d) == DictType)
        self.assert_('added' in d.keys())
        cp = d['added']
        apeers = self.check_compact_peers(cp)
        self.assert_('added.f' in d.keys())
        f = d['added.f']
        print "test: Length of added.f",len(f)
        self.assert_(type(f) == StringType)
        self.assert_(len(apeers) == len(f))
        self.assert_('dropped' in d.keys())
        cp = d['dropped']
        self.check_compact_peers(cp)
        
        # Check that the fake client we created is included
        self.assert_(len(apeers) == 1)
        self.assert_(apeers[0][1] == 4321)
        

    def check_compact_peers(self,cp):
        self.assert_(type(cp) == StringType)
        self.assert_(len(cp) % 6 == 0)
        peers = []
        for x in xrange(0, len(cp), 6):
            ip = '.'.join([str(ord(i)) for i in cp[x:x+4]])
            port = (ord(cp[x+4]) << 8) | ord(cp[x+5])
            peers.append((ip, port))
        #print "test: Got compact peers",peers
        return peers

    #
    # Bad EXTEND handshake message
    #    
    def subtest_bad_ut_pex(self):
        methods = [self.create_empty,
            self.create_ext_id_not_byte,
            self.create_not_bdecodable,
            self.create_not_dict1,
            self.create_not_dict2,
            self.create_bad_keys,
            self.create_added_missing,
            self.create_added_f_missing,
            self.create_dropped_missing,
            self.create_added_not_str,
            self.create_added_f_not_str,
            self.create_dropped_not_str,
            self.create_added_too_small,
            self.create_added_f_too_big,
            self.create_dropped_too_small]

        for m in methods:
            self._test_bad(m)

    #
    # Main test code for bad EXTEND ut_pex messages
    #
    def _test_bad(self,gen_drequest_func):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=self.infohash)
        print >> sys.stderr,"\ntest: ",gen_drequest_func
        
        hsmsg = self.create_good_nontribler_extend_hs()
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
        return EXTEND+chr(1)

    def create_ext_id_not_byte(self):
        return EXTEND+'Hallo kijkbuiskinderen'
    
    def create_not_bdecodable(self):
        return EXTEND+chr(1)+"bla"

    def create_not_dict1(self):
        d = 481
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_not_dict2(self):
        d = []
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_bad_keys(self):
        d = {}
        d['bla1'] = ''
        d['bla2'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd
        
    def create_added_missing(self):
        d = {}
        d['added.f'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd
        
    def create_added_f_missing(self):
        d = {}
        d['added'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_dropped_missing(self):
        d = {}
        d['added'] = ''
        d['added.f'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_added_not_str(self):
        d = {}
        d['added'] = 481
        d['added.f'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_added_f_not_str(self):
        d = {}
        d['added'] = ''
        d['added.f'] = 481
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_dropped_not_str(self):
        d = {}
        d['added'] = ''
        d['added.f'] = ''
        d['dropped'] = 481
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_added_too_small(self):
        d = {}
        d['added'] = '\x82\x25\xc1\x40\x00' # should be 6 bytes
        d['added.f'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_added_f_too_big(self):
        d = {}
        d['added'] = ''
        d['added.f'] = '\x00'
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_dropped_too_small(self):
        d = {}        
        d['added'] = ''
        d['added.f'] = ''
        d['dropped'] = '\x82\x25\xc1\x40\x00' # should be 6 bytes
        bd = bencode(d)
        return EXTEND+chr(1)+bd



def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestUTorrentPeerExchange))
    
    return suite

if __name__ == "__main__":
    unittest.main()

