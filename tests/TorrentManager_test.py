import unittest
import xmlrpclib
import os
import pytest
from time import sleep

# Import configuration
from TestConfig import *


class TorrentsRemoteSearch(unittest.TestCase):

    def setUp(self):
        """
        Load XML-RPC connection.
        :return: Nothing.
        """
        self.xmlrpc = xmlrpclib.ServerProxy(XMLRPC_URL, allow_none=True)

    def tearDown(self):
        """
        Destroy XML-RPC connection.
        :return: Nothing.
        """
        self.xmlrpc = None

    @pytest.mark.timeout(10)
    def testA_Methods(self):
        """
        Tests if the torrents.* methods exist
        :return: Nothing.
        """
        methods = self.xmlrpc.system.listMethods()

        assert len(methods) > 0
        assert 'torrents.get_remote_results' in methods
        assert 'torrents.get_remote_results_count' in methods
        assert 'torrents.search_remote' in methods

    def testB_RemoteSearchSintel(self):
        """
        Search for 'Sintel' and check results.
        :return: Nothing.
        """
        # Clear previous results
        self.xmlrpc.torrents.search_remote("vodo")
        sleep(1)

        self.xmlrpc.torrents.search_remote("sintel")

        result_count = 0
        timeout = REMOTE_SEARCH_TIMEOUT
        while (not result_count > 0) and (timeout > 0):
            result_count = self.xmlrpc.torrents.get_remote_results_count()

            sleep(REMOTE_SEARCH_SLEEP)
            timeout -= REMOTE_SEARCH_SLEEP

        assert result_count > 0
        assert timeout >= 0

        results = self.xmlrpc.torrents.get_remote_results()

        hitrate = 0.0
        for result in results:
            hitrate += 1 if "sintel" in result['name'].lower() else 0

        missrate = ((len(results) - hitrate) / len(results))
        assert  missrate <= REMOTE_SEARCH_TOLERANCE, "Missrate is %s%%" % (missrate * 100)

    def testC_RemoteSearchVodo(self):
        """
        Search for 'Vodo' and check results.
        :return: Nothing.
        """
        self.xmlrpc.torrents.search_remote("vodo")

        result_count = 0
        timeout = REMOTE_SEARCH_TIMEOUT
        while (not result_count > 0) and (timeout > 0):
            result_count = self.xmlrpc.torrents.get_remote_results_count()

            sleep(REMOTE_SEARCH_SLEEP)
            timeout -= REMOTE_SEARCH_SLEEP

        assert result_count > 0
        assert timeout >= 0

        results = self.xmlrpc.torrents.get_remote_results()

        hitrate = 0.0
        for result in results:
            hitrate += 1 if "vodo" in result['name'].lower() else 0

        missrate = ((len(results) - hitrate) / len(results))
        assert missrate <= REMOTE_SEARCH_TOLERANCE, "Missrate is %s%%" % (missrate * 100)

    @unittest.skipIf(not REMOTE_DEADLOCK_TESTS, "REMOTE_DEADLOCK_TESTS is False")
    def XtestY_Deadlock_slow(self):
        """
        Do a big amount of searches with a large interval between them.
        :return: Nothing.
        """
        slp = 10
        lps = 10

        loops = lps
        while loops > 0:
            keywords = ['sintel', 'vod', 'hd', 'movies']

            while loops > 0:
                for keyword in keywords:
                    self.xmlrpc.torrents.search_remote(keyword)
                    print "."
                    sleep(slp)

                print "%s/%s.." % (loops, lps)
                loops -= 1

    @unittest.skipIf(not REMOTE_DEADLOCK_TESTS, "REMOTE_DEADLOCK_TESTS is False")
    def testZ_Deadlock_fast(self):
        """
        Do a big amount of searches with a small interval between them.
        :return: Nothing.
        """

        slp = 0.1
        lps = 100
        while slp < 3:
            loops = lps
            keywords = ['sintel', 'vod', 'hd', 'movies']

            while loops > 0:
                for keyword in keywords:
                    self.xmlrpc.torrents.search_remote(keyword)
                    sleep(slp)

                loops -= 1

            slp = slp * 2
            lps = lps / 2
            print slp,

if __name__ == '__main__':
    print "Using %s as test target." % XMLRPC_URL
    unittest.main()