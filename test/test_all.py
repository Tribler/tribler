""" Run all test cases """

import sys
import os
import unittest
    
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
    
    test_modules = [
        test_cachedb,
        test_friend,
        test_cachedbhandler,
        ]

    alltests = unittest.TestSuite()
    for module in test_modules:
        alltests.addTest(module.test_suite())
    return alltests

def main():
    unittest.main(defaultTest='suite')
    
