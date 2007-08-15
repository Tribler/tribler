# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO: Let Tribler initiate a BT connection to us. We then pretend to be old client
# and then he should iniate an OL connection to us.
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

class TestExtendHandshake(TestAsServer):
    """ 
    Testing EXTEND handshake message: uTorrent and Bram's BitTorrent now support 
    an extension to the protocol, documented on 
    http://www.rasterbar.com/products/libtorrent/extension_protocol.html

    The problem is that the bit they use in the options field of the BT handshake
    is the same as we use to indicate a peer supports the overlay-swarm connection.
    The new clients will send an EXTEND message with ID 20 after the handshake to
    inform the otherside what new messages it supports.

    See BitTornado/BT1/Connecter.py
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
        self.config['torrent_dir'] = os.path.join('extend_hs_dir')
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
        self.subtest_good_nontribler_extend_hs()
        self.subtest_good_tribler_extend_hs()

        self.subtest_bad_empty()
        self.subtest_bad_ext_id_not_byte()
        self.subtest_bad_not_hs()
        self.subtest_bad_not_bdecodable()
        self.subtest_bad_not_dict1()
        self.subtest_bad_not_dict2()
        self.subtest_bad_m_not_dict1()
        self.subtest_bad_m_not_dict2()
        # bencode doesn't permit this:
        #self.subtest_bad_m_key_not_str()
        self.subtest_bad_m_val_not_int()
        
        # Tribler doesn't check for these
        ##self.subtest_bad_p_not_int()
        ##self.subtest_bad_v_not_utf8str()


    #
    # Good EXTEND handshake message
    #
    def subtest_good_nontribler_extend_hs(self):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        self._test_good(self.create_good_nontribler_extend_hs,options=options,infohash=self.infohash)

    def subtest_good_tribler_extend_hs(self):
        self._test_good(self.create_good_tribler_extend_hs,infohash=self.infohash)
        
        # We've said we're a Tribler peer, and we initiated the connection, so 
        # now *we* should now try to establish an overlay-swarm connection.
        s = OLConnection(self.my_keypair,'localhost',self.hisport,mylistenport=self.mylistenport)
        # the connection should be intact, so this should not throw an
        # exception:
        time.sleep(5)
        s.send('bla')
        s.close()

    def _test_good(self,msg_gen_func,options=None,infohash=None):
        if options is None and infohash is None:
            s = BTConnection('localhost',self.hisport)
        elif options is None:
            s = BTConnection('localhost',self.hisport,user_infohash=infohash)
        elif infohash is None:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options)
        else:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=infohash)
        msg = msg_gen_func()
        s.send(msg)
        s.read_handshake_medium_rare()
        time.sleep(5)

        # Tribler should send an EXTEND message back
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            self.assert_(resp[0] == EXTEND)
            self.check_tribler_extend_hs(resp[1:])
            #s.close()
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with EXTEND message"
            self.assert_(False)
        

    def create_good_nontribler_extend_hs(self):
        d = {}
        d['m'] = {'hallo':12, 'dag':255 }
        d['p'] = self.mylistenport
        d['v'] = 'TestSweet 1.2.3.4'
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_good_tribler_extend_hs(self):
        d = {}
        d['m'] = {'Tr_OVERLAYSWARM':253}
        d['p'] = self.mylistenport
        d['v'] = 'Tribler 3.5.1'
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

    #
    # Bad EXTEND handshake message
    #    
    def subtest_bad_empty(self):
        self._test_bad(self.create_empty)

    def subtest_bad_ext_id_not_byte(self):
        self._test_bad(self.create_ext_id_not_byte)
    
    def subtest_bad_not_hs(self):
        self._test_bad(self.create_not_hs)
    
    def subtest_bad_not_bdecodable(self):
        self._test_bad(self.create_not_bdecodable)

    def subtest_bad_not_dict1(self):
        self._test_bad(self.create_not_dict1)

    def subtest_bad_not_dict2(self):
        self._test_bad(self.create_not_dict2)

    def subtest_bad_m_not_dict1(self):
        self._test_bad(self.create_m_not_dict1)

    def subtest_bad_m_not_dict2(self):
        self._test_bad(self.create_m_not_dict2)

    def subtest_bad_m_key_not_str(self):
        self._test_bad(self.create_m_key_not_str)

    def subtest_bad_m_val_not_int(self):
        self._test_bad(self.create_m_val_not_int)

    def subtest_bad_p_not_int(self):
        self._test_bad(self.create_p_not_int)

    def subtest_bad_v_not_utf8str(self):
        self._test_bad(self.create_v_not_utf8str)

    #
    # Main test code for bad EXTEND handshake messages
    #
    def _test_bad(self,gen_drequest_func):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=self.infohash)
        print >> sys.stderr,"\ntest: ",gen_drequest_func
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
        return EXTEND

    def create_ext_id_not_byte(self):
        return EXTEND+'Hallo kijkbuiskinderen'
    
    def create_not_hs(self):
        d = {}
        bd = bencode(d)
        return EXTEND+chr(231)+bd

    def create_not_bdecodable(self):
        return EXTEND+chr(0)+"bla"

    def create_not_dict1(self):
        d = 481
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_not_dict2(self):
        d = []
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_m_not_dict1(self):
        m = 481
        d={'m':m}
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_m_not_dict2(self):
        m = []
        d={'m':m}
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_m_key_not_str(self):
        m = {481:123}
        d={'m':m}
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_m_val_not_int(self):
        m = {'Message for ya, sir':[]}
        d={'m':m}
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_p_not_int(self):
        p = []
        d={'p':p}
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_v_not_utf8str(self):
        v = []
        d={'v':v}
        bd = bencode(d)
        return EXTEND+chr(0)+bd


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestExtendHandshake))
    
    return suite

if __name__ == "__main__":
    unittest.main()

