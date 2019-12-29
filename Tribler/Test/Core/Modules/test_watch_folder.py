import os
import shutil

from Tribler.Test.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer


class TestWatchFolder(TestAsServer):

    def setUpPreSession(self):
        super(TestWatchFolder, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_watch_folder_enabled(True)

        self.watch_dir = self.session_base_dir / 'watch'
        os.mkdir(self.watch_dir)

        self.config.set_watch_folder_path(self.watch_dir)

    def test_watchfolder_no_files(self):
        self.session.watch_folder.check_watch_folder()
        self.assertEqual(len(self.session.ltmgr.get_downloads()), 0)

    def test_watchfolder_no_torrent_file(self):
        shutil.copyfile(TORRENT_UBUNTU_FILE, self.watch_dir / "test.txt")
        self.session.watch_folder.check_watch_folder()
        self.assertEqual(len(self.session.ltmgr.get_downloads()), 0)

    def test_watchfolder_invalid_dir(self):
        shutil.copyfile(TORRENT_UBUNTU_FILE, self.watch_dir / "test.txt")
        self.session.config.set_watch_folder_path(self.watch_dir / "test.txt")
        self.session.watch_folder.check_watch_folder()
        self.assertEqual(len(self.session.ltmgr.get_downloads()), 0)

    def test_watchfolder_utf8_dir(self):
        os.mkdir(self.watch_dir / u"\xe2\x82\xac")
        shutil.copyfile(TORRENT_UBUNTU_FILE, self.watch_dir / u"\xe2\x82\xac" / u"\xe2\x82\xac.torrent")
        self.session.config.set_watch_folder_path(self.watch_dir)
        self.session.watch_folder.check_watch_folder()

    def test_watchfolder_torrent_file_one_corrupt(self):
        shutil.copyfile(TORRENT_UBUNTU_FILE, self.watch_dir / "test.torrent")
        shutil.copyfile(TESTS_DATA_DIR / 'test_rss.xml', self.watch_dir / "test2.torrent")
        self.session.watch_folder.check_watch_folder()
        self.assertEqual(len(self.session.ltmgr.get_downloads()), 1)
        self.assertTrue((self.watch_dir / "test2.torrent.corrupt").is_file())

    def test_cleanup(self):
        self.session.watch_folder.cleanup_torrent_file(TESTS_DATA_DIR, 'thisdoesnotexist123.bla')
        self.assertFalse((TESTS_DATA_DIR / 'thisdoesnotexist123.bla.corrupt').exists())
