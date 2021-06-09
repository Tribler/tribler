import shutil

import pytest

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING

from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_download_torrent_from_url(enable_libtorrent, session, tmpdir, file_server, free_port):
    # Setup file server to serve torrent file
    shutil.copyfile(TORRENT_UBUNTU_FILE, tmpdir / "ubuntu.torrent")
    download = await session.dlmgr.start_download_from_uri(f'http://localhost:{file_server}/ubuntu.torrent')
    await download.wait_for_status(DLSTATUS_DOWNLOADING)


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_download_torrent_from_file(enable_libtorrent, session):
    d = await session.dlmgr.start_download_from_uri(TORRENT_UBUNTU_FILE.as_uri())
    await d.wait_for_status(DLSTATUS_DOWNLOADING)
