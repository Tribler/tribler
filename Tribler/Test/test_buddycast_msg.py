# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
import socket
from sha import sha
from random import randint,shuffle
from traceback import print_exc
from types import StringType, ListType, DictType
from time import sleep
import tempfile
from M2Crypto import Rand,EC

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
import btconn
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

DEBUG=True


class TestBuddyCastMsg(TestAsServer):
    """ 
    Testing BUDDYCAST message of BuddyCast extension V3
    """
    
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        # BuddyCast
        self.config.set_buddycast(True)
        self.config.set_start_recommender(True)
        
        fd,self.superpeerfilename = tempfile.mkstemp()
        os.write(fd,'')
        os.close(fd)
        self.config.set_superpeer_file(self.superpeerfilename)

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
            os.remove(self.superpeerfilename)
        except:
            print_exc()

    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        # 1. test good BUDDYCAST
        self.subtest_good_buddycast()

        """
        # 2. test various bad BUDDYCAST messages
        self.subtest_bad_not_bdecodable()
        self.subtest_bad_not_dict1()
        self.subtest_bad_not_dict2()
        self.subtest_bad_empty_dict()
        self.subtest_bad_wrong_dict_keys()

        self.subtest_bad_persinfo()
        """

    #
    # Good BUDDYCAST
    #
    def subtest_good_buddycast(self):
        """ 
            test good BUDDYCAST messages
        """
        print >>sys.stderr,"test: good BUDDYCAST"
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_buddycast()
        s.send(msg)

        s.b.s.settimeout(60.0)
        try:
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >>sys.stderr,"test: good BUDDYCAST: Got reply",getMessageName(resp[0])
                if resp[0] == BUDDYCAST:
                    break
                elif resp[0] == GET_METADATA:
                    self.check_get_metadata(resp[1:])
                elif resp[0] == KEEP_ALIVE:
                    self.check_keep_alive(resp[1:])
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with BUDDYCAST message"
            self.assert_(False)

        self.check_buddycast(resp[1:])
        time.sleep(10)
        # the other side should not have closed the connection, as
        # this is all valid, so this should not throw an exception:
        s.send('bla')
        s.close()

    def create_good_buddycast(self):
        
        self.myprefs = self.create_good_my_prefs()
        tastebuddies = self.create_good_taste_buddies()
        randompeers = self.create_good_random_peers()
        recentcoll = self.create_good_recently_collected_torrents()
        
        d = {}
        d['ip'] = '127.0.0.1'
        d['port'] = 481
        d['name'] = 'Bud Spencer'
        d['preferences'] = self.myprefs
        d['taste buddies'] = tastebuddies 
        d['random peers'] = randompeers
        
        # selversion >= OLPROTO_VER_THIRD:
        d['connectable'] = True
        
        # selversion >= OLPROTO_VER_FOURTH:
        d['collected torrents'] = recentcoll
        
        # selversion >= OLPROTO_VER_SIXTH:
        d['npeers'] = 3904
        d['nfiles'] = 4027
        d['ndls'] = 4553
        
        return self.create_payload(d)

    def create_good_my_prefs(self):
        p = []
        for i in range(0,50):
            infohash = chr(ord('a')+i) * 20
            p.append(infohash)
        return p

    create_good_recently_collected_torrents = create_good_my_prefs

    def create_good_taste_buddies(self):
        tbs = []
        for i in range(0,10):
           tb = self.create_good_peer(i)
           tbs.append(tb)
        return tbs 

    def create_good_random_peers(self):
        tbs = []
        for i in range(0,10):
           tb = self.create_good_peer(i)
           tbs.append(tb)
        return tbs 
        
    def create_good_peer(self,id):
        d = {}
        d['permid'] = 'peer '+str(id)
        d['ip'] = '192.168.0.'+str(id)
        d['port'] = 7762+id
        d['oversion'] = btconn.current_version
        d['nfiles'] = 100+id
        d['connect_time'] = int(time.time())
        d['similarity'] = 1
        return d

    def create_payload(self,r):
        return BUDDYCAST+bencode(r)

    def check_buddycast(self,data):
        d = bdecode(data)
        
        print >>sys.stderr,"test: Got BUDDYCAST",d.keys()
        print >>sys.stderr,"test: Got CONTENT",`d`
        return
        
        self.assert_(type(d) == DictType)
        self.assert_('ip' in d)
        self.assert_(type(d['ip']) == StringType)
        self.assert_('port' in d)
        self.assert_(type(d['port']) == IntType)
        self.assert_('name' in d)
        self.assert_(type(d['name']) == StringType)
        self.assert_('preferences' in d)
        self.check_preferences(d['preferences'])
        self.assert_('taste buddies' in d)
        self.check_taste_buddies(d['taste buddies'])
        self.assert_('random peers' in d)
        self.check_random_peers(d['random peers'])
        # selversion >= OLPROTO_VER_THIRD:
        self.assert_('connectable' in d)
        self.assert_(type(d['connectable']) == BooleanType)
        # selversion >= OLPROTO_VER_FOURTH:
        self.assert_('collected torrents' in d)
        self.check_collected_torrents(d['collected torrents'])
        # selversion >= OLPROTO_VER_SIXTH:
        self.assert_('npeers' in d)
        self.assert_(type(d['npeers']) == IntType)
        self.assert_('nfiles' in d)
        self.assert_(type(d['nfiles']) == IntType)
        self.assert_('ndls' in d)
        self.assert_(type(d['ndls']) == IntType)

    def check_preferences(self,p):
        self.assert_(type(p) == ListType)
        self.assert_(len(p) <= 50)
        for infohash in p:
            self.check_infohash(infohash)
            
    def check_infohash(self,infohash):
        self.assert_(type(infohash) == StringType)
        self.assert_(len(infohash) == 20)

    def check_taste_buddies(self,peerlist):
        return self.check_peer_list(peerlist)
    
    def check_random_peers(self,peerlist):
        return self.check_peer_list(peerlist)

    def check_peer_list(self,peerlist):
        self.assert_(type(peerlist) == ListType)
        for p in peerlist:
            self.check_peer(p)

    def check_peer(self,d):
        self.assert_(type(d) == DictType)
        self.assert_('permid' in d)
        self.assert_(type(d['permid']) == StringType)
        self.assert_('ip' in d)
        self.assert_(type(d['ip']) == StringType)
        self.assert_('port' in d)
        self.assert_(type(d['port']) == IntType)
        self.assert_('oversion' in d)
        self.assert_(type(d['oversion']) == IntType)
        self.assert_('nfiles' in d)
        self.assert_(type(d['nfiles']) == IntType)
        self.assert_('connect_time' in d)
        self.assert_(type(d['connect_time']) == IntType)
        self.assert_('similarity' in d)
        self.assert_(type(d['similarity']) == IntType)


    def check_get_metadata(self,data):
        infohash = bdecode(data)
        self.check_infohash(infohash)
        
        # Extra check: he can only ask us for metadata for an infohash we
        # gave him.
        self.assert_(infohash in self.myprefs)        

    def check_keep_alive(self,data):
        self.assert_(len(data) == 0)

    #
    # Bad buddycast
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

    #
    # Bad 'persinfo' 
    #
    def subtest_bad_persinfo(self):
        """ Cut a corner """
        methods = [
            self.make_persinfo_not_dict1,
            self.make_persinfo_not_dict2,
            self.make_persinfo_empty_dict,
            self.make_persinfo_wrong_dict_keys,
            self.make_persinfo_name_not_str,
            self.make_persinfo_icontype_not_str,
            self.make_persinfo_icontype_noslash,
            self.make_persinfo_icondata_not_str,
            self.make_persinfo_icondata_too_big ]
        for method in methods:
            # Hmmm... let's get dirty
            print >> sys.stderr,"\ntest: ",method,
            func = lambda: self.create_bad_persinfo(method)
            self._test_bad(func)

    def _test_bad(self,gen_buddycast_func):
        print >>sys.stderr,"test: bad BUDDYCAST",gen_buddycast_func
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = gen_buddycast_func()
        s.send(msg)
        time.sleep(5)
        # the other side should not like this and close the connection
        self.assert_(len(s.recv())==0)
        s.close()

    def create_not_bdecodable(self):
        return BUDDYCAST+"bla"

    def create_not_dict1(self):
        buddycast = 481
        return self.create_payload(buddycast)

    def create_not_dict2(self):
        buddycast = []
        return self.create_payload(buddycast)

    def create_empty_dict(self):
        buddycast = {}
        return self.create_payload(buddycast)

    def create_wrong_dict_keys(self):
        buddycast = {}
        buddycast['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        buddycast['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return self.create_payload(buddycast)


    #
    # Bad persinfo
    #
    def create_bad_persinfo(self,gen_persinfo_func):
        buddycast = {}
        pi = gen_persinfo_func()
        buddycast['persinfo'] = pi
        return self.create_payload(buddycast)

    def make_persinfo_not_dict1(self):
        return 481

    def make_persinfo_not_dict2(self):
        return []

    def make_persinfo_empty_dict(self):
        return {}

    def make_persinfo_wrong_dict_keys(self):
        pi = {}
        pi['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        pi['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return pi

    def make_persinfo_name_not_str(self):
        [sig,pi] = self.create_good_persinfo()
        pi['name'] = 481
        return pi

    def make_persinfo_icontype_not_str(self):
        [sig,pi] = self.create_good_persinfo()
        pi['icontype'] = 481
        return pi

    def make_persinfo_icontype_noslash(self):
        [sig,pi] = self.create_good_persinfo()
        pi['icontype'] = 'image#jpeg'
        return pi

    def make_persinfo_icondata_not_str(self):
        [sig,pi] = self.create_good_persinfo()
        pi['icondata'] = 481
        return pi

    def make_persinfo_icondata_too_big(self):
        [sig,pi] = self.create_good_persinfo()
        pi['icondata'] = "".zfill(ICON_MAX_SIZE+100)
        return pi

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCastMsg))
    
    return suite


if __name__ == "__main__":
    unittest.main()

