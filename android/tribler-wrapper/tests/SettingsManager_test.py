import unittest
import xmlrpclib
import os
import pytest
from time import sleep

# Import configuration
from TestConfig import *


class SetGetSettings(unittest.TestCase):

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
        Tests if the settings.* methods exist
        :return: Nothing.
        """
        methods = self.xmlrpc.system.listMethods()

        assert len(methods) > 0
        assert 'settings.get_family_filter' in methods
        assert 'settings.set_family_filter' in methods
        assert 'settings.get_thumbs_directory' in methods

    def testB_GetThumbsDir(self):
        """
        Test whether the thumbs dir is returned correctly.
        :return: Nothing.
        """
        coltordir = self.xmlrpc.settings.get_thumbs_directory()

        assert 'collected_torrent_files' in coltordir

    def testC_SetFamilyFilter(self):
        """
        Enable and disable the family filter.
        :return: Nothing
        """
        xxx_filter = self.xmlrpc.settings.get_family_filter()

        # TODO: Enable this whenever the family filter is on by default
        #assert xxx_filter == True

        # Test disable
        assert self.xmlrpc.settings.set_family_filter(False)

        xxx_filter = self.xmlrpc.settings.get_family_filter()
        assert xxx_filter is False

        # Test enable
        assert self.xmlrpc.settings.set_family_filter(True)

        xxx_filter = self.xmlrpc.settings.get_family_filter()
        assert xxx_filter is True

    def testD_SearchFamilyFilterEnabled(self):
        """
        Search for a naughty word and check for XXX results.
        :return: Nothing.
        """
        assert self.xmlrpc.settings.set_family_filter(True)

        results = self.naughty_search()

        for res in results:
            assert not res['category'].lower() == "xxx"

    def testE_SearchFamilyFilterDisabled(self):
        """
        Search for a naughty word and check for XXX results.
        :return: Nothing.
        """
        assert self.xmlrpc.settings.set_family_filter(False)

        results = self.naughty_search()

        find_naughty_results = False
        for res in results:
            find_naughty_results = find_naughty_results or res['category'].lower() == "xxx"

        assert find_naughty_results

    def naughty_search(self):
        """
        Search for torrents using a naughty word.
        :return: List of torrents.
        """

        # First clear previous naughty search
        self.xmlrpc.torrents.search_remote("thisisarandomlongstringwithprobablynoresults")

        # Search for naughty torrents
        self.xmlrpc.torrents.search_remote(SEARCH_NAUGHTY_WORD)

        result_count = 0
        timeout = REMOTE_SEARCH_TIMEOUT
        while (not result_count > 0) and (timeout > 0):
            result_count = self.xmlrpc.torrents.get_remote_results_count()

            sleep(REMOTE_SEARCH_SLEEP)
            timeout -= REMOTE_SEARCH_SLEEP

        assert result_count > 0
        assert timeout >= 0

        results = self.xmlrpc.torrents.get_remote_results()

        #print results
        return results

if __name__ == '__main__':
    print "Using %s as test target." % XMLRPC_URL
    unittest.main()