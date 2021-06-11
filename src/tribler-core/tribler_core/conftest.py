import os
from pathlib import Path
from unittest.mock import Mock

from aiohttp import web

from ipv8.database import database_blob
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_common.network_utils import NetworkUtils
from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.libtorrent.download import Download
from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.session import Session
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TESTS_DIR
from tribler_core.tests.tools.tracker.udp_tracker import UDPTracker
from tribler_core.upgrade.legacy_to_pony import DispersyToPonyMigration
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify


@pytest.fixture(name="tribler_root_dir")
def _tribler_root_dir(tmpdir):
    return Path(tmpdir)


@pytest.fixture(name="tribler_state_dir")
def _tribler_state_dir(tribler_root_dir):
    return tribler_root_dir / "dot.Tribler"


@pytest.fixture(name="tribler_download_dir")
def _tribler_download_dir(tribler_root_dir):
    return tribler_root_dir / "TriblerDownloads"


@pytest.fixture(name="tribler_config")
def _tribler_config(tribler_state_dir, tribler_download_dir):
    return TriblerConfig(tribler_state_dir)\
        .put_path('download_defaults', 'saveas', tribler_download_dir)\
        .put('torrent_checking', 'enabled', False)\
        .put('ipv8', 'enabled', False)\
        .put('discovery_community', 'enabled', False)\
        .put('ipv8', 'walk_scaling_enabled', False)\
        .put('libtorrent', 'enabled', False)\
        .put('libtorrent', 'dht_readiness_timeout', 0)\
        .put('api', 'http_enabled', False)\
        .put('tunnel_community', 'enabled', False)\
        .put('popularity_community', 'enabled', False)\
        .put('dht', 'enabled', False)\
        .put('libtorrent', 'dht', False)\
        .put('chant', 'enabled', False)\
        .put('resource_monitor', 'enabled', False)\
        .put('bootstrap', 'enabled', False)


def get_free_port():
    return NetworkUtils(remember_checked_ports_enabled=True).get_random_free_port()


@pytest.fixture
def seed_config(tribler_config, tmpdir_factory):
    seed_config = tribler_config.copy()
    seed_config.state_dir = tmpdir_factory.mktemp("seeder")
    return seed_config\
        .put('libtorrent', 'enabled', True)\
        .put('libtorrent', 'port', get_free_port())\
        .put('tunnel_community', 'socks5_listen_ports', [(get_free_port()) for _ in range(5)])


@pytest.fixture
def download_config():
    return DownloadConfig()


@pytest.fixture
def state_dir(tribler_config):
    return tribler_config.state_dir


@pytest.fixture
def enable_libtorrent(tribler_config):
    tribler_config.put('libtorrent', 'enabled', True)


@pytest.fixture
def enable_ipv8(tribler_config):
    tribler_config.put('ipv8', 'enabled', True)


@pytest.fixture
def mock_dlmgr(session, mocker, tmpdir):
    mocker.patch.object(session, 'dlmgr')
    session.dlmgr.shutdown = lambda: succeed(None)
    session.dlmgr.get_checkpoint_dir = lambda: tmpdir


@pytest.fixture
def mock_dlmgr_get_download(session, mock_dlmgr):  # pylint: disable=unused-argument, redefined-outer-name
    session.dlmgr.get_download = lambda _: None


@pytest.fixture(name='session')
async def _session(tribler_config):
    tribler_config\
        .put('api', 'http_port', get_free_port())\
        .put('libtorrent', 'port', get_free_port())\
        .put('tunnel_community', 'socks5_listen_ports', [get_free_port() for _ in range(5)])

    session = Session(tribler_config)
    session.upgrader_enabled = False

    await session.start()
    yield session
    await session.shutdown()


@pytest.fixture
def video_tdef():
    return TorrentDef.load(TESTS_DATA_DIR / 'video.avi.torrent')


@pytest.fixture
async def video_seeder_session(seed_config, video_tdef):
    seeder_session = Session(seed_config)
    seeder_session.upgrader_enabled = False
    await seeder_session.start()
    dscfg_seed = DownloadConfig()
    dscfg_seed.set_dest_dir(TESTS_DATA_DIR)
    upload = seeder_session.dlmgr.start_download(tdef=video_tdef, config=dscfg_seed)
    await upload.wait_for_status(DLSTATUS_SEEDING)
    yield seeder_session
    await seeder_session.shutdown()


@pytest.fixture
def channel_tdef():
    return TorrentDef.load(TESTS_DATA_DIR / 'sample_channel' / 'channel_upd.torrent')


@pytest.fixture
async def channel_seeder_session(seed_config, channel_tdef):
    seeder_session = Session(seed_config)
    seeder_session.upgrader_enabled = False
    await seeder_session.start()
    dscfg_seed = DownloadConfig()
    dscfg_seed.set_dest_dir(TESTS_DATA_DIR / 'sample_channel')
    upload = seeder_session.dlmgr.start_download(tdef=channel_tdef, config=dscfg_seed)
    await upload.wait_for_status(DLSTATUS_SEEDING)
    yield seeder_session
    await seeder_session.shutdown()


selected_ports = set()


@pytest.fixture(name="free_port")
def fixture_free_port():
    return NetworkUtils(remember_checked_ports_enabled=True).get_random_free_port(start=1024, stop=50000)


@pytest.fixture
async def file_server(tmpdir, free_port):
    """
    Returns a file server that listens in a free port, and serves from the "serve" directory in the tmpdir.
    """
    app = web.Application()
    app.add_routes([web.static('/', Path(tmpdir))])
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', free_port)
    await site.start()
    yield free_port
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
def metadata_store(tmpdir):
    metadata_store_path = Path(tmpdir) / 'test.db'
    mds = MetadataStore(metadata_store_path, tmpdir, TEST_PERSONAL_KEY, disable_sync=True)
    yield mds
    mds.shutdown()


@pytest.fixture
def dispersy_to_pony_migrator(metadata_store):
    dispersy_db_path = TESTS_DATA_DIR / 'upgrade_databases/tribler_v29.sdb'
    migrator = DispersyToPonyMigration(dispersy_db_path)
    migrator.initialize(metadata_store)
    return migrator


@pytest.fixture(name='enable_api')
def _enable_api(tribler_config, free_port):
    tribler_config\
        .put('api', 'http_enabled', True)\
        .put('api', 'http_port', free_port)\
        .put('api', 'retry_port', True)


@pytest.fixture
def enable_https(tribler_config, free_port):
    tribler_config\
        .put('api', 'https_enabled', True)\
        .put('api', 'https_port', free_port)\
        .put_path('api', 'https_certfile', TESTS_DIR / 'data' / 'certfile.pem')


@pytest.fixture(name='enable_chant')
def _enable_chant(tribler_config):
    (tribler_config.put('chant', 'enabled', True)
        .put('chant', 'manager_enabled', True)
        .put('libtorrent', 'enabled', True))


@pytest.fixture
def enable_watch_folder(tribler_state_dir, tribler_config):
    tribler_config.put_path('watch_folder', 'directory', tribler_state_dir / "watch")
    os.makedirs(tribler_state_dir / "watch")
    tribler_config.put('watch_folder', 'enabled', True)


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
async def test_download(session, mock_dlmgr, test_tdef):
    download = Download(session, test_tdef)
    download.config = DownloadConfig(state_dir=session.config.state_dir)
    download.infohash = hexlify(test_tdef.get_infohash())
    yield download
    await download.shutdown()


@pytest.fixture
def mock_lt_status():
    lt_status = Mock()
    lt_status.state = 3
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
def needle_in_haystack(enable_chant, enable_api, session):  # pylint: disable=unused-argument
    num_hay = 100
    with db_session:
        _ = session.mds.ChannelMetadata(title='test', tags='test', subscribed=True, infohash=random_infohash())
        for x in range(0, num_hay):
            session.mds.TorrentMetadata(title='hay ' + str(x), infohash=random_infohash())
        session.mds.TorrentMetadata(title='needle', infohash=database_blob(bytearray(random_infohash())))
        session.mds.TorrentMetadata(title='needle2', infohash=database_blob(bytearray(random_infohash())))
    return session
