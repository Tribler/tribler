import os
import shutil

from asynctest import Mock

import pytest

from tribler_core.components.watch_folder.watch_folder import WatchFolder
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE


@pytest.fixture
async def watcher_fixture(tmp_path):
    watch = WatchFolder(watch_folder_path=tmp_path, download_manager=Mock(), notifier=Mock())
    yield watch
    await watch.stop()


def test_watchfolder_no_files(watcher_fixture):
    watcher_fixture.check_watch_folder()
    watcher_fixture.download_manager.start_download.assert_not_called()


def test_watchfolder_no_torrent_file(watcher_fixture):
    shutil.copyfile(TORRENT_UBUNTU_FILE, watcher_fixture.watch_folder / "test.txt")
    watcher_fixture.check_watch_folder()
    watcher_fixture.download_manager.start_download.assert_not_called()


def test_watchfolder_utf8_dir(watcher_fixture, tmp_path):
    new_watch_dir = tmp_path / "\xe2\x82\xac"
    os.mkdir(new_watch_dir)
    shutil.copyfile(TORRENT_UBUNTU_FILE, new_watch_dir / "\xe2\x82\xac.torrent")
    watcher_fixture.watch_folder = new_watch_dir
    watcher_fixture.check_watch_folder()


def test_watchfolder_torrent_file_one_corrupt(watcher_fixture):
    def mock_start_download(*_, **__):
        mock_start_download.downloads_started += 1

    mock_start_download.downloads_started = 0

    shutil.copyfile(TORRENT_UBUNTU_FILE, watcher_fixture.watch_folder / "test.torrent")
    shutil.copyfile(TESTS_DATA_DIR / 'test_rss.xml', watcher_fixture.watch_folder / "test2.torrent")
    watcher_fixture.download_manager.start_download = mock_start_download
    watcher_fixture.download_manager.download_exists = lambda *_: False
    watcher_fixture.check_watch_folder()
    assert mock_start_download.downloads_started == 1
    assert (watcher_fixture.watch_folder / "test2.torrent.corrupt").is_file()


def test_cleanup(watcher_fixture):
    watcher_fixture.cleanup_torrent_file(TESTS_DATA_DIR, 'thisdoesnotexist123.bla')
    assert not (TESTS_DATA_DIR / 'thisdoesnotexist123.bla.corrupt').exists()
