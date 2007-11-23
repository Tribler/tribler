""" Run all test cases that can be run in a single python interpreter after one another """

import sys
import os
import unittest

import hotshot, hotshot.stats
import math

    
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

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(PrintInfoFakeTest))
    return suite

def suite():
    import test_cachedb as test_cachedb
    import test_friend as test_friend
    import test_cachedbhandler as test_cachedbhandler
    import test_superpeers as test_superpeers
    """
    import test_buddycast as test_buddycast
    import test_buddycast2_datahandler as test_buddycast2_datahandler
    import test_sim as test_sim
    """
    import test_merkle as test_merkle
    import test_permid as test_permid
    import test_permid_response1 as test_permid_response1
    import test_dialback_request as test_dialback_request
    import test_extend_hs as test_extend_hs
    import test_extend_hs_t350 as test_extend_hs_t350
    import test_social_overlap as test_social_overlap
    import test_gui_server as test_gui_server
    """
    import test_remote_query as test_remote_query
    """
    import test_ut_pex as test_ut_pex
    import test_bartercast as test_bartercast

    # Note: There are more tests, but these require a fresh Python interpreter
    # for each test, so they need to be run from shell scripts. See test_*.sh and
    # test_*.bat in this dir.
    
    # Legend: 
    # '#'  = broken
    # '##' = disable temporarily for testing a specific test
    #
    test_modules = [
        test_cachedb,
        ##test_friend,   # TEMPARNO: need to fix MyDB ref
        test_cachedbhandler,
        #test_superpeers, # TEMPARNO: need to fix MyDB + SuperPeerList ref
        ##test_buddycast,  # currently not working due to unfinished test functions
        ##test_buddycast2_datahandler, # complains about addRemoteSearchPeer 
        ##test_sim, # currently not working due to unfinished test functions
        test_merkle,
        test_permid,
        test_permid_response1,
        test_dialback_request,
        test_extend_hs,
        test_extend_hs_t350,
        test_social_overlap,
        test_gui_server,
        ##test_remote_query, # TEMPARNO: need to fix torrentManager dependency
        test_ut_pex,
        test_bartercast
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
    
if __name__ == "__main__":
    main()
    
