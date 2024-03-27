import gc
from unittest.mock import MagicMock

import pytest
from aiohttp import web

from tribler.core.components.libtorrent.download_manager.download import Download
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE, TORRENT_VIDEO_FILE
from tribler.core.utilities.unicode import hexlify


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
    lt_status.total_payload_upload = 30
    lt_status.total_payload_download = 100
    lt_status.all_time_upload = 200
    lt_status.all_time_download = 1000
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


@pytest.fixture
def dual_movie_tdef() -> TorrentDef:
    tdef = TorrentDef()
    tdef.add_content(TORRENT_VIDEO_FILE)
    tdef.add_content(TORRENT_UBUNTU_FILE)
    tdef.save()
    return tdef


@pytest.fixture(autouse=True)
def ensure_gc(request):
    """ Ensure that the garbage collector runs after each test.
    This is critical for test stability as we use Libtorrent and need to ensure all its destructors are called. """
    # For this fixture, it is necessary for it to be called as late as possible within the current test's scope.
    # Therefore it should be placed at the first place in the "function" scope.
    # If there are two or more autouse fixtures within this scope, the order should be explicitly set through using
    # this fixture as a dependency.
    # See the discussion in https://github.com/Tribler/tribler/pull/7542 for more information.

    yield
    # Without "yield" the fixture triggers the garbage collection at the beginning of the (next) test.
    # For that reason, the errors triggered during the garbage collection phase will take place not in the erroneous
    # test but in the randomly scheduled next test. Usually, these errors are silently suppressed, as any exception in
    # __del__ methods is silently suppressed, but they still can somehow affect the test.
    #
    # By adding the yield we move the garbage collection phase to the end of the current test, to not affect the next
    # test.
    gc.collect()
