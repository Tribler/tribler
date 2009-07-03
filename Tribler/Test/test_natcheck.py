# Written by Arno Bakker, Boudewijn Schoon
# see LICENSE.txt for license information

import sys
import time
import unittest
import socket

from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.CacheDB.SqliteCacheDBHandler import CrawlerDBHandler

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

        s = OLConnection(self.my_keypair, "localhost", self.hisport, mylistenport=self.listen_port)
        self.send_crawler_request(s, CRAWLER_NATCHECK, 42, 0, "")
        s.close()

        if DEBUG: print >>sys.stderr, "test_natcheck: the nat-check code allows for a 10 minute delay in reporting the nat stats"
        self.listen_socket.settimeout(11 * 60)

        # wait for reply
        try:
            conn, addr = self.listen_socket.accept()
        except socket.timeout:
            if DEBUG: print >> sys.stderr,"test_natcheck: timeout, bad, peer didn't connect to send the crawler reply"
            assert False, "test_natcheck: timeout, bad, peer didn't connect to send the crawler reply"
        s = OLConnection(self.my_keypair, "", 0, conn, mylistenport=self.listen_port)

        # read reply
        error, payload = self.receive_crawler_reply(s, CRAWLER_NATCHECK, 42)
        assert error == 0
        if DEBUG: print >>sys.stderr, "test_natcheck:", bdecode(payload)

        time.sleep(1)

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestNatCheck))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="test_suite")

