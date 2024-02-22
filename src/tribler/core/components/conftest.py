from unittest.mock import MagicMock

import pytest
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.util import succeed

from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.settings import LibtorrentSettings
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.database.db.store import MetadataStore
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import DownloadStatus

# pylint: disable=redefined-outer-name

TEST_PERSONAL_KEY = LibNaCLSK(
    b'4c69624e61434c534b3af56022aa5d556c07aeed704ee98df7dca580f'
    b'522e1405663f0d36508d2189cb8991af2dd27b34bc18b4d24869e2c4f2cfdb164a78ea6e687daf7a21640d62b1b'[10:]
)


@pytest.fixture
def tribler_config(tmp_path) -> TriblerConfig:
    state_dir = Path(tmp_path) / "dot.Tribler"
    download_dir = Path(tmp_path) / "TriblerDownloads"
    config = TriblerConfig(state_dir=state_dir)
    config.download_defaults.put_path_as_relative('saveas', download_dir, state_dir=str(state_dir))
    config.torrent_checking.enabled = False
    config.ipv8.enabled = False
    config.ipv8.walk_scaling_enabled = False
    config.ipv8.rust_endpoint = False
    config.discovery_community.enabled = False
    config.libtorrent.enabled = False
    config.libtorrent.dht_readiness_timeout = 0
    config.tunnel_community.enabled = False
    config.content_discovery_community.enabled = False
    config.dht.enabled = False
    config.libtorrent.dht = False
    config.chant.enabled = False
    config.resource_monitor.enabled = False
    config.bootstrap.enabled = False
    return config


@pytest.fixture
def state_dir(tmp_path):
    state_dir = tmp_path / 'state_dir'
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def mock_dlmgr(state_dir):
    download_manager = MagicMock()
    download_manager.config = LibtorrentSettings()
    download_manager.shutdown = lambda: succeed(None)
    checkpoints_dir = state_dir / 'dlcheckpoints'
    checkpoints_dir.mkdir()
    download_manager.get_checkpoint_dir = lambda: checkpoints_dir
    download_manager.state_dir = state_dir
    download_manager.get_downloads = lambda: []
    download_manager.checkpoints_count = 1
    download_manager.checkpoints_loaded = 1
    download_manager.all_checkpoints_are_loaded = True
    return download_manager


@pytest.fixture
async def video_tdef():
    return await TorrentDef.load(TESTS_DATA_DIR / 'video.avi.torrent')


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
    upload = await dlmgr.start_download(tdef=video_tdef, config=dscfg_seed)
    await upload.wait_for_status(DownloadStatus.SEEDING)
    yield dlmgr
    await dlmgr.shutdown()


@pytest.fixture
def metadata_store(tmp_path):
    mds = MetadataStore(db_filename=tmp_path / 'test.db',
                        channels_dir=tmp_path / 'channels',
                        my_key=TEST_PERSONAL_KEY,
                        disable_sync=True)
    yield mds
    mds.shutdown()


@pytest.fixture
def tribler_db():
    db = TriblerDatabase()
    yield db
    db.shutdown()


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
