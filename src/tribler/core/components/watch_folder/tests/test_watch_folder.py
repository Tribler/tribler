import os
import shutil

import pytest
from asynctest import MagicMock

from tribler.core.components.watch_folder.settings import WatchFolderSettings
from tribler.core.components.watch_folder.watch_folder import WatchFolder
from tribler.core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE


# pylint: disable=redefined-outer-name, protected-access

@pytest.fixture
async def watch_folder(tmp_path):
    watch = WatchFolder(
        state_dir=tmp_path,
        settings=WatchFolderSettings(
            enabled=True,
            directory=''
        ),
        download_manager=MagicMock(),
        notifier=MagicMock()
    )
    yield watch
    await watch.stop()


def test_watchfolder_no_files(watch_folder):
    watch_folder.check_watch_folder()
    watch_folder.download_manager.start_download.assert_not_called()


def test_watchfolder_no_torrent_file(watch_folder: WatchFolder):
    directory = watch_folder.settings.get_path_as_absolute('directory', watch_folder.state_dir)

    shutil.copyfile(TORRENT_UBUNTU_FILE, directory / "test.txt")
    watch_folder.check_watch_folder()
    watch_folder.download_manager.start_download.assert_not_called()


def test_watchfolder_utf8_dir(watch_folder, tmp_path):
    new_watch_dir = tmp_path / "\xe2\x82\xac"
    os.mkdir(new_watch_dir)
    shutil.copyfile(TORRENT_UBUNTU_FILE, new_watch_dir / "\xe2\x82\xac.torrent")
    watch_folder.watch_folder = new_watch_dir
    watch_folder.check_watch_folder()


def test_watchfolder_torrent_file_one_corrupt(watch_folder: WatchFolder):
    directory = watch_folder.settings.get_path_as_absolute('directory', watch_folder.state_dir)
    def mock_start_download(*_, **__):
        mock_start_download.downloads_started += 1

    mock_start_download.downloads_started = 0

    shutil.copyfile(TORRENT_UBUNTU_FILE, directory / "test.torrent")
    shutil.copyfile(TESTS_DATA_DIR / 'test_rss.xml', directory / "test2.torrent")
    watch_folder.download_manager.start_download = mock_start_download
    watch_folder.download_manager.download_exists = lambda *_: False
    watch_folder.check_watch_folder()
    assert mock_start_download.downloads_started == 1
    assert (directory / "test2.torrent.corrupt").is_file()


def test_cleanup(watch_folder):
    watch_folder.cleanup_torrent_file(TESTS_DATA_DIR, 'thisdoesnotexist123.bla')
    assert not (TESTS_DATA_DIR / 'thisdoesnotexist123.bla.corrupt').exists()
