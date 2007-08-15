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
from M2Crypto import Rand,EC

from test_as_server import TestAsServer
from olconn import OLConnection
from BitTornado.bencode import bencode,bdecode
from BitTornado.BT1.MessageID import *

from Tribler.Dialogs.MugshotManager import MugshotManager,ICON_MAX_SIZE

from Tribler.CacheDB.CacheDBHandler import BarterCastDBHandler

DEBUG=True


class TestBarterCast(TestAsServer):
    """ 
    Testing SOCIAL_OVERLAP message of Social Network extension V1
    """
    
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        Rand.load_file('randpool.dat', -1)

    def setUpPreTriblerInit(self):
        """ override TestAsServer """
        TestAsServer.setUpPreTriblerInit(self)
        # Enable buddycast
        self.config['buddycast'] = 1
        self.config['start_recommender'] = 1

    def setUpPreLaunchMany(self):
        """ override TestAsServer """
        TestAsServer.setUpPreLaunchMany(self)

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
        # 1. test good SOCIAL_OVERLAP
        self.subtest_good_bartercast()


        # 2. test various bad SOCIAL_OVERLAP messages
        self.subtest_bad_not_bdecodable()
        self.subtest_bad_not_dict1()
        self.subtest_bad_not_dict2()
        self.subtest_bad_empty_dict()
        self.subtest_bad_wrong_dict_keys()

        

    #
    # Good SOCIAL_OVERLAP
    #
    def subtest_good_bartercast(self):
        """ 
            test good BARTERCAST messages
        """
        print >>sys.stderr,"test: good BARTERCAST"
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_bartercast()
        s.send(msg)
        resp = s.recv()
        self.assert_(resp[0] == BARTERCAST)
        self.check_bartercast(resp[1:])
        time.sleep(10)
        # the other side should not have closed the connection, as
        # this is all valid, so this should not throw an exception:
        s.send('bla')
        s.close()

    def create_good_bartercast(self):

        print "Creating good bartercast message..."

        top_peers = ["permid1", "permid2"]
        data = {}
        
        for permid in top_peers:

            data_to = 100
            data_from = 200
            data[permid] = {'u': data_to, 'd': data_from}
        
        bartercast_data = {'data': data}

        print "Bartercast_data: ", bartercast_data
        
        return self.create_payload(bartercast_data)


    def create_payload(self,r):
        return BARTERCAST+bencode(r)

    def check_bartercast(self,data):
        d = bdecode(data)
        
        print "Received data:"
        print d
        
        self.assert_(type(d) == DictType)
        self.assert_(d.has_key('data'))
        self.check_bartercast_data(d['data'])


    def check_bartercast_data(self,d):
        self.assert_(type(d) == DictType)
        print "test: bartercast_data: keys is",d.keys()



    # Bad soverlap
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

