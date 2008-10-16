# Written by Arno Bakker, Lucian d' Acunto, Boudewijn Schoon
# see LICENSE.txt for license information

import socket
import unittest
import os
import sys
import time
#from sha import sha
#from random import randint,shuffle
#from traceback import print_exc
#from types import StringType, IntType, ListType
#from threading import Thread
#from M2Crypto import Rand,EC

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
#from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler
from Tribler.Core.CacheDB.SqliteCacheDBHandler import CrawlerDBHandler

from test_crawler import TestCrawler


DEBUG=True

class TestNatCheck(TestCrawler):
    """ 
    Testing Nat-Check statistics gathering using the Crawler framework
    """
    
#     def setUp(self):
#         """ override TestAsServer """
#         TestAsServer.setUp(self)
#         Rand.load_file('randpool.dat', -1)

#     def setUpPreSession(self):
#         """ override TestAsServer """
#         TestAsServer.setUpPreSession(self)
#         # Enable buddycast
#         self.config.set_buddycast(True)
#         self.config.set_start_recommender(True)
#         self.config.set_bartercast(True)

#     def setUpPostSession(self):
#         """ override TestAsServer """
#         TestAsServer.setUpPostSession(self)

#         self.mypermid = str(self.my_keypair.pub().get_der())
#         self.hispermid = str(self.his_keypair.pub().get_der())        
#         self.myhash = sha(self.mypermid).digest()

#     def tearDown(self):
#         """ override TestAsServer """
#         TestAsServer.tearDown(self)
#         try:
#             os.remove('randpool.dat')
#         except:
#             pass

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
        assert not self.my_permid in crawler_db.getCrawlers()

        s = OLConnection(self.my_keypair, "localhost", self.hisport)
        self.send_crawler_request(s, CRAWLER_NATCHECK, 0, 0, "")

        error, payload = self.receive_crawler_reply(s, CRAWLER_NATCHECK, 0)
        assert error == 0
        if DEBUG:
            print >>sys.stderr, payload

        time.sleep(1)
        s.close()

if __name__ == "__main__":
    unittest.main()

