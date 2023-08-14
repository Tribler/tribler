import pytest

from tribler.core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo


@pytest.fixture()
def test_tdef_no_metainfo(state_dir):
    return TorrentDefNoMetainfo(b"1" * 20, "test")


@pytest.fixture()
def tdef():
    return TorrentDef()
