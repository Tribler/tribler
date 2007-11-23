# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
import socket
import tempfile
from time import sleep
from types import StringType, ListType, DictType, IntType

from M2Crypto import EC
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import QUERY, QUERY_REPLY, getMessageName

from btconn import BTConnection
from olconn import OLConnection
from Tribler.Test_as_server import TestAsServer

DEBUG=True

TEST_QUERY = 'hallo'
TEST_QUERY_ONWIRE = 'SIMPLE '+TEST_QUERY

class TestQueryReplyActive(TestAsServer):

    """  
    Testing QUERY_REPLY message of Query extension V1 

    This test checks how the Tribler code responds to good and bad 
    QUERY_REPLY messages. I.e. the Tribler client initiates
    the dialback by connecting to us and sending a QUERY and we
    reply with good and bad messages.

    This test allows authoritative answers from superpeers.

    WARNING: Each of the test_ methods should be tested by running the TestCase 
    in a separate Python interpreter to prevent problems with our singleton 
    classes, e.g. SuperPeerDB, etc.
    """

    def setUpPreSession(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: Pre Tribler Init"
        TestAsServer.setUpPreSession(self)
        print >> sys.stderr,"test: Pre Tribler Init: config_path",self.config_path
        # Enable social networking
        self.config['rquery'] = 1


    def pretest(self):
        # 1. First connect to Tribler
        self.openconn = OLConnection(self.my_keypair,'localhost',self.hisport)
        sleep(3)
        
        # 2. Make Tribler send query
        self.lm.overlay_apps.rquery_handler.sendQuery(TEST_QUERY,10)


    #
    # Good QUERY, builds on TestQueryReply code
    #    
    def singtest_good_qreply(self):
        self.pretest()
        self._test_qreply(self.create_good_qreply,True)

    #
    # Bad QUERY, builds on TestQueryReply code
    #    
    def singtest_bad_not_bdecodable(self):
        self.pretest()
        self._test_qreply(self.create_not_bdecodable,False)


    ### TODO: send different valid answers so consensus not reached

    #
    # Main test code
    #
    def _test_qreply(self,gen_qreply,good):
        print >> sys.stderr,"test: waiting for reply"
        s = self.openconn

        msg = s.recv()
        self.assert_(len(msg) > 0)
        print >> sys.stderr,"test: Received overlay message",getMessageName(msg[0])
        self.assert_(msg[0] == QUERY)
        id = self.check_rquery(msg[1:])
        
        resp = gen_qreply(id)
        print >> sys.stderr,"test: sending QUERY_REPLY"
        s.send(resp)
        if good:
            time.sleep(10)
            # the other side should not have closed the connection, as
            # this is all valid, so this should not throw an exception:
            s.send('bla')
            s.close()
        else:
            # the other side should not like this and close the connection
            self.assert_(len(s.recv())==0)
            s.close()


    def create_good_qreply(self,id):
        r = {}
        r['content_name'] = 'Hallo S22E44'
        r['length'] = 481
        r['leecher'] = 11
        r['seeder'] = 22
        r['category'] = 'Video'
        
        d2 = {}
        ih = 'i'*20
        d2[ih] = r
        
        d = {}
        d['id'] = id
        d['a'] = d2
        
        b = bencode(d)
        return QUERY_REPLY+b

    def create_not_bdecodable(self,id):
        return QUERY_REPLY+"bla"

    def check_rquery(self,data):
        d = bdecode(data)
        self.assert_(type(d) == DictType)
        self.assert_(d.has_key('q'))
        q = d['q']
        self.assert_(type(q) == StringType)
        self.assert_(d.has_key('id'))
        id = d['id']
        self.assert_(type(id) == StringType)

        self.assert_(q == TEST_QUERY_ONWIRE)
        return d['id']


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. SuperPeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_qra.py <method name>"
    else:
        suite.addTest(TestQueryReplyActive(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])
    
if __name__ == "__main__":
    main()
