import pytest

from tribler.core.components.libtorrent.settings import DownloadDefaultsSettings, LibtorrentSettings, SeedingMode
from tribler.core.utilities.network_utils import NetworkUtils


def test_port_validation():
    assert LibtorrentSettings(port=-1)
    assert LibtorrentSettings(port=None)

    with pytest.raises(ValueError):
        LibtorrentSettings(port=-2)

    with pytest.raises(ValueError):
        LibtorrentSettings(port=NetworkUtils.MAX_PORT + 1)


async def test_proxy_type_validation():
    assert LibtorrentSettings(proxy_type=1)

    with pytest.raises(ValueError):
        LibtorrentSettings(proxy_type=-1)

    with pytest.raises(ValueError):
        LibtorrentSettings(proxy_type=6)


def test_number_hops_validation():
    assert DownloadDefaultsSettings(number_hops=1)

    with pytest.raises(ValueError):
        DownloadDefaultsSettings(number_hops=-1)

    with pytest.raises(ValueError):
        DownloadDefaultsSettings(number_hops=4)


def test_seeding_mode():
    assert DownloadDefaultsSettings(seeding_mode=SeedingMode.forever)

    with pytest.raises(ValueError):
        DownloadDefaultsSettings(seeding_mode='')
