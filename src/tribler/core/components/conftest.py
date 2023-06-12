from unittest.mock import MagicMock

import pytest
from ipv8.util import succeed

from tribler.core.components.libtorrent.settings import LibtorrentSettings
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.utilities.path_util import Path


# pylint: disable=redefined-outer-name

@pytest.fixture
def tribler_config(tmp_path) -> TriblerConfig:
    state_dir = Path(tmp_path) / "dot.Tribler"
    download_dir = Path(tmp_path) / "TriblerDownloads"
    config = TriblerConfig(state_dir=state_dir)
    config.download_defaults.put_path_as_relative('saveas', download_dir, state_dir=str(state_dir))
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
def video_tdef():
    return TorrentDef.load(TESTS_DATA_DIR / 'video.avi.torrent')
