import os
import shutil
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.common import TORRENT_UBUNTU_FILE, TESTS_DATA_DIR


class TestWatchFolder(TestAsServer):

    def setUpPreSession(self):
        super(TestWatchFolder, self).setUpPreSession()
        self.config.set_libtorrent(True)
        self.config.set_watch_folder_enabled(True)

        self.watch_dir = os.path.join(self.session_base_dir, 'watch')
        os.mkdir(self.watch_dir)

        self.config.set_watch_folder_path(self.watch_dir)

    def test_watchfolder_no_files(self):
        self.session.lm.watch_folder.check_watch_folder()
        self.assertEqual(len(self.session.get_downloads()), 0)

    def test_watchfolder_no_torrent_file(self):
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(self.watch_dir, "test.txt"))
        self.session.lm.watch_folder.check_watch_folder()
        self.assertEqual(len(self.session.get_downloads()), 0)

    def test_watchfolder_invalid_dir(self):
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(self.watch_dir, "test.txt"))
        self.session.set_watch_folder_path(os.path.join(self.watch_dir, "test.txt"))
        self.session.lm.watch_folder.check_watch_folder()
        self.assertEqual(len(self.session.get_downloads()), 0)

    def test_watchfolder_torrent_file_one_corrupt(self):
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(self.watch_dir, "test.torrent"))
        shutil.copyfile(os.path.join(TESTS_DATA_DIR, 'test_rss.xml'), os.path.join(self.watch_dir, "test2.torrent"))
        self.session.lm.watch_folder.check_watch_folder()
        self.assertEqual(len(self.session.get_downloads()), 1)
        self.assertTrue(os.path.isfile(os.path.join(self.watch_dir, "test2.torrent.corrupt")))

    def test_cleanup(self):
        self.session.lm.watch_folder.cleanup_torrent_file(TESTS_DATA_DIR, 'thisdoesnotexist123.bla')
        self.assertFalse(os.path.exists(os.path.join(TESTS_DATA_DIR, 'thisdoesnotexist123.bla.corrupt')))
