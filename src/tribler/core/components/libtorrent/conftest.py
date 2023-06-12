import pytest

from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig


# pylint: disable=redefined-outer-name


@pytest.fixture
def download_config():
    return DownloadConfig()
