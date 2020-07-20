import pytest

from tribler_core.modules.category_filter.family_filter import XXXFilter
from tribler_core.modules.category_filter.l2_filter import is_forbidden


@pytest.fixture
def family_filter():
    family_filter = XXXFilter()
    family_filter.xxx_terms.add("term1")
    family_filter.xxx_terms.add("term2")
    family_filter.xxx_searchterms.add("term3")
    return family_filter


def test_is_xxx(family_filter):
    assert not family_filter.isXXX(None)
    assert family_filter.isXXX("term1")
    assert not family_filter.isXXX("term0")
    assert family_filter.isXXX("term3")


def test_is_xxx_term(family_filter):
    assert family_filter.isXXXTerm("term1es")
    assert not family_filter.isXXXTerm("term0es")
    assert family_filter.isXXXTerm("term1s")
    assert not family_filter.isXXXTerm("term0n")


def test_xxx_torrent_metadata_dict(family_filter):
    d = {
        "title": "XXX",
        "tags": "",
        "tracker": "http://sooo.dfd/announce"
    }
    assert family_filter.isXXXTorrentMetadataDict(d)


def test_l2_filter():
    assert is_forbidden("9yo ponies")
    assert is_forbidden("12yo ponies")
    assert not is_forbidden("18yo ponies")
