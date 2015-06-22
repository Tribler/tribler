import unittest
import xmlrpclib
import os
import pytest
from time import sleep

# Import configuration
from TestConfig import *


class DownloadByInfohash(unittest.TestCase):

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
        Tests if the downloads.* methods exist
        :return: Nothing.
        """
        methods = self.xmlrpc.system.listMethods()

        assert len(methods) > 0
        assert 'downloads.add' in methods
        assert 'downloads.remove' in methods
        assert 'downloads.get_progress_info' in methods
        assert 'downloads.get_all_progress_info' in methods
        #assert 'downloads.get_vod_info' in methods
        #assert 'downloads.get_full_info' in methods
        assert 'downloads.start_vod' in methods
        assert 'downloads.stop_vod' in methods
        assert 'downloads.get_vod_uri' in methods
        assert 'downloads.set_state' in methods

    def clean_torrents(self):
        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        for dl in all_dls:
            self.xmlrpc.downloads.remove(dl['infohash'], True)

        while len(self.xmlrpc.downloads.get_all_progress_info()) > 0:
            sleep(1)

    def add_torrent(self, infohash, name):
        if not self.xmlrpc.downloads.add(SINTEL_TEST_INFOHASH, 'Sintel'):
            return False
        sleep(1)

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        while len(all_dls) < 1:
            all_dls = self.xmlrpc.downloads.get_all_progress_info()
            sleep(1)

        return True

    def remove_torrent(self, infohash, removedata):
        assert self.xmlrpc.downloads.remove(infohash, removedata)
        sleep(1)

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        while len(all_dls) > 0:
            all_dls = self.xmlrpc.downloads.get_all_progress_info()
            sleep(1)

        return True

    def wait_for_dht(self):
        timeout = DHT_DOWNLOAD_TORRENT_TIMEOUT

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        while all_dls[0]['status_string'] == 'DLSTATUS_METADATA' and (timeout > 0):
            all_dls = self.xmlrpc.downloads.get_all_progress_info()

            sleep(DHT_DOWNLOAD_TORRENT_SLEEP)
            timeout -= DHT_DOWNLOAD_TORRENT_SLEEP

        assert timeout >= 0, "Waited longer than %ss for status change" % DHT_DOWNLOAD_TORRENT_TIMEOUT
        assert not all_dls[0]['status_string'] == 'DLSTATUS_METADATA', "Download status is wrong: %s" % all_dls[0]['status_string']

    def wait_for_download(self):
        timeout = TORRENT_DOWNLOAD_STALL_TIMEOUT
        progress = 0

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        while all_dls[0]['status_string'] == 'DLSTATUS_DOWNLOADING' and (timeout > 0):
            all_dls = self.xmlrpc.downloads.get_all_progress_info()

            if progress == all_dls[0]['progress']:
                timeout -= TORRENT_DOWNLOAD_STALL_SLEEP
            else:
                progress = all_dls[0]['progress']
                timeout = TORRENT_DOWNLOAD_STALL_TIMEOUT

            print "%.2f%% at %.2f KiB/s" % (progress * 100, all_dls[0]['speed_down'] / 1024)
            sleep(TORRENT_DOWNLOAD_STALL_SLEEP)

        assert timeout >= 0
        assert not all_dls[0]['status_string'] == 'DLSTATUS_DOWNLOADING', all_dls[0]['status_string']
        assert all_dls[0]['status_string'] == 'DLSTATUS_SEEDING', all_dls[0]['status_string']

    def testC_AddAndRemoveSintel(self):
        """
        Add and remove Sintel torrent.
        :return: Nothing.
        """

        self.clean_torrents()

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        assert len(all_dls) == 0, "Found downloads while there shouldn't be any:\n%s" % all_dls

        assert self.add_torrent(SINTEL_TEST_INFOHASH, 'Sintel')

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        assert len(all_dls) == 1, "Found more or less than one download:\n%s" % all_dls
        assert all_dls[0]['infohash'] == SINTEL_TEST_INFOHASH, "Infohash does not match (%s != %s)" % (all_dls[0]['infohash'], SINTEL_TEST_INFOHASH)

        self.wait_for_dht()
        sleep(1)

        assert self.remove_torrent(SINTEL_TEST_INFOHASH, True)
        sleep(1)

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        assert len(all_dls) == 0, "Found downloads while there shouldn't be any:\n%s" % all_dls

    @unittest.skipIf(not DOWNLOAD_TORRENT_TESTS, "DOWNLOAD_TORRENT_TESTS is False")
    def testD_DownloadSintel(self):
        """
        Full Sintel torrent download.
        :return: Nothing.
        """

        self.clean_torrents()

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        assert len(all_dls) == 0, all_dls

        assert self.add_torrent(SINTEL_TEST_INFOHASH, 'Sintel')

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        assert len(all_dls) == 1
        assert all_dls[0]['infohash'] == SINTEL_TEST_INFOHASH

        self.wait_for_dht()
        sleep(1)

        self.wait_for_download()
        sleep(1)

        assert self.remove_torrent(SINTEL_TEST_INFOHASH, True)
        sleep(1)

        all_dls = self.xmlrpc.downloads.get_all_progress_info()
        assert len(all_dls) == 0


if __name__ == '__main__':
    print "Using %s as test target." % XMLRPC_URL
    unittest.main()