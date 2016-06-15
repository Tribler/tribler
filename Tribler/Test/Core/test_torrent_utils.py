import os
import tempfile
import shutil
import libtorrent

from Tribler.Core.Utilities.torrent_utils import create_torrent_file
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.test_as_server import TESTS_DATA_DIR


class TriblerCoreTestTorrentUtils(TriblerCoreTest):

    def setUp(self, annotate=True):
        super(TriblerCoreTestTorrentUtils, self).setUp(annotate)

        self._ubuntu_torrent_name = u"ubuntu-15.04-desktop-amd64.iso.torrent"
        self._origin_torrent_path = os.path.join(TESTS_DATA_DIR, self._ubuntu_torrent_name)

        # create a temporary dir
        self._temp_dir = tempfile.mkdtemp()
        self._test_torrent_path = os.path.join(self._temp_dir, self._ubuntu_torrent_name)
        # copy the test torrent into the dir
        shutil.copyfile(self._origin_torrent_path, self._test_torrent_path)

    def tearDown(self, annotate=True):
        super(TriblerCoreTestTorrentUtils, self).tearDown(annotate)

        # remove the temporary dir
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_create_torrent(self):
        """
        Tests the create_torrent_file() function.
        """

        def on_torrent_created(result):
            # start a libtorrent session to check if the file is correct
            lt_session = libtorrent.session()
            p = {'save_path': self._temp_dir,
                 'ti': libtorrent.torrent_info(result['torrent_file_path'])}
            handle = lt_session.add_torrent(p)

            # if handle.is_valid() returns false, the created torrent file is invalid
            self.assertTrue(handle.is_valid())

            # cleanup libtorrent session
            lt_session.remove_torrent(handle)
            del lt_session

        params = {'': ''}
        create_torrent_file([self._test_torrent_path], params, callback=on_torrent_created)


    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    TORRENT_DATA_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/torrent_creation_files/"))
    FILE1_NAME = "file1.txt"
    FILE2_NAME = "file2.txt"

    def get_params(self):
        return { "comment" : "Proudly created by Tribler", "created by" : "someone",
                 "announce" : "http://tracker.com/announce", "announce-list" : ["http://tracker.com/announce"],
                 "httpseeds" : "http://seed.com", "urllist" : "http://urlseed.com/seed.php",
                 "nodes" : [] }

    def test_create_torrent_one_file(self):
        create_torrent_file([os.path.join(self.TORRENT_DATA_DIR, self.FILE1_NAME)],
                            self.get_params(), self.created_torrent_one_file)

    def test_create_torrent_one_file_2(self):
        create_torrent_file([os.path.join(self.TORRENT_DATA_DIR, self.FILE2_NAME)], {})

    def test_create_torrent_with_nodes(self):
        params = self.get_params()
        params["nodes"] = [("127.0.0.1", 1234)]
        create_torrent_file([os.path.join(self.TORRENT_DATA_DIR, self.FILE1_NAME)],
                            params, self.created_torrent_one_file)

    def created_torrent_one_file(self, result):
        self.assertIsInstance(result, dict)
        self.assertEqual(result["base_path"], self.TORRENT_DATA_DIR)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isfile(result["torrent_file_path"]))

        os.remove(result["torrent_file_path"])

    def test_create_torrent_two_files(self):
        create_torrent_file([os.path.join(self.TORRENT_DATA_DIR, self.FILE1_NAME),
                             os.path.join(self.TORRENT_DATA_DIR, self.FILE2_NAME)],
                            self.get_params())
        self.assertTrue(os.path.isfile(os.path.abspath(os.path.join(self.TORRENT_DATA_DIR, u"torrent_creation_files.torrent"))))
        os.remove(os.path.abspath(os.path.join(self.TORRENT_DATA_DIR, u"torrent_creation_files.torrent")))
