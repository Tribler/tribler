import os
import tempfile
import unittest
from sets import Set
from random import shuffle

from Tribler.BuddyCast.similarity import *

pref1 = [1,3,6,8,9,0,2,7,5,4]
pref2 = [1,2,3,4,5,6,7,8,9,0]
pref3 = [1,3,5,7,9, 11, 13]
pref4 = [11, 24, 25, 64]
pref5 = []
pref6 = [1, 66, 77, 88, 99, 100, 11]
        
class TestSim(unittest.TestCase):
    
    def setUp(self):
        pass
        
    def tearDown(self):
        pass
        
    def test_similarity(self):
        
        assert cooccurrence(pref1[:], pref2[:]) == 10 and P2PSim(pref1[:], pref2[:]) == 1000, \
              (cooccurrence(pref1[:], pref2[:]), P2PSim(pref1[:], pref2[:]))
        assert cooccurrence(pref1[:], pref3[:]) == 5  and P2PSim(pref1[:], pref3[:]) == 597
        assert cooccurrence(pref1[:], pref4[:]) == 0  and P2PSim(pref1[:], pref4[:]) == 0
        assert cooccurrence(pref1[:], pref5[:]) == 0  and P2PSim(pref1[:], pref5[:]) == 0
        assert cooccurrence(pref1[:], pref6[:]) == 1  and P2PSim(pref1[:], pref6[:]) == 119

    def test_selectByProbability(self):
        #pref = pref1
        #pref = range(100)
        pref = range(10)
        shuffle(pref)
        print pref
        stat = [0] * len(pref)
        for j in xrange(200000):
            x = selectByProbability(pref[:], 1, smooth=2)
            for i in x:
                stat[i] += 1
        base = min(stat)
        if base == 0:
            x = stat[:]
            x.sort()
            for y in x:
                if y > 0:
                    base = y
                    break
        for i in xrange(len(pref)):
            stat[i] = 1.0*stat[i]/base
            print "%.2f"%stat[i]
            
    def xxtest_selectByProbability2(self):
        pref = range(10)
        shuffle(pref)
        stat = {}
        for p in pref:
            k = 'peer'+str(p)
            stat[k] = 0
        for j in xrange(100000):
            v = []
            for p in pref:
                k = 'peer'+str(p)
                v.append(k)
            x = selectByProbability(pref[:], 1, smooth=0)
            for i in x:
                stat[i] += 1
        min = 10**10
        for k in stat:
            if stat[k] > 0 and stat[k] < min:
                min = stat[k]
        for k in stat:
            stat[k] = 1.0*stat[k] / min
            print k, "%.2f"%stat[k]
        
def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSim))
    
    return suite
