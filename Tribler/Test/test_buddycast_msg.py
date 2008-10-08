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
from types import StringType, ListType, DictType, IntType, BooleanType
from time import sleep
import tempfile
from M2Crypto import Rand,EC

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
import btconn
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.simpledefs import *

DEBUG=True


class TestBuddyCastMsg(TestAsServer):
    """ 
    Testing BUDDYCAST message of BuddyCast extension V1+2+3
    
    Note this is based on a reverse-engineering of the protocol.
    Source code of the specific Tribler release is authoritative.
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

        # Give Tribler some download history
        print >>sys.stderr,"test: Populating MYPREFERENCES table"
        self.myprefdb = self.session.open_dbhandler(NTFY_MYPREFERENCES)
        data = {'destination_path':'.'}
        infohashes = self.create_good_my_prefs(self,btconn.current_version)
        for i in range(0,len(infohashes)):
            commit = (i == len(infohashes)-1) 
            self.myprefdb.addMyPreference(infohashes[i], data, commit=commit)

        # Give Tribler some peers
        print >>sys.stderr,"test: Populating PEERS table"
        self.peerdb = self.session.open_dbhandler(NTFY_PEERS)
        past = int(time.time())-1000000000
        peers = self.create_good_random_peers(btconn.current_version,num=200)
        
        peers = []
        
        for i in range(0,len(peers)):
            peer = peers[i]
            peer.update({'last_seen':past, 'last_connected':past})
            del peer['connect_time']
            peer['num_torrents'] = peer['nfiles'] 
            del peer['nfiles']
            commit = (i == len(peers)-1)
            self.peerdb.addPeer(peer['permid'], peer, update_dns=True, update_connected=True, commit=commit)


    def tearDown(self):
        """ override TestAsServer """
        TestAsServer.tearDown(self)
        try:
            os.remove(self.superpeerfilename)
        except:
            print_exc()


    def singtest_good_buddycast2(self):
        """ I want a fresh Tribler for this """
        self.subtest_good_buddycast(2)
        
    def singtest_good_buddycast3(self):
        """ I want a fresh Tribler for this """
        self.subtest_good_buddycast(3)
        
    def singtest_good_buddycast4(self):
        """ I want a fresh Tribler for this """
        self.subtest_good_buddycast(4)
        
    def singtest_good_buddycast6(self):
        """ I want a fresh Tribler for this """
        self.subtest_good_buddycast(6)

    def singtest_bad_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        self.subtest_bad_not_bdecodable()
        self.subtest_bad_not_dict1()
        self.subtest_bad_not_dict2()
        self.subtest_bad_empty_dict()
        self.subtest_bad_wrong_dict_keys()
        self.subtest_bad_buddycast_simple()
        self.subtest_bad_taste_buddies()
        self.subtest_bad_random_peers()

    #
    # Good BUDDYCAST
    #
    def subtest_good_buddycast(self,oversion):
        """ 
            test good BUDDYCAST messages
        """
        print >>sys.stderr,"test: good BUDDYCAST",oversion
        s = OLConnection(self.my_keypair,'localhost',self.hisport,myoversion=oversion)
        msg = self.create_good_buddycast_payload(oversion)
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
                    if oversion >= 3:
                        self.check_keep_alive(resp[1:])
                    else:
                        print >> sys.stderr,"test: Tribler sent KEEP_ALIVE, not allowed in olproto ver",oversion
                        self.assert_(False)
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with BUDDYCAST message"
            self.assert_(False)

        self.check_buddycast(resp[1:],oversion)
        time.sleep(10)
        # the other side should not have closed the connection, as
        # this is all valid, so this should not throw an exception:
        s.send('bla')
        s.close()

    def create_good_buddycast_payload(self,oversion):
        d = self.create_good_buddycast(oversion)
        return self.create_payload(d)
        
    def create_good_buddycast(self,oversion):
        self.myprefs = self.create_good_my_prefs(oversion)
        tastebuddies = self.create_good_taste_buddies(oversion)
        randompeers = self.create_good_random_peers(oversion)
        recentcoll = self.create_good_recently_collected_torrents(oversion)
        d = {}
        d['ip'] = '127.0.0.1'
        d['port'] = 481
        d['name'] = 'Bud Spencer'
        d['preferences'] = self.myprefs
        d['taste buddies'] = tastebuddies 
        d['random peers'] = randompeers
        
        if oversion >= 3:
            d['connectable'] = True
        
        if oversion >= 4:
            d['collected torrents'] = recentcoll
        
        if oversion >= 6:
            d['npeers'] = 3904
            d['nfiles'] = 4027
            d['ndls'] = 4553

        #print >>sys.stderr,"test: Sending",`d`
        
        return d

    def create_good_my_prefs(self,oversion,num=50):
        p = []
        for i in range(0,num):
            infohash = chr(ord('a')+i) * 20
            p.append(infohash)
        return p

    create_good_recently_collected_torrents = create_good_my_prefs

    def create_good_taste_buddies(self,oversion):
        tbs = []
        for i in range(0,10):
           tb = self.create_good_peer(i,oversion)
           tbs.append(tb)
        return tbs 

    def create_good_random_peers(self,oversion,num=10):
        tbs = []
        for i in range(0,num):
           tb = self.create_good_peer(i,oversion)
           tbs.append(tb)
        return tbs 
        
    def create_good_peer(self,id,oversion):
        d = {}
        d['permid'] = 'peer '+str(id)
        d['ip'] = '192.168.0.'+str(id)
        d['port'] = 7762+id
        d['connect_time'] = int(time.time())

        if oversion <= 2:
            d['age'] = 0
            
        if oversion <= 3:
            d['preferences'] = self.create_good_my_prefs(oversion,num=10)
        else:
            d['similarity'] = 1

        if oversion >= 6:
            d['oversion'] = btconn.current_version
            d['nfiles'] = 100+id
        
        return d

    def create_payload(self,r):
        return BUDDYCAST+bencode(r)

    def check_buddycast(self,data,oversion):
        d = bdecode(data)
        
        print >>sys.stderr,"test: Got BUDDYCAST",d.keys()
        #print >>sys.stderr,"test: Got CONTENT",`d`
        
        self.assert_(type(d) == DictType)
        self.assert_('ip' in d)
        self.assert_(type(d['ip']) == StringType)
        self.assert_('port' in d)
        self.assert_(type(d['port']) == IntType)
        self.assert_('name' in d)
        self.assert_(type(d['name']) == StringType)
        self.assert_('preferences' in d)
        self.check_preferences(d['preferences'],oversion)
        self.assert_('taste buddies' in d)
        self.check_taste_buddies(d['taste buddies'],oversion)
        self.assert_('random peers' in d)
        self.check_random_peers(d['random peers'],oversion
                                )
        if oversion >= 3:
            self.assert_('connectable' in d)
            #print >>sys.stderr,"CONNECTABLE TYPE",type(d['connectable'])
            self.assert_(type(d['connectable']) == IntType)
        if oversion >= 4:
            self.assert_('collected torrents' in d)
            self.check_collected_torrents(d['collected torrents'],oversion)
        if oversion >= 6:
            self.assert_('npeers' in d)
            self.assert_(type(d['npeers']) == IntType)
            self.assert_('nfiles' in d)
            self.assert_(type(d['nfiles']) == IntType)
            self.assert_('ndls' in d)
            self.assert_(type(d['ndls']) == IntType)

    def check_preferences(self,p,oversion):
        self.assert_(type(p) == ListType)
        self.assert_(len(p) <= 50)
        for infohash in p:
            self.check_infohash(infohash)
            
    check_collected_torrents = check_preferences
            
    def check_infohash(self,infohash):
        self.assert_(type(infohash) == StringType)
        self.assert_(len(infohash) == 20)

    def check_taste_buddies(self,peerlist,oversion):
        return self.check_peer_list(peerlist,True,oversion)
    
    def check_random_peers(self,peerlist,oversion):
        return self.check_peer_list(peerlist,False,oversion)

    def check_peer_list(self,peerlist,taste,oversion):
        self.assert_(type(peerlist) == ListType)
        for p in peerlist:
            self.check_peer(p,taste,oversion)

    def check_peer(self,d,taste,oversion):
        self.assert_(type(d) == DictType)
        self.assert_('permid' in d)
        self.assert_(type(d['permid']) == StringType)
        self.assert_('ip' in d)
        self.assert_(type(d['ip']) == StringType)
        self.assert_('port' in d)
        self.assert_(type(d['port']) == IntType)
        self.assert_('connect_time' in d)
        self.assert_(type(d['connect_time']) == IntType)

        if oversion <= 3 and taste:
            self.assert_('preferences' in d)
            self.check_preferences(d['preferences'],oversion)
        
        if oversion >= 4:
            self.assert_('similarity' in d)
            self.assert_(type(d['similarity']) == IntType)

        if oversion >= 6:
            if 'oversion' in d:
                # Jie made this optional, only if peer has enough collected files
                # its record will contain these fields
                self.assert_(type(d['oversion']) == IntType)
                self.assert_('nfiles' in d)
                self.assert_(type(d['nfiles']) == IntType)
            

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

    def subtest_bad_buddycast_simple(self):
        methods = [
            self.make_bad_ip,
            self.make_bad_port,
            self.make_bad_name,
            self.make_bad_preferences,
            self.make_bad_collected_torrents]
        for method in methods:
            print >> sys.stderr,"\ntest: ",method,
            self._test_bad(method)
        
        
    def make_bad_ip(self):
        d = self.create_good_buddycast(btconn.current_version)
        d['ip'] = 481
        return self.create_payload(d)

    def make_bad_port(self):
        d = self.create_good_buddycast(btconn.current_version)
        d['port'] = '127.0.0.1'
        return self.create_payload(d)

    def make_bad_name(self):
        d = self.create_good_buddycast(btconn.current_version)
        d['name'] = 481
        return self.create_payload(d)
    
    def make_bad_preferences(self):
        d = self.create_good_buddycast(btconn.current_version)
        d['preferences'] = 481
        return self.create_payload(d)

    def make_bad_collected_torrents(self):
        d = self.create_good_buddycast(btconn.current_version)
        d['collected torrents'] = 481
        return self.create_payload(d)

        
    def subtest_bad_taste_buddies(self):
        methods = [
            self.make_bad_tb_not_list,
            self.make_bad_tb_list_not_dictelems,
            self.make_bad_tb_list_bad_peer]
        for method in methods:
            d = self.create_good_buddycast(btconn.current_version)
            d['taste buddies'] = method()
            func = lambda:self.create_payload(d)
            
            print >> sys.stderr,"\ntest: ",method,
            self._test_bad(func)

    def make_bad_tb_not_list(self):
        tbs = 481
        return tbs
        
    def make_bad_tb_list_not_dictelems(self):
        tbs = []
        for i in range(0,50):
            tbs.append(i)
        return tbs
        
    def make_bad_tb_list_bad_peer(self):
        tbs = []
        for i in range(0,50):
            tbs.append(self.make_bad_peer())
        return tbs

    def make_bad_peer(self):
        d = {}
        d['permid'] = 'peer 481'
        # Error is too little fields. 
        # TODO: test all possible bad peers
        
        return d


    def subtest_bad_random_peers(self):
        methods = [
            self.make_bad_ip,
            self.make_bad_port,
            self.make_bad_name,
            self.make_bad_preferences,
            self.make_bad_collected_torrents]
        for method in methods:
            d = self.create_good_buddycast(btconn.current_version)
            d['taste buddies'] = method()
            func = lambda:self.create_payload(d)
            
            print >> sys.stderr,"\ntest: ",method,
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

def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_buddycast_msg.py <method name>"
    else:
        suite.addTest(TestBuddyCastMsg(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
