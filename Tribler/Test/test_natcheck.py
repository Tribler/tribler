# Written by Arno Bakker, Boudewijn Schoon
# see LICENSE.txt for license information

import sys
import time
import unittest

from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler
from Tribler.Core.CacheDB.SqliteCacheDBHandler import CrawlerDBHandler
from Tribler.Test.test_as_server import TestAsServer

from olconn import OLConnection
from test_crawler import TestCrawler

DEBUG=True

class TestNatCheck(TestCrawler):
    """ 
    Testing Nat-Check statistics gathering using the Crawler framework
    """

    def test_all(self):
        """
        I want to start a Tribler client once and then connect to it
        many times. So there must be only one test method to prevent
        setUp() from creating a new client every time.

        The code is constructed so unittest will show the name of the
        (sub)test where the error occured in the traceback it prints.
        """
        self.subtest_valid_nat_check()
        
    def subtest_valid_nat_check(self):
        """
        Send a CRAWLER_NATCHECK message to the Tribler instance. A
        reply containing a nat type should be returned.
        """
        print >>sys.stderr, "-"*80, "\ntest: subtest_valid_nat_check"

        # make sure that the OLConnection IS in the crawler_db
        crawler_db = CrawlerDBHandler.getInstance()
        crawler_db.temporarilyAddCrawler(self.my_permid)
        assert self.my_permid in crawler_db.getCrawlers()

        s = OLConnection(self.my_keypair, "localhost", self.hisport)
        self.send_crawler_request(s, CRAWLER_NATCHECK, 0, 0, "")

        error, payload = self.receive_crawler_reply(s, CRAWLER_NATCHECK, 0)
        assert error == 0
        if DEBUG:
            print >>sys.stderr, "test_natcheck:", bdecode(payload)

        time.sleep(1)
        s.close()

if __name__ == "__main__":
    def test_suite():
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(TestNatCheck))
        return suite
    unittest.main(defaultTest="test_suite")

