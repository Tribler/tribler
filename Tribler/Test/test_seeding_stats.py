# Written by Boudewijn Schoon
# see LICENSE.txt for license information

import sys
import time
import unittest
import cPickle

from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.CacheDB.SqliteCacheDBHandler import CrawlerDBHandler

from olconn import OLConnection
from test_crawler import TestCrawler

DEBUG=True

class TestSeedingStats(TestCrawler):
    """ 
    Testing Seeding-Stats statistics gathering using the Crawler framework
    """

    def test_all(self):
        """
        I want to start a Tribler client once and then connect to it
        many times. So there must be only one test method to prevent
        setUp() from creating a new client every time.

        The code is constructed so unittest will show the name of the
        (sub)test where the error occured in the traceback it prints.
        """
        self.subtest_invalid_query()
        self.subtest_valid_query()

    def subtest_invalid_query(self):
        """
        Send a CRAWLER_SEEDINGSTATS_QUERY message to the Tribler
        instance. Execute an invalid SQL query.
        """
        print >>sys.stderr, "-"*80, "\ntest: subtest_invalid_query"

        # make sure that the OLConnection IS in the crawler_db
        crawler_db = CrawlerDBHandler.getInstance()
        crawler_db.temporarilyAddCrawler(self.my_permid)

        s = OLConnection(self.my_keypair, "localhost", self.hisport)

        queries = ["FOO BAR", cPickle.dumps(["select * from category", ""])]
        for query in queries:
            self.send_crawler_request(s, CRAWLER_SEEDINGSTATS_QUERY, 0, 0, query)

            error, payload = self.receive_crawler_reply(s, CRAWLER_SEEDINGSTATS_QUERY, 0)
            assert error != 0, error
            if DEBUG:
                print >>sys.stderr, "test_seeding_stats:", payload

        time.sleep(1)
        
    def subtest_valid_query(self):
        """
        Send a CRAWLER_SEEDINGSTATS_QUERY message to the Tribler
        instance. Execute a valid SQL query.
        """
        print >>sys.stderr, "-"*80, "\ntest: subtest_valid_query"

        # make sure that the OLConnection IS in the crawler_db
        crawler_db = CrawlerDBHandler.getInstance()
        crawler_db.temporarilyAddCrawler(self.my_permid)

        s = OLConnection(self.my_keypair, "localhost", self.hisport, mylistenport=self.listen_port)

        queries = [cPickle.dumps(["SELECT * FROM SeedingStats", "SELECT * FROM SeedingStats WHERE crawled = 0"])]
        for query in queries:
            self.send_crawler_request(s, CRAWLER_SEEDINGSTATS_QUERY, 0, 0, query)

            error, payload = self.receive_crawler_reply(s, CRAWLER_SEEDINGSTATS_QUERY, 0)
            assert error == 0, (error, payload)

            if DEBUG:
                print >>sys.stderr, "test_seeding_stats:", cPickle.loads(payload)

        time.sleep(1)

if __name__ == "__main__":
    def test_suite():
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(TestSeedingStats))
        return suite
    unittest.main(defaultTest="test_suite")

