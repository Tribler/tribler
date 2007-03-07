# Written by Jie Yang
# see LICENSE.txt for license information

# Arno, pychecker-ing: the addTarget and getTarget methods of JobQueue are
# no longer there, this code needs to be updated.

import os
import unittest
from tempfile import mkdtemp
from distutils.dir_util import copy_tree, remove_tree
from sets import Set
from traceback import print_exc

from Tribler.BuddyCast.buddycast import DataHandler
from Tribler.__init__ import tribler_init

import hotshot, hotshot.stats
import math
from random import random, shuffle

myid =  147

class TestBuddyCastDataHandler(unittest.TestCase):
    
    def setUp(self):
        # prepare database
        testdbpath = os.path.join('.Tribler', 'bsddb')
        self.homepath = mkdtemp()
        #print "\ntest: create tmp dir", self.homepath
        self.dbpath = os.path.join(self.homepath, 'bsddb')
        copy_tree(testdbpath, self.dbpath)
        
        tribler_init(unicode(self.homepath))
        self.data_handler = DataHandler(db_dir=self.dbpath)
        # self.data_handler.max_num_peers = 100
        # self.data_handler.postInit()
        
    def tearDown(self):
        #del self.data_handler
        #self.data_handler.close()
        remove_tree(self.homepath)
        
    def _test_getAllPeers(self):
        # testing to get a number of recently seen peers
        num_peers = 64    #TODO: remove dir problem, right test
        peers = self.data_handler.getAllPeers(num_peers)
        values = peers.values()
        values.sort()
        oldvls = 0
        for v in values:
            vls = v[0]
            assert vls >= oldvls, (vls, oldvls)
            oldvls = vls
        assert len(peers) == num_peers, (len(peers), num_peers)
        
    def _test_updateMyPreferences(self):
        self.data_handler.updateMyPreferences()
        assert len(self.data_handler.mypreflist)>0, len(self.data_handler.mypreflist)
        
    def _test_updateAllPref(self):
        num_peers = 56
        self.data_handler.getAllPeers(num_peers)
        self.data_handler.updateAllPref()
        #for p in self.data_handler.preferences:
        #    print len(self.data_handler.preferences[p]), `p[30:40]`
        assert len(self.data_handler.preferences) == num_peers, (len(self.data_handler.preferences), num_peers)
        
    def test_updateAllI2ISim(self):
        self.data_handler.getAllPeers()
        self.data_handler.updateAllPref()
        from time import time
        t = time()
        torrents = self.data_handler.updateAllI2ISim(ret=True)
        print "used", time()-t
        print len(torrents), len(self.data_handler.peers)
        for t in torrents:
            print torrents[t]
            break
        #for p in self.data_handler.peers:
        #    print self.data_handler.peers[p]

    def xxtest_profile(self):
        def foo(n = 10000):
            def bar(n):
                for i in range(n):
                    math.pow(i,2)
            def baz(n):
                for i in range(n):
                    math.sqrt(i)
            bar(n)
            baz(n)
        
        self.preload2(136, 30)
        print "profile starts"
        prof = hotshot.Profile("test.prof")
        prof.runcall(self.buddycast.buddycast_core.getBuddyCastData)
        prof.close()
        stats = hotshot.stats.load("test.prof")
        stats.strip_dirs()
        stats.sort_stats('cumulative', 'time', 'calls')
        stats.print_stats(100)
        

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCastDataHandler))
    
    return suite

    
