import pytest

from tribler.core.config.tribler_config import TriblerConfig
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
