"""
Seeding tests.

Author(s): Arno Bakker, Niels Zeilemaker
"""
import pytest

from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler_core.tests.tools.common import TESTS_DATA_DIR


@pytest.mark.asyncio
@pytest.mark.timeout(20)
async def test_seeding(download_manager, video_seeder, video_tdef, tmp_path):
    """
    Test whether a torrent is correctly seeded
    """
    dscfg = DownloadConfig()
    dscfg.set_dest_dir(tmp_path)
    download = download_manager.start_download(tdef=video_tdef, config=dscfg)
    download.add_peer(("127.0.0.1", video_seeder.libtorrent_port))
    await download.wait_for_status(DLSTATUS_SEEDING)

    with open(tmp_path / "video.avi", "rb") as f:
        realdata = f.read()
    with open(TESTS_DATA_DIR / 'video.avi', "rb") as f:
        expdata = f.read()

    assert realdata == expdata
