import asyncio
import shutil
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.reporter.exception_handler import NoCrashException
from tribler.core.components.watch_folder.settings import WatchFolderSettings
from tribler.core.components.watch_folder.watch_folder import WatchFolder
from tribler.core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE, TORRENT_VIDEO_FILE
from tribler.core.utilities.path_util import Path

# pylint: disable=redefined-outer-name, protected-access
TEST_TORRENT = "test.torrent"
TEST_CHECK_INTERVAL = 0.1


@pytest.fixture
async def watch_folder(tmp_path):
    download_manager = MagicMock()
    download_manager.start_download = AsyncMock()
    watch = WatchFolder(
        state_dir=tmp_path,
        settings=WatchFolderSettings(
            enabled=True,
            directory=''
        ),
        download_manager=download_manager,
        notifier=MagicMock(),
        check_interval=TEST_CHECK_INTERVAL
    )
    yield watch
    await watch.stop()


async def test_watch_folder_no_files(watch_folder):
    # Test that in the case of an empty folder, downloads are not started
    assert await watch_folder._check_watch_folder()

    assert not watch_folder.download_manager.start_download.called


async def test_watch_folder_no_torrent_file(watch_folder: WatchFolder):
    # Test that in the case of a folder without torrents, downloads are not started
    directory = watch_folder.settings.get_path_as_absolute('directory', watch_folder.state_dir)
    shutil.copyfile(TORRENT_UBUNTU_FILE, directory / "test.txt")

    assert await watch_folder._check_watch_folder()

    assert not watch_folder.download_manager.start_download.called


async def test_watch_folder_utf8_dir(watch_folder, tmp_path):
    # Test that torrents with UTF characters in the path are processed correctly
    watch_folder.download_manager.download_exists = Mock(return_value=False)
    unicode_folder = tmp_path / "\xe2\x82\xac"
    unicode_folder.mkdir()
    shutil.copyfile(TORRENT_UBUNTU_FILE, unicode_folder / "\xe2\x82\xac.torrent")

    assert await watch_folder._check_watch_folder()

    assert watch_folder.download_manager.start_download.called


async def test_watch_folder_torrent_file_corrupt(watch_folder: WatchFolder):
    # Test that all corrupted files are renamed to `<file_name>.corrupt`
    corrupted_torrent = watch_folder.state_dir / "test2.torrent"
    shutil.copyfile(TESTS_DATA_DIR / 'test_rss.xml', corrupted_torrent)

    await watch_folder._check_watch_folder_handle_exceptions()

    assert not corrupted_torrent.exists()
    assert Path(f'{corrupted_torrent}.corrupt').exists()


@patch.object(TorrentDef, 'get_metainfo', Mock(return_value=None))
async def test_watch_folder_torrent_file_no_metainfo(watch_folder: WatchFolder):
    # Test that in the case of missing metainfo, the torrent file will be skipped
    watch_folder.download_manager.download_exists = Mock(return_value=False)
    shutil.copyfile(TORRENT_UBUNTU_FILE, watch_folder.state_dir / "test.torrent")

    assert await watch_folder._check_watch_folder()

    assert not watch_folder.download_manager.start_download.called


async def test_watch_folder_torrent_file_start_download(watch_folder: WatchFolder):
    # Test that in the case of presence of a torrent file, a download is started
    watch_folder.download_manager.download_exists = Mock(return_value=False)
    shutil.copyfile(TORRENT_VIDEO_FILE, watch_folder.state_dir / "test.torrent")

    assert await watch_folder._check_watch_folder()

    assert watch_folder.download_manager.start_download.call_count == 1


@patch.object(WatchFolder, '_check_watch_folder_handle_exceptions')
async def test_watch_folder_start_schedule(mocked_check_watch_folder: Mock, watch_folder: WatchFolder):
    # Test that the `start` method schedules the `check_watch_folder` execution
    watch_folder.start()
    await asyncio.sleep(TEST_CHECK_INTERVAL * 3)

    assert 2 <= mocked_check_watch_folder.call_count <= 3


@patch.object(WatchFolder, '_check_watch_folder')
async def test_watch_folder_start_schedule_with_exception(mocked_check_watch_folder: Mock, watch_folder: WatchFolder):
    # Test that errors in the `check_watch_folder` method don't affect the `start` execution
    mocked_check_watch_folder.side_effect = PermissionError

    watch_folder.start()
    await asyncio.sleep(TEST_CHECK_INTERVAL * 3)

    assert 2 <= mocked_check_watch_folder.call_count <= 3


@patch.object(WatchFolder, '_check_watch_folder', Mock(side_effect=PermissionError))
async def test_watch_folder_no_crash_exception(watch_folder: WatchFolder):
    # Test that errors raised in `_check_watch_folder` reraise as `NoCrashException`
    with pytest.raises(NoCrashException):
        await watch_folder._check_watch_folder_handle_exceptions()


async def test_watch_folder_invalid_dir(watch_folder: WatchFolder, tmp_path):
    """ Test that the watch folder is disabled when the directory is invalid"""
    watch_folder.settings.put_path_as_relative(
        property_name='directory',
        value=Path('path that does not exist'),
        state_dir=Path(tmp_path)
    )

    assert not await watch_folder._check_watch_folder()


async def test_watch_folder_not_dir(watch_folder: WatchFolder, tmp_path):
    """ Test that the watch folder is disabled when the "directory" setting is not a directory"""
    any_file = tmp_path / 'any.file'
    any_file.touch()

    watch_folder.settings.put_path_as_relative(
        property_name='directory',
        value=any_file,
        state_dir=Path(tmp_path)
    )

    assert not await watch_folder._check_watch_folder()


async def test_watch_folder_disabled(watch_folder: WatchFolder):
    """ Test that the watch folder is disabled when the "enabled" setting is False"""
    watch_folder.settings.enabled = False
    assert not await watch_folder._check_watch_folder()
