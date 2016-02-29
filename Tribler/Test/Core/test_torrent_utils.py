import os
from Tribler.Core.Utilities.torrent_utils import create_torrent_file
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestTorrentUtils(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    TORRENT_DATA_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/torrent_creation_files/"))
    FILE1_NAME = "file1.txt"
    FILE2_NAME = "file2.txt"

    def get_params(self):
        return { "piece length" : 65536, "comment" : "Proudly created by Tribler", "created by" : "someone",
                 "announce" : "http://tracker.com/announce", "announce-list" : ["http://tracker.com/announce"],
                 "httpseeds" : "http://seed.com", "urllist" : "http://urlseed.com/seed.php",
                 "nodes" : [] }

    def test_create_torrent_one_file(self):
        create_torrent_file([os.path.join(self.TORRENT_DATA_DIR, self.FILE1_NAME)],
                            self.get_params(), self.created_torrent_one_file)

    def test_create_torrent_one_file_2(self):
        create_torrent_file([os.path.join(self.TORRENT_DATA_DIR, self.FILE2_NAME)], {})

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
        self.assertTrue(os.path.isfile(os.path.abspath(os.path.join(self.TORRENT_DATA_DIR, u"file2.txt.torrent"))))
        os.remove(os.path.abspath(os.path.join(self.TORRENT_DATA_DIR, u"file2.txt.torrent")))
