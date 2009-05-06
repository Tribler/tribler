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
from traceback import print_exc
from types import DictType,StringType,IntType

from Tribler.Test.test_extend_hs import TestExtendHandshake
from olconn import OLConnection
from btconn import BTConnection
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BitTornado.BT1.track import compact_ip,decompact_ip
from Tribler.Core.Utilities.Crypto import sha
from Tribler.Core.Utilities.utilities import isValidIP

DEBUG=True

class TestNetworkAwareExtendHandshake(TestExtendHandshake):
    """ 
    Test our network awareness code that tries to detect if we're behind
    the same NAT and if so, connect via the internal network.
    
    See BitTornado/BT1/Connecter.py
    """

    def setUp(self):
        """ override TestAsServer """
        TestExtendHandshake.setUp(self)

    def setUpPreSession(self):
        """ override TestAsServer """
        TestExtendHandshake.setUpPreSession(self)
    
    def setUpPostSession(self):
        """ override TestAsServer """
        TestExtendHandshake.setUpPostSession(self)

        # Create a fake "internal network interface"
        self.setUpMyListenSocket()

        self.myid = "R------andomPeer4811"
        
    def setUpDownloadConfig(self):
        dscfg = TestExtendHandshake.setUpDownloadConfig(self)
        
        dscfg.set_same_nat_try_internal(True)
        dscfg.set_unchoke_bias_for_internal(481)
        return dscfg

    def setUpMyListenSocket(self):
        self.destport = 4811
        
        # Start our server side, to with Tribler will try to connect
        self.destss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.destss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.destss.bind(('', self.destport))
        self.destss.listen(1)

    def singtest_ext_ip_unknown(self):
        """ Send EXTEND hs to Tribler with yourip set to 127.0.0.1, so it
        appears we are using the same IP address. Tribler doesn't know its
        own external IP address, so it will do a loopback test to yourip
        to check. If this check succeeds it will connect to us via the 
        internal network, i.e., our internal interface self.destss.
        """
        self.session.lm.upnp_ext_ip = None
        self.subtest_good_tribler_extend_hs()
       
        
    def singtest_ext_ip_known(self):
        """ Same as singtest_ext_ip_unknown() except no loopback test is needed
        as Tribler knows its external IP and it will be the same as the sent yourip.
        """
        self.session.lm.upnp_ext_ip = '127.0.0.1'
        self.subtest_good_tribler_extend_hs()
        
        
    #
    # Good EXTEND handshake message
    #
    def subtest_good_tribler_extend_hs(self):
        self._test_good(self.create_good_tribler_extend_hs,infohash=self.infohash)
        
    def _test_good(self,msg_gen_func,options=None,infohash=None):
        
        print >>sys.stderr,"test: test good, gen_func",msg_gen_func
        
        if options is None and infohash is None:
            s = BTConnection('localhost',self.hisport,myid=self.myid)
        elif options is None:
            s = BTConnection('localhost',self.hisport,user_infohash=infohash,myid=self.myid)
        elif infohash is None:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options,myid=self.myid)
        else:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=infohash,myid=self.myid)
        msg = msg_gen_func()
        s.send(msg)
        s.read_handshake_medium_rare()
        time.sleep(5)

        # Tribler should send an EXTEND message back
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            print >>sys.stderr,"test: Got reply",getMessageName(resp[0])
            self.assert_(resp[0] == EXTEND)
            self.check_tribler_extend_hs(resp[1:])
            #s.close()
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with EXTEND message"
            self.assert_(False)

        # Tribler should try to connect to our internal interface
        self.destss.settimeout(10.0)
        conn, addr = self.destss.accept()
        s2 = BTConnection('',0,conn,user_infohash=self.infohash,myid=self.myid)
        s2.send(INTERESTED)
        s2.read_handshake_medium_rare()
        
        # Is it him?
        self.assert_(s.hisid == s2.hisid)

        # He should close original conn
        try:
            while True:
                resp = s.recv()
                if len(resp) > 0:
                    print >>sys.stderr,"test: Got data on internal conn",getMessageName(resp[0])
                else:
                    break
        except socket.timeout:
            self.assert_(False)
                
        self.assert_(True)
        

    def create_good_tribler_extend_hs(self):
        d = {}
        d['m'] = {'Tr_OVERLAYSWARM':253}
        d['p'] = self.mylistenport
        d['v'] = 'Tribler 4.5.0'
        d['yourip'] = compact_ip('127.0.0.1')
        d['ipv4'] = compact_ip('224.4.8.1')
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
        
        print >>sys.stderr,"test: Reply is",`d`

def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_na_extend_hs.py <method name>"
    else:
        suite.addTest(TestNetworkAwareExtendHandshake(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
