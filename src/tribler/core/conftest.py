import asyncio
import logging
import os
import platform
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.util import succeed

from tribler.core.components.knowledge.db.knowledge_db import KnowledgeDatabase
from tribler.core.components.libtorrent.download_manager.download import Download
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.settings import LibtorrentSettings
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.tests.tools.common import TESTS_DATA_DIR, TESTS_DIR
from tribler.core.tests.tools.tracker.udp_tracker import UDPTracker
from tribler.core.utilities.network_utils import default_network_utils
from tribler.core.utilities.simpledefs import DownloadStatus
from tribler.core.utilities.unicode import hexlify

# Enable origin tracking for coroutine objects in the current thread, so when a test does not handle
# some coroutine properly, we can see a traceback with the name of the test which created the coroutine.
# Note that the error can happen in an unrelated test where the unhandled task from the previous test
# was garbage collected. Without the origin tracking, it may be hard to see the test that created the task.
sys.set_coroutine_origin_tracking_depth(10)


def pytest_configure(config):  # pylint: disable=unused-argument
    # Disable logging from faker for all tests
    logging.getLogger('faker.factory').propagate = False


@pytest.fixture(name="tribler_root_dir")
def _tribler_root_dir(tmp_path):
    return Path(tmp_path)


@pytest.fixture(name="tribler_state_dir")
def _tribler_state_dir(tribler_root_dir):
    return tribler_root_dir / "dot.Tribler"


@pytest.fixture(name="tribler_download_dir")
def _tribler_download_dir(tribler_root_dir):
    return tribler_root_dir / "TriblerDownloads"


@pytest.fixture(name="tribler_config")
def _tribler_config(tribler_state_dir, tribler_download_dir) -> TriblerConfig:
    config = TriblerConfig(state_dir=tribler_state_dir)
    config.download_defaults.put_path_as_relative('saveas', tribler_download_dir, state_dir=tribler_state_dir)
    config.torrent_checking.enabled = False
    config.ipv8.enabled = False
    config.ipv8.walk_scaling_enabled = False
    config.discovery_community.enabled = False
    config.libtorrent.enabled = False
    config.libtorrent.dht_readiness_timeout = 0
    config.tunnel_community.enabled = False
    config.popularity_community.enabled = False
    config.dht.enabled = False
    config.libtorrent.dht = False
    config.chant.enabled = False
    config.resource_monitor.enabled = False
    config.bootstrap.enabled = False
    return config


@pytest.fixture
def download_config():
    return DownloadConfig()


@pytest.fixture
def state_dir(tmp_path):
    state_dir = tmp_path / 'state_dir'
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def enable_ipv8(tribler_config):
    tribler_config.ipv8.enabled = True


@pytest.fixture
def mock_dlmgr(state_dir):
    dlmgr = MagicMock()
    dlmgr.config = LibtorrentSettings()
    dlmgr.shutdown = lambda: succeed(None)
    checkpoints_dir = state_dir / 'dlcheckpoints'
    checkpoints_dir.mkdir()
    dlmgr.get_checkpoint_dir = lambda: checkpoints_dir
    dlmgr.state_dir = state_dir
    dlmgr.get_downloads = lambda: []
    dlmgr.checkpoints_count = 1
    dlmgr.checkpoints_loaded = 1
    dlmgr.all_checkpoints_are_loaded = True
    return dlmgr


@pytest.fixture
def mock_dlmgr_get_download(mock_dlmgr):  # pylint: disable=unused-argument, redefined-outer-name
    mock_dlmgr.get_download = lambda _: None


@pytest.fixture
def video_tdef():
    return TorrentDef.load(TESTS_DATA_DIR / 'video.avi.torrent')


@pytest.fixture
async def video_seeder(tmp_path_factory, video_tdef):
    config = LibtorrentSettings()
    config.dht = False
    config.upnp = False
    config.natpmp = False
    config.lsd = False
    seeder_state_dir = tmp_path_factory.mktemp('video_seeder_state_dir')
    dlmgr = DownloadManager(
        config=config,
        state_dir=seeder_state_dir,
        notifier=MagicMock(),
        peer_mid=b"0000")
    dlmgr.metadata_tmpdir = tmp_path_factory.mktemp('metadata_tmpdir')
    dlmgr.initialize()
    dscfg_seed = DownloadConfig()
    dscfg_seed.set_dest_dir(TESTS_DATA_DIR)
    upload = dlmgr.start_download(tdef=video_tdef, config=dscfg_seed)
    await upload.wait_for_status(DownloadStatus.SEEDING)
    yield dlmgr
    await dlmgr.shutdown()


selected_ports = set()


@pytest.fixture(name="free_port")
def fixture_free_port():
    return default_network_utils.get_random_free_port(start=1024, stop=50000)


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
async def magnet_redirect_server(free_port):
    """
    Return a HTTP redirect server that redirects to a magnet.
    """
    magnet_link = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"

    async def redirect_handler(_):
        return web.HTTPFound(magnet_link)

    app = web.Application()
    app.add_routes([web.get('/', redirect_handler)])
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    http_server = web.TCPSite(runner, 'localhost', free_port)
    await http_server.start()
    yield free_port
    await http_server.stop()


TEST_PERSONAL_KEY = LibNaCLSK(
    b'4c69624e61434c534b3af56022aa5d556c07aeed704ee98df7dca580f'
    b'522e1405663f0d36508d2189cb8991af2dd27b34bc18b4d24869e2c4f2cfdb164a78ea6e687daf7a21640d62b1b'[10:]
)


@pytest.fixture
def metadata_store(tmp_path):
    mds = MetadataStore(db_filename=tmp_path / 'test.db',
                        channels_dir=tmp_path / 'channels',
                        my_key=TEST_PERSONAL_KEY,
                        disable_sync=True)
    yield mds
    mds.shutdown()


@pytest.fixture
def knowledge_db():
    db = KnowledgeDatabase()
    yield db
    db.shutdown()


@pytest.fixture
def enable_https(tribler_config, free_port):
    tribler_config.api.put_path_as_relative('https_certfile', TESTS_DIR / 'data' / 'certfile.pem',
                                            tribler_config.state_dir)
    tribler_config.api.https_enabled = True
    tribler_config.api.https_port = free_port


@pytest.fixture
def enable_watch_folder(tribler_state_dir, tribler_config):
    tribler_config.watch_folder.put_path_as_relative('directory', tribler_state_dir / "watch", tribler_state_dir)
    os.makedirs(tribler_state_dir / "watch")
    tribler_config.watch_folder.enabled = True


@pytest.fixture
async def udp_tracker(free_port):
    udp_tracker = UDPTracker(free_port)
    yield udp_tracker
    await udp_tracker.stop()


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
def event_loop():
    if platform.system() == 'Windows':
        # to prevent the "Loop is closed" error
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_download(mock_dlmgr, test_tdef):
    config = DownloadConfig(state_dir=mock_dlmgr.state_dir)
    download = Download(test_tdef, download_manager=mock_dlmgr, config=config)
    download.infohash = hexlify(test_tdef.get_infohash())
    yield download

    await download.shutdown()


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


@pytest.fixture
def mock_handle(mocker, test_download):
    return mocker.patch.object(test_download, 'handle')


@pytest.fixture
def peer_key():
    return default_eccrypto.generate_key("curve25519")


@pytest.fixture
async def download_manager(tmp_path_factory):
    config = LibtorrentSettings()
    config.dht = False
    config.upnp = False
    config.natpmp = False
    config.lsd = False
    download_manager = DownloadManager(
        config=config,
        state_dir=tmp_path_factory.mktemp('state_dir'),
        notifier=MagicMock(),
        peer_mid=b"0000")
    download_manager.metadata_tmpdir = tmp_path_factory.mktemp('metadata_tmpdir')
    download_manager.initialize()
    yield download_manager

    await download_manager.shutdown()
