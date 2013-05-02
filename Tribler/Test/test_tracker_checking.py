from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
import unittest


class TestTorrentChecking(unittest.TestCase):

    def setUp(self):
        self.torrentChecking = TorrentChecking()

    def test_torrent_checking(self):
        infohash_str = 'TkFX5S4qd2DPW63La/VObgOH/Nc='
        infohash = str2bin(infohash_str)

        self.torrentChecking.addToQueue(infohash)

    def tearDown(self):
        self.torrentChecking.shutdown()
        TorrentChecking.delInstance()
