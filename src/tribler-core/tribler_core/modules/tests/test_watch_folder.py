import os
import shutil

from tribler_core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE


def test_watchfolder_no_files(enable_watch_folder, mock_dlmgr, session):
    session.watch_folder.check_watch_folder()
    session.dlmgr.start_download.assert_not_called()


def test_watchfolder_no_torrent_file(enable_watch_folder, mock_dlmgr, tribler_state_dir, session):
    shutil.copyfile(TORRENT_UBUNTU_FILE, tribler_state_dir / "watch" / "test.txt")
    session.watch_folder.check_watch_folder()
    session.dlmgr.start_download.assert_not_called()


def test_watchfolder_invalid_dir(enable_watch_folder, mock_dlmgr, tribler_state_dir, session):
    shutil.copyfile(TORRENT_UBUNTU_FILE, tribler_state_dir / "watch" / "test.txt")
    session.config.set_watch_folder_path(tribler_state_dir / "watch" / "test.txt")
    session.watch_folder.check_watch_folder()
    session.dlmgr.start_download.assert_not_called()


def test_watchfolder_utf8_dir(enable_watch_folder, mock_dlmgr, tribler_state_dir, session):
    os.mkdir(tribler_state_dir / "watch" / "\xe2\x82\xac")
    shutil.copyfile(TORRENT_UBUNTU_FILE, tribler_state_dir / "watch" / "\xe2\x82\xac" / "\xe2\x82\xac.torrent")
    session.config.set_watch_folder_path(tribler_state_dir / "watch")
    session.watch_folder.check_watch_folder()


def test_watchfolder_torrent_file_one_corrupt(enable_watch_folder, mock_dlmgr, tribler_state_dir, session):
    def mock_start_download(*_, **__):
        mock_start_download.downloads_started += 1

    mock_start_download.downloads_started = 0

    shutil.copyfile(TORRENT_UBUNTU_FILE, tribler_state_dir / "watch" / "test.torrent")
    shutil.copyfile(TESTS_DATA_DIR / 'test_rss.xml', tribler_state_dir / "watch" / "test2.torrent")
    session.dlmgr.start_download = mock_start_download
    session.dlmgr.download_exists = lambda *_: False
    session.watch_folder.check_watch_folder()
    assert mock_start_download.downloads_started == 1
    assert (tribler_state_dir / "watch" / "test2.torrent.corrupt").is_file()


def test_cleanup(enable_watch_folder, mock_dlmgr, tribler_state_dir, session):
    session.watch_folder.cleanup_torrent_file(TESTS_DATA_DIR, 'thisdoesnotexist123.bla')
    assert not (TESTS_DATA_DIR / 'thisdoesnotexist123.bla.corrupt').exists()
