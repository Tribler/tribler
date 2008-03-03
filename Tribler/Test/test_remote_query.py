# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
from sha import sha
from random import randint,shuffle
from traceback import print_exc
from types import StringType, ListType, DictType, IntType
from threading import Thread
from time import sleep
from M2Crypto import Rand,EC

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from Tribler.Core.API import *
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *


DEBUG=True


class TestRemoteQuery(TestAsServer):
    """ 
    Testing QUERY message of Social Network extension V1
    """
    
    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        # Enable remote query
        self.config.set_remote_query(True)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        #self.mypermid = str(self.my_keypair.pub().get_der())
        #self.hispermid = str(self.his_keypair.pub().get_der())
        
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        
        # Add two torrents that will match our query and one that shouldn't
        torrent = self.get_default_torrent('Hallo S01E10')
        ih = 'b' * 20
        self.torrent_db.addTorrent(ih,torrent)
        
        torrent = self.get_default_torrent('Hallo S02E01')
        ih = 'c' * 20
        self.torrent_db.addTorrent(ih,torrent)

        torrent = self.get_default_torrent('Halo Demo')
        ih = 'd' * 20
        self.torrent_db.addTorrent(ih,torrent)

    def tearDown(self):
        TestAsServer.tearDown()
        self.session.close_dbhandler(self.torrent_db)
      

    def get_default_torrent(self,title):
        torrent = {}
        torrent['torrent_name'] = title
        info = {}
        info['name'] = title
        info['creation date'] = int(time.time())
        info['num_files'] = 0
        info['length'] = 0
        info['announce'] = 'http://localhost:0/announce'
        info['announce-list'] = []
        torrent['info'] = info
        torrent['status'] = 'good'
        return torrent

    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        # 1. test good QUERY
        self.subtest_good_rquery()

        # 2. test various bad QUERY messages
        self.subtest_bad_not_bdecodable()
        self.subtest_bad_not_dict1()
        self.subtest_bad_not_dict2()
        self.subtest_bad_empty_dict()
        self.subtest_bad_wrong_dict_keys()

        self.subtest_bad_q_not_list()
        self.subtest_bad_id_not_str()

    #
    # Good QUERY
    #
    def subtest_good_rquery(self):
        """ 
            test good QUERY messages
        """
        print >>sys.stderr,"test: good QUERY"
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_rquery()
        s.send(msg)
        resp = s.recv()
        if len(resp) > 0:
            print >>sys.stderr,"test: good QUERY: got",getMessageName(resp[0])
        self.assert_(resp[0] == QUERY_REPLY)
        self.check_rquery_reply(resp[1:])
        time.sleep(10)
        # the other side should not have closed the connection, as
        # this is all valid, so this should not throw an exception:
        s.send('bla')
        s.close()

    def create_good_rquery(self):
        d = {}
        d['q'] = 'SIMPLE hallo'
        d['id'] = 'a' * 20
        return self.create_payload(d)

    def create_payload(self,r):
        return QUERY+bencode(r)

    def check_rquery_reply(self,data):
        d = bdecode(data)
        self.assert_(type(d) == DictType)
        self.assert_(d.has_key('a'))
        self.check_adict(d['a'])
        self.assert_(d.has_key('id'))
        id = d['id']
        self.assert_(type(id) == StringType)

        k = d['a'].keys()
        self.assert_(len(k) == 2)
        var1 = k[0] == ('b'*20) and k[1] == ('c'*20)
        var2 = k[0] == ('c'*20) and k[1] == ('b'*20)
        self.assert_(var1 or var2)

    def check_adict(self,d):
        self.assert_(type(d) == DictType)
        for key,value in d.iteritems():
            self.assert_(type(key) == StringType)
            self.assert_(len(key) == 20)
            self.check_rdict(value)
    
    def check_rdict(self,d):
        self.assert_(type(d) == DictType)
        self.assert_('content_name' in d)
        self.assert_(type(d['content_name']) == StringType)
        self.assert_('length' in d)
        self.assert_(type(d['length']) == IntType)
        self.assert_('leecher' in d)
        self.assert_(type(d['leecher']) == IntType)
        self.assert_('seeder' in d)
        self.assert_(type(d['seeder']) == IntType)


    # Bad rquery
    #    
    def subtest_bad_not_bdecodable(self):
        self._test_bad(self.create_not_bdecodable)

    def subtest_bad_not_dict1(self):
        self._test_bad(self.create_not_dict1)

    def subtest_bad_not_dict2(self):
        self._test_bad(self.create_not_dict2)

    def subtest_bad_empty_dict(self):
        self._test_bad(self.create_empty_dict)

    def subtest_bad_wrong_dict_keys(self):
        self._test_bad(self.create_wrong_dict_keys)

    def subtest_bad_q_not_list(self):
        self._test_bad(self.create_bad_q_not_list)

    def subtest_bad_id_not_str(self):
        self._test_bad(self.create_bad_id_not_str)


    def _test_bad(self,gen_rquery_func):
        print >>sys.stderr,"test: bad QUERY",gen_rquery_func
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = gen_rquery_func()
        s.send(msg)
        time.sleep(5)
        # the other side should not like this and close the connection
        self.assert_(len(s.recv())==0)
        s.close()

    def create_not_bdecodable(self):
        return QUERY+"bla"

    def create_not_dict1(self):
        rquery = 481
        return self.create_payload(rquery)

    def create_not_dict2(self):
        rquery = []
        return self.create_payload(rquery)

    def create_empty_dict(self):
        rquery = {}
        return self.create_payload(rquery)

    def create_wrong_dict_keys(self):
        rquery = {}
        rquery['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        rquery['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return self.create_payload(rquery)


    #
    # Bad q
    #
    def create_bad_q_not_list(self):
        rquery = {}
        rquery['q'] = 481
        rquery['id'] = 'a' * 20
        return self.create_payload(rquery)


    #
    # Bad id
    #
    def create_bad_id_not_str(self):
        rquery = {}
        rquery['q'] = ['hallo']
        rquery['id'] = 481
        return self.create_payload(rquery)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestRemoteQuery))
    
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

