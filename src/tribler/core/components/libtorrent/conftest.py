import pytest
from aiohttp import web

from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.tests.tools.common import TESTS_DATA_DIR


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
