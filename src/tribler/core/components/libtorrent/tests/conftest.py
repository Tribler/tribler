import pytest

from tribler_core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo


@pytest.fixture
def test_tdef_no_metainfo(state_dir):
    tdef = TorrentDefNoMetainfo(b"1" * 20, "test")
    return tdef


@pytest.fixture
def tdef():
    return TorrentDef()


@pytest.fixture
def mock_download_config(mocker, test_download):
    return mocker.patch.object(test_download, 'config')


@pytest.fixture
def mock_download_state(mocker, test_download):
    return mocker.patch.object(test_download, 'get_state')
