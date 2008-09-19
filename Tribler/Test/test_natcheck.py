# Written by Arno Bakker, Michel Meulpolder
# see LICENSE.txt for license information

import socket
import unittest
import os
import sys
import time
from sha import sha
from random import randint,shuffle
from traceback import print_exc
from types import StringType, IntType, ListType
from threading import Thread
from M2Crypto import Rand,EC

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler
from Tribler.Core.CacheDB.SqliteCacheDBHandler import SuperPeerDBHandler


DEBUG=True

class TestNatCheck(TestAsServer):
    """ 
    Testing SOCIAL_OVERLAP message of Social Network extension V1
    """
    
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        Rand.load_file('randpool.dat', -1)

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        # Enable buddycast
        self.config.set_buddycast(True)
        self.config.set_start_recommender(True)
        self.config.set_bartercast(True)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())        
        self.myhash = sha(self.mypermid).digest()

    def tearDown(self):
        """ override TestAsServer """
        TestAsServer.tearDown(self)
        try:
            os.remove('randpool.dat')
        except:
            pass

    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        if DEBUG: print >> sys.stderr,  "Creating good nat check..."
        self.subtest_bad_do_nat_check()
        self.subtest_good_do_nat_check()
        #self.subtest_good_nat_check_reply()

        

    def subtest_bad_do_nat_check(self):
        """
        Send a DO_NAT_CHECK message to the Tribler instance. No reply
        should be send because the OLConnection is NOT a superpeer and
        therefore not allowed to request a nat check.
        """
        print >>sys.stderr, "-"*80, "\ntest: bad DO_NAT_CHECK"

        # make sure that the OLConnection is NOT in the superpeer_db
        superpeer_db = SuperPeerDBHandler.getInstance()
        self.assert_(not self.mypermid in superpeer_db.getSuperPeers())

        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_do_nat_check()

        # a KEEP_ALIVE message will eventually be send, therefore,
        # this call will not block.
        s.send(msg)

        resp = s.recv()
        if DEBUG: print >> sys.stderr, "responce type is", message_map[resp[0]]
        self.assert_(resp[0] != NAT_CHECK_REPLY)

        time.sleep(5)
        s.close()

    def subtest_good_do_nat_check(self):
        """
        Send a DO_NAT_CHECK message to the Tribler instance. A reply
        containing a nat type should be returned.
        """
        print >>sys.stderr, "-"*80, "\ntest: good DO_NAT_CHECK"

        # make sure that the OLConnection IS in the superpeer_db
        superpeer_db = SuperPeerDBHandler.getInstance()
        superpeer_db.addExternalSuperPeer({"permid":self.mypermid})
        self.assert_(self.mypermid in superpeer_db.getSuperPeers())

        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_do_nat_check()
        s.send(msg)

        # It will take a LONG time before everything is discovered
        # (the NAT firewall timeout will also be measured which
        # probably takes a long time, currently at 10 minutes...)
        #
        # We must ignore KEEP_ALIVE messages that are received in the
        # mean-time. This also means that if the code fails, this test
        # will run forever...
        begin = time.time()
        print >>sys.stderr, "Waiting for responce. Will take a long time (around 1200 seconds)."
        while True:
            resp = s.recv()
            print >>sys.stderr, "Waiting for responce. Will take a long time (around 1200 seconds). Waited %d seconds so far" % (time.time() - begin)
            if DEBUG: print >> sys.stderr, "responce type is", message_map[resp[0]]
            if resp[0] == NAT_CHECK_REPLY:
                break
            
        self.assert_(resp[0] == NAT_CHECK_REPLY)
        self.check_nat_check_reply(resp[1:])

        time.sleep(5)
        s.close()


    def subtest_good_nat_check_reply(self):
        """ 
            test good NAT_CHECK_REPLY messages
        """
        if DEBUG: print >> sys.stderr, "test: good NAT_CHECK_REPLY"
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_nat_check_reply()
        if DEBUG: print >> sys.stderr, "nat_check_reply: ", msg
        s.send(msg)
        time.sleep(10)
        s.close()


    def create_good_do_nat_check(self):
        if DEBUG: print >> sys.stderr,  "Creating good do_nat_check message..."
        return DO_NAT_CHECK


    def create_good_nat_check_reply(self):

        if DEBUG: print >> sys.stderr,  "Creating good nat_check_reply message..."

        ncr_data = ['Port Restricted Cone NAT', 3, 90, '123.123.123.123', 1234, '168.192.0.2', 5678]
        
        return NAT_CHECK_REPLY+bencode(ncr_data)


    def check_nat_check_reply(self,data):

        d = bdecode(data)

        self.assert_(type(d) == ListType)
        self.assert_(len(d) == 7)
        self.assert_(type(d[0]) == StringType)
        self.assert_(type(d[1]) == IntType)
        self.assert_(type(d[2]) == IntType)
        self.assert_(type(d[3]) == StringType)
        self.assert_(type(d[4]) == IntType)
        self.assert_(type(d[5]) == StringType)
        self.assert_(type(d[6]) == IntType)
        
        if DEBUG: print >> sys.stderr,  "Received data:"
        if DEBUG: print >> sys.stderr,  d



    # Bad overlap
    #    
    def subtest_bad_not_bdecodable(self):
        self._test_bad(self.create_not_bdecodable)

    def _test_bad(self,gen_soverlap_func):
        print >>sys.stderr,"test: bad BARTERCAST",gen_soverlap_func
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = gen_soverlap_func()
        s.send(msg)
        time.sleep(5)
        # the other side should not like this and close the connection
        self.assert_(len(s.recv())==0)
        s.close()

    def create_not_bdecodable(self):
        return BARTERCAST+"bla"

    def create_not_dict1(self):
        bartercast = 481
        return self.create_payload(bartercast)

    def create_not_dict2(self):
        bartercast = []
        return self.create_payload(bartercast)

    def create_empty_dict(self):
        bartercast = {}
        return self.create_payload(bartercast)

    def create_wrong_dict_keys(self):
        bartercast = {}
        bartercast['data'] = {'permid1': {}}
        return self.create_payload(bartercast)




def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBarterCast))
    
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

