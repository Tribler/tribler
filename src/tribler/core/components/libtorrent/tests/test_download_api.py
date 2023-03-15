import shutil

from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler.core.utilities.rest_utils import path_to_url
from tribler.core.utilities.simpledefs import DownloadStatus


async def test_download_torrent_from_url(tmp_path, file_server, download_manager):
    # Setup file server to serve torrent file
    shutil.copyfile(TORRENT_UBUNTU_FILE, tmp_path / "ubuntu.torrent")
    download = await download_manager.start_download_from_uri(f'http://localhost:{file_server}/ubuntu.torrent',
                                                              config=DownloadConfig())
    await download.wait_for_status(DownloadStatus.DOWNLOADING)


async def test_download_torrent_from_file(download_manager):
    uri = path_to_url(TORRENT_UBUNTU_FILE)
    d = await download_manager.start_download_from_uri(uri, config=DownloadConfig())
    await d.wait_for_status(DownloadStatus.DOWNLOADING)


async def test_download_torrent_from_file_with_escaped_characters(download_manager, tmp_path):
    destination = tmp_path / 'ubuntu%20%21 15.04.torrent'
    shutil.copyfile(TORRENT_UBUNTU_FILE, destination)
    uri = path_to_url(destination)
    d = await download_manager.start_download_from_uri(uri, config=DownloadConfig())
    await d.wait_for_status(DownloadStatus.DOWNLOADING)
