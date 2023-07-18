from unittest.mock import MagicMock

import pytest
from aiohttp import web

from tribler.core.components.libtorrent.download_manager.download import Download
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.utilities.unicode import hexlify


# pylint: disable=redefined-outer-name


@pytest.fixture
def download_config():
    return DownloadConfig()


@pytest.fixture
def test_tdef(state_dir):
    tdef = TorrentDef()
    sourcefn = TESTS_DATA_DIR / 'video.avi'
    tdef.add_content(sourcefn)
    tdef.set_tracker("http://localhost/announce")
    torrentfn = state_dir / "gen.torrent"
    tdef.save(torrentfn)
    return tdef


@pytest.fixture
async def file_server(tmp_path, free_port):
    """
    Returns a file server that listens in a free port, and serves from the "serve" directory in the tmp_path
    """
    app = web.Application()
    app.add_routes([web.static('/', tmp_path)])
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', free_port)
    await site.start()
    yield free_port

    await app.shutdown()
    await runner.shutdown()
    await site.stop()


@pytest.fixture
async def test_download(mock_dlmgr, test_tdef):
    config = DownloadConfig(state_dir=mock_dlmgr.state_dir)
    download = Download(test_tdef, download_manager=mock_dlmgr, config=config)
    download.infohash = hexlify(test_tdef.get_infohash())
    yield download

    await download.shutdown()


@pytest.fixture
def mock_handle(test_download):
    test_download.handle = MagicMock()


@pytest.fixture
def mock_lt_status():
    lt_status = MagicMock()
    lt_status.upload_rate = 123
    lt_status.download_rate = 43
    lt_status.total_upload = 100
    lt_status.total_download = 200
    lt_status.all_time_upload = 100
    lt_status.total_done = 200
    lt_status.list_peers = 10
    lt_status.download_payload_rate = 10
    lt_status.upload_payload_rate = 30
    lt_status.list_seeds = 5
    lt_status.progress = 0.75
    lt_status.error = False
    lt_status.paused = False
    lt_status.state = 3
    lt_status.num_pieces = 0
    lt_status.pieces = []
    lt_status.finished_time = 10
    return lt_status
