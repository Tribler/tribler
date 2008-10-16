# Written by Boudewijn Schoon
# see LICENSE.txt for license information

import socket
import unittest
import os
import sys
import time
from sha import sha
from random import randint,shuffle
from traceback import print_exc
from types import StringType, IntType, ListType
from threading import Thread
from M2Crypto import Rand,EC
import cPickle

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_REQUEST, CRAWLER_REPLY, CRAWLER_DATABASE_QUERY, getMessageName

from Tribler.Core.CacheDB.SqliteCacheDBHandler import CrawlerDBHandler

DEBUG=True

class TestCrawler(TestAsServer):
    """ 
    Testing the user side of the crawler
    """
    
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        Rand.load_file('randpool.dat', -1)

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)

        # Enable buddycast and crawler handling
        self.config.set_buddycast(True)
        self.config.set_crawler(True)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.my_permid = str(self.my_keypair.pub().get_der())
        self.my_hash = sha(self.my_permid).digest()
        self.his_permid = str(self.his_keypair.pub().get_der())        

    def tearDown(self):
        """ override TestAsServer """
        TestAsServer.tearDown(self)
        try:
            os.remove('randpool.dat')
        except:
            pass

    def test_all(self):
        """
        I want to start a Tribler client once and then connect to it
        many times. So there must be only one test method to prevent
        setUp() from creating a new client every time.

        The code is constructed so unittest will show the name of the
        (sub)test where the error occured in the traceback it prints.
        """
        self.subtest_invalid_permid()
        self.subtest_invalid_messageid()
        self.subtest_invalid_sql_query()
        self.subtest_valid_messageid()

    def subtest_invalid_permid(self):
        """
        Send crawler messages from a non-crawler peer
        """
        print >>sys.stderr, "-"*80, "\ntest: invalid_messageid"

        # make sure that the OLConnection is NOT in the crawler_db
        crawler_db = CrawlerDBHandler.getInstance()
        assert not self.my_permid in crawler_db.getCrawlers()

        # We are not a registered crawler, any request from us should
        # be denied
        messages = [CRAWLER_REQUEST,
                    CRAWLER_REQUEST + CRAWLER_DATABASE_QUERY,
                    CRAWLER_REQUEST + CRAWLER_DATABASE_QUERY,
                    CRAWLER_REQUEST + chr(0)]
        for msg in messages:
            s = OLConnection(self.my_keypair, "localhost", self.hisport)
            s.send(msg)
            response  = s.recv()
            assert response == "", "response type is %s" % getMessageName(response[0])

        time.sleep(1)
        s.close()

    def subtest_invalid_messageid(self):
        """
        Send an invalid message-id from a registered crawler peer
        """
        print >>sys.stderr, "-"*80, "\ntest: invalid_messageid"

        # make sure that the OLConnection IS in the crawler_db
        crawler_db = CrawlerDBHandler.getInstance()
        crawler_db.temporarilyAddCrawler(self.my_permid)

        # We are a registered crawler, start sending invalid messages
        messages = [CRAWLER_REQUEST,
                    CRAWLER_REQUEST + chr(0),
                    CRAWLER_REPLY,
                    CRAWLER_REPLY + chr(0)]
        for msg in messages:
            s = OLConnection(self.my_keypair, "localhost", self.hisport)
            s.send(msg)
            response  = s.recv()
            assert response == "", "response type is %s" % getMessageName(response[0])

        time.sleep(1)
        s.close()

    def subtest_invalid_sql_query(self):
        """
        Send an invalid sql query from a registered crawler peer
        """
        print >>sys.stderr, "-"*80, "\ntest: invalid_sql_query"

        # make sure that the OLConnection IS in the crawler_db
        crawler_db = CrawlerDBHandler.getInstance()
        crawler_db.temporarilyAddCrawler(self.my_permid)

        s = OLConnection(self.my_keypair, "localhost", self.hisport)

        queries = ["FOO BAR"]
        for query in queries:
            self.send_crawler_request(s, CRAWLER_DATABASE_QUERY, 0, 0, query)

            error, payload = self.receive_crawler_reply(s, CRAWLER_DATABASE_QUERY, 0)
            assert error == 1
            if DEBUG:
                print >>sys.stderr, payload

        time.sleep(1)
        s.close()

    def subtest_valid_messageid(self):
        """
        Send a valid message-id from a registered crawler peer
        """
        print >>sys.stderr, "-"*80, "\ntest: valid_messageid"

        # make sure that the OLConnection IS in the crawler_db
        crawler_db = CrawlerDBHandler.getInstance()
        crawler_db.temporarilyAddCrawler(self.my_permid)

        s = OLConnection(self.my_keypair, "localhost", self.hisport)

        queries = ["SELECT name FROM category", "SELECT * FROM peer", "SELECT * FROM torrent"]
        for query in queries:
            self.send_crawler_request(s, CRAWLER_DATABASE_QUERY, 0, 0, query)

            error, payload = self.receive_crawler_reply(s, CRAWLER_DATABASE_QUERY, 0)
            assert error == 0
            if DEBUG:
                print >>sys.stderr, cPickle.loads(payload)

        time.sleep(1)
        s.close()

    def send_crawler_request(self, sock, message_id, channel_id, frequency, payload):
        # Sending a request from a Crawler to a Tribler peer
        #     SIZE    INDEX
        #     1 byte: 0      CRAWLER_REQUEST (from Tribler.Core.BitTornado.BT1.MessageID)
        #     1 byte: 1      --MESSAGE-SPECIFIC-ID--
        #     1 byte: 2      Channel id
        #     2 byte: 3+4    Frequency
        #     n byte: 5...   Request payload
        sock.send("".join((CRAWLER_REQUEST,
                           message_id,
                           chr(channel_id & 0xFF),
                           chr((frequency >> 8) & 0xFF) + chr(frequency & 0xFF),
                           payload)))

    def receive_crawler_reply(self, sock, message_id, channel_id):
        # Sending a reply from a Tribler peer to a Crawler
        #     SIZE    INDEX
        #     1 byte: 0      CRAWLER_REPLY (from Tribler.Core.BitTornado.BT1.MessageID)
        #     1 byte: 1      --MESSAGE-SPECIFIC-ID--
        #     1 byte: 2      Channel id
        #     1 byte: 3      Parts left
        #     1 byte: 4      Indicating success (0) or failure (non 0)
        #     n byte: 5...   Reply payload

        parts = []
        while True:
            response  = sock.recv()
            if response:
                if response[0] == CRAWLER_REPLY and response[1] == message_id and ord(response[2]) == channel_id:
                    if DEBUG:
                        print >>sys.stderr, "test_crawler: received", getMessageName(response[0:2]), "channel", channel_id, "parts left", ord(response[3])
                    parts.append(response[5:])

                    if ord(response[3]):
                        # there are parts left
                        continue

                    return ord(response[4]), "".join(parts)

            return False

if __name__ == "__main__":
    unittest.main()

