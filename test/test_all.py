""" Run all test cases """

import sys
import os
import unittest

import hotshot, hotshot.stats, test.test_all
import math
from test.test_all import *

    
verbose = 0
if 'verbose' in sys.argv:
    verbose = 1
    sys.argv.remove('verbose')

if 'silent' in sys.argv:  # take care of old flag, just in case
    verbose = 0
    sys.argv.remove('silent')

def print_versions():
    print "Testing Tribler"

class PrintInfoFakeTest(unittest.TestCase):
    def testPrintVersions(self):
        print_versions()

# This little hack is for when this module is run as main and all the
# other modules import it so they will still be able to get the right
# verbose setting.  It's confusing but it works.
import test_all
test_all.verbose = verbose

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(PrintInfoFakeTest))
    return suite

def suite():
    import test.test_cachedb as test_cachedb
    import test.test_friend as test_friend
    import test.test_cachedbhandler as test_cachedbhandler
    import test.test_superpeers as test_superpeers
    import test.test_buddycast as test_buddycast
    import test.test_sim as test_sim
    import test.test_merkle as test_merkle
    import test.test_permid as test_permid
    import test.test_permid_response1 as test_permid_response1
    
    test_modules = [
        test_cachedb,
        test_friend,
        test_cachedbhandler,
        test_superpeers,
        test_buddycast,
	test_sim,
	test_merkle,
	test_permid,
	test_permid_response1
        ]

    alltests = unittest.TestSuite()
    for module in test_modules:
        alltests.addTest(module.test_suite())
    return alltests

def main():
    unittest.main(defaultTest='suite')
    
    
def foo(n = 10000):
    def bar(n):
        for i in range(n):
            math.pow(i,2)
    def baz(n):
        for i in range(n):
            math.sqrt(i)
    bar(n)
    baz(n)

def profile():
    print "profile starts"
    prof = hotshot.Profile("test.prof")
    prof.runcall(foo) #test.test_all.main)
    prof.close()
    stats = hotshot.stats.load("test.prof")
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(100)
    
    
