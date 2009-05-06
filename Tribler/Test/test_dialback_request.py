# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
import socket
from Tribler.Core.Utilities.Crypto import sha
from traceback import print_exc
from types import StringType

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from btconn import BTConnection
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.NATFirewall.ReturnConnHandler import dialback_infohash
from Tribler.Core.Utilities.utilities import isValidIP

DEBUG=True

class TestDialbackRequest(TestAsServer):
    """ 
    Testing DIALBACK_REQUEST message of Dialback extension V1
    """
    
    #def setUp(self):
    #    """ override TestAsServer """
    #    TestAsServer.setUp(self)

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)

        # Enable dialback
        self.config.set_dialback(True)
        # H4X0R: testing only
        self.config.sessconfig['dialback_active'] = 0

        self.setUpMyListenSocket()

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)
        self.myip = '127.0.0.1'

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
        # 1. test good DIALBACK_REQUEST
        self.subtest_good_drequest()
        
        # 2. test various bad DIALBACK_REQUEST messages
        self.subtest_bad_not_empty()

    #
    # Good DIALBACK_REQUEST
    #
    def subtest_good_drequest(self):
        """ 
            test good DIALBACK_REQUEST messages
        """
        s = OLConnection(self.my_keypair,'localhost',self.hisport,mylistenport=self.mylistenport)
        msg = self.create_good_drequest()
        s.send(msg)
        time.sleep(5)

        # And connect back to us
        conn, addr = self.myss.accept()
        s2 = BTConnection('',0,conn,mylistenport=self.mylistenport,user_infohash=dialback_infohash)
        s2.read_handshake_medium_rare()
        resp = s2.recv()
        print >> sys.stderr,"test: Me got DIALBACK_REPLY from him, len",len(resp)
        self.assert_(resp[0] == DIALBACK_REPLY)
        self.check_drequest(resp[1:])

    def create_good_drequest(self):
        return str(DIALBACK_REQUEST)

    def check_drequest(self,data):
        s = bdecode(data)
        self.assert_(type(s) == StringType)
        self.assert_(isValidIP(s))
        self.assert_(s == self.myip)

    #
    # Bad DIALBACK_REQUEST
    #    
    def subtest_bad_not_empty(self):
        self._test_bad(self.create_not_empty)

    #
    # Main test code for bad DIALBACK_REQUEST messages
    #
    def _test_bad(self,gen_drequest_func):
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        print >> sys.stderr,"\ntest: ",gen_drequest_func
        msg = gen_drequest_func()
        s.send(msg)
        time.sleep(5)
        # the other side should not like this and close the connection
        resp = s.recv()
        self.assert_(len(resp)==0)
        s.close()

        # However, closing the connection is the specified behaviour, check
        # that he doesn't connect back
        try:
            self.myss.settimeout(10.0)
            print >> sys.stderr,"test: See if peer connects back (would be bad)"
            conn, addr = self.myss.accept()
            s = BTConnection('',0,conn,mylistenport=self.mylistenport,user_infohash=dialback_infohash)
            s.read_handshake_medium_rare()
            resp = s.recv()
            print >> sys.stderr,"test: Got reply back, len",len(resp),"see if expected"
            self.assert_(len(resp) > 0)
            self.assert_(resp[0] != DIALBACK_REPLY)
            print >> sys.stderr,"test: Reply was acceptable",getMessageName(resp[0])
        except socket.timeout:
            self.assert_(True)
            print >> sys.stderr,"test: Good, accept() timed out"

    #
    # Bad message creators
    # 
    def create_not_empty(self):
        return DIALBACK_REQUEST+"bla"


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestDialbackRequest))
    
    return suite

if __name__ == "__main__":
    unittest.main()

