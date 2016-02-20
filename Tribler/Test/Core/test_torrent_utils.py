import os
from Tribler.Core.Utilities.torrent_utils import create_torrent_file
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestTorrentUtils(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    TORRENT_DATA_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/torrent_creation_files/"))

    def get_params(self):
        return { "piece length" : 42, "comment" : "Proudly created by Tribler", "created by" : "someone",
                 "announce" : "http://tracker.com/announce", "announce-list" : ["http://tracker.com/announce"],
                 "httpseeds" : "http://seed.com", "urllist" : "http://urlseed.com/seed.php" }

    def test_create_torrent_one_file(self):
        create_torrent_file([self.TORRENT_DATA_DIR + "/file1.txt"], self.get_params(), self.created_torrent_one_file)

    def created_torrent_one_file(self, result):
        self.assertIsInstance(result, dict)
        self.assertEqual(result["base_path"], self.TORRENT_DATA_DIR)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isfile(result["torrent_file_path"]))

        os.remove(result["torrent_file_path"])

    def test_create_torrent_two_files(self):
        create_torrent_file([self.TORRENT_DATA_DIR + "/file1.txt", self.TORRENT_DATA_DIR + "/file2.txt"],
                            self.get_params())
        self.assertTrue(os.path.isfile(os.path.abspath(os.path.join(self.TORRENT_DATA_DIR, u"file2.txt.torrent"))))
        os.remove(os.path.abspath(os.path.join(self.TORRENT_DATA_DIR, u"file2.txt.torrent")))
