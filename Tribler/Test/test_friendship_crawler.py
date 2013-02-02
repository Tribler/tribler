# Written by Boudewijn Schoon, Arno Bakker
# see LICENSE.txt for license information

import unittest
import sys
import time
from traceback import print_exc
from M2Crypto import EC

from Tribler.Test.test_crawler import TestCrawler
from olconn import OLConnection
from Tribler.Core.Utilities.bencode import bencode, bdecode

from Tribler.Core.MessageID import CRAWLER_FRIENDSHIP_STATS
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.CacheDB.SqliteCacheDBHandler import CrawlerDBHandler
from Tribler.Core.CacheDB.SqliteFriendshipStatsCacheDB import FriendshipStatisticsDBHandler

DEBUG=True

class TestFriendshipCrawler(TestCrawler):
    """ 
    Testing the user side of the crawler
    """

    def setUpPreSession(self):
        TestCrawler.setUpPreSession(self)
        self.config.set_social_networking(True)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestCrawler.setUpPostSession(self)

        self.some_keypair = EC.gen_params(EC.NID_sect233k1)
        self.some_keypair.gen_key()
        self.some_permid = str(self.some_keypair.pub().get_der())

        self.friendshipStatistics_db = FriendshipStatisticsDBHandler.getInstance()
        self.friendshipStatistics_db.insertFriendshipStatistics( bin2str(self.his_permid), bin2str(self.some_permid), int(time.time()), 0, commit=True)        
        self.friendshipStatistics_db.insertFriendshipStatistics( bin2str(self.my_permid), bin2str(self.some_permid), int(time.time()), 0, commit=True)

        # make sure that the OLConnection IS in the crawler_db
        crawler_db = CrawlerDBHandler.getInstance()
        crawler_db.temporarilyAddCrawler(self.my_permid)

    
    def test_all(self):
        """
        I want to start a Tribler client once and then connect to it
        many times. So there must be only one test method to prevent
        setUp() from creating a new client every time.

        The code is constructed so unittest will show the name of the
        (sub)test where the error occured in the traceback it prints.
        """
        self.subtest_good_friendship_stats()

    def subtest_good_friendship_stats(self):
        """
        Send a valid message-id from a registered crawler peer
        """
        print >>sys.stderr, "-"*80, "\ntest: good friendship stats"

        s = OLConnection(self.my_keypair, "localhost", self.hisport)

        t = time.time() - 100.0
        msg_dict = {'current time':int(t)}
        payload = bencode(msg_dict)
        self.send_crawler_request(s, CRAWLER_FRIENDSHIP_STATS, 0, 0, payload)

        error, payload = self.receive_crawler_reply(s, CRAWLER_FRIENDSHIP_STATS, 0)
        assert error == 0
        
        d = bdecode(payload)
        if DEBUG:
            print >>sys.stderr, "test: Got FRIENDSHIPSTATISTICS",`d`
        stats = d['stats']
        self.assert_(len(stats) == 1)
        record = d['stats'][0]
        self.assert_(record[0] == bin2str(self.his_permid))  # source_permid
        self.assert_(record[1] == bin2str(self.some_permid)) # target_permid
        self.assert_(record[2] == 0) # isForwarder

        time.sleep(1)
        s.close()

    # def send_crawler_request(self, sock, message_id, channel_id, frequency, payload):
    # def receive_crawler_reply(self, sock, message_id, channel_id):

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestFriendshipCrawler))
    
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="test_suite")


