import os
import random
from pathlib import Path
from unittest.mock import Mock

from aiohttp import web

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.util import succeed

import pytest

from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.libtorrent.download import Download
from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.session import Session
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TESTS_DIR
from tribler_core.tests.tools.tracker.udp_tracker import UDPTracker
from tribler_core.upgrade.db72_to_pony import DispersyToPonyMigration
from tribler_core.utilities.network_utils import get_random_port
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
def tribler_root_dir(tmpdir):
    return Path(tmpdir)


@pytest.fixture
def tribler_state_dir(tribler_root_dir):
    return tribler_root_dir / "dot.Tribler"


@pytest.fixture
def tribler_download_dir(tribler_root_dir):
    return tribler_root_dir / "TriblerDownloads"


@pytest.fixture
def tribler_config(tribler_state_dir, tribler_download_dir):
    config = TriblerConfig(tribler_state_dir)
    config.set_default_destination_dir(tribler_download_dir)
    config.set_torrent_checking_enabled(False)
    config.set_ipv8_enabled(False)
    config.set_discovery_community_enabled(False)
    config.set_ipv8_walk_scaling_enabled(False)
    config.set_libtorrent_enabled(False)
    config.set_libtorrent_dht_readiness_timeout(0)
    config.set_api_http_enabled(False)
    config.set_tunnel_community_enabled(False)
    config.set_popularity_community_enabled(False)
    config.set_dht_enabled(False)
    config.set_version_checker_enabled(False)
    config.set_libtorrent_dht_enabled(False)
    config.set_chant_enabled(False)
    config.set_resource_monitor_enabled(False)
    config.set_bootstrap_enabled(False)

    return config


@pytest.fixture
def seed_config(tribler_config, tmpdir_factory):
    seed_config = tribler_config.copy()
    seed_config.set_state_dir(Path(tmpdir_factory.mktemp("seeder")))
    seed_config.set_libtorrent_enabled(True)

    return seed_config


@pytest.fixture
def download_config():
    return DownloadConfig()


@pytest.fixture
def state_dir(tribler_config):
    return tribler_config.get_state_dir()


@pytest.fixture
def enable_libtorrent(tribler_config):
    tribler_config.set_libtorrent_enabled(True)


@pytest.fixture
def enable_ipv8(tribler_config):
    tribler_config.set_ipv8_enabled(True)


@pytest.fixture
def mock_dlmgr(session, mocker, tmpdir):
    mocker.patch.object(session, 'dlmgr')
    session.dlmgr.shutdown = lambda: succeed(None)
    session.dlmgr.get_checkpoint_dir = lambda: tmpdir


@pytest.fixture
def mock_dlmgr_get_download(session, mocker, tmpdir, mock_dlmgr):
    session.dlmgr.get_download = lambda _: None


@pytest.fixture
async def session(tribler_config):
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


@pytest.fixture
def free_ports():
    """
    Return random, free ports.
    This is here to make sure that tests in different buckets get assigned different listen ports.
    Also, make sure that we have no duplicates in selected ports.
    """
    global selected_ports

    def get_ports(param):
        rstate = random.getstate()
        random.seed()
        ports = []
        for _ in range(param):
            selected_port = get_random_port(min_port=1024, max_port=50000)
            while selected_port in selected_ports:
                selected_port = get_random_port(min_port=1024, max_port=50000)
            selected_ports.add(selected_port)
            ports.append(selected_port)
        random.setstate(rstate)
        return ports

    return get_ports


@pytest.fixture
def free_port(free_ports):
    return free_ports(1)[0]


@pytest.fixture
def free_https_port(free_ports):
    return free_ports(1)[0]


@pytest.fixture
def free_file_server_port(free_ports):
    return free_ports(2)[1]


@pytest.fixture
async def file_server(free_file_server_port, tmpdir):
    """
    Returns a file server that listens in a free port, and serves from the "serve" directory in the tmpdir.
    """
    app = web.Application()
    app.add_routes([web.static('/', Path(tmpdir))])
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', free_file_server_port)
    await site.start()
    yield free_file_server_port
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


@pytest.fixture
def enable_api(tribler_config, free_port):
    tribler_config.set_api_http_enabled(True)
    tribler_config.set_api_http_port(free_port)
    tribler_config.set_api_retry_port(True)


@pytest.fixture
def enable_https(tribler_config, free_https_port):
    tribler_config.set_api_https_enabled(True)
    tribler_config.set_api_https_port(free_https_port)
    tribler_config.set_api_https_certfile(TESTS_DIR / 'data' / 'certfile.pem')


@pytest.fixture
def enable_chant(tribler_config):
    tribler_config.set_chant_enabled(True)


@pytest.fixture
def enable_watch_folder(tribler_state_dir, tribler_config):
    tribler_config.set_watch_folder_path(tribler_state_dir / "watch")
    os.makedirs(tribler_state_dir / "watch")
    tribler_config.set_watch_folder_enabled(True)


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
    download.config = DownloadConfig(state_dir=session.config.get_state_dir())
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
    lt_status.all_time_download = 200
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
