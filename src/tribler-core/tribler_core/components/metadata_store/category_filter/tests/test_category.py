import pytest

from tribler_core.components.metadata_store.category_filter.category import Category, cmp_rank
from tribler_core.components.metadata_store.category_filter.family_filter import XXXFilter


@pytest.fixture(name="xxx_filter")
def fixture_xxx_filter():
    return XXXFilter()


@pytest.fixture(name="category_filter")
def fixture_category_filter(xxx_filter):
    return Category(xxx_filter=xxx_filter)


def test_get_category_names(category_filter):
    assert len(category_filter.category_info) == 10


def test_calculate_category_multi_file(category_filter):
    torrent_info = {b"info": {b"files": [{b"path": [b"my", b"path", b"video.avi"], b"length": 1234}]},
                    b"announce": b"http://tracker.org", b"comment": b"lorem ipsum"}
    assert category_filter.calculateCategory(torrent_info, "my torrent") == "VideoClips"


def test_calculate_category_single_file(category_filter):
    torrent_info = {b"info": {b"name": b"my_torrent", b"length": 1234},
                    b"announce-list": [[b"http://tracker.org"]], b"comment": b"lorem ipsum"}
    assert category_filter.calculateCategory(torrent_info, "my torrent"), "other"


def test_calculate_category_xxx(category_filter, xxx_filter):
    xxx_filter.xxx_terms.add("term1")
    torrent_info = {b"info": {b"name": b"term1", b"length": 1234},
                    b"announce-list": [[b"http://tracker.org"]], b"comment": b"lorem ipsum"}
    assert category_filter.calculateCategory(torrent_info, "my torrent") == "xxx"


def test_calculate_category_invalid_announce_list(category_filter, xxx_filter):
    xxx_filter.xxx_terms.add("term1")
    torrent_info = {b"info": {b"name": b"term1", b"length": 1234},
                    b"announce-list": [[]], b"comment": b"lorem ipsum"}
    assert category_filter.calculateCategory(torrent_info, "my torrent") == "xxx"


def test_cmp_rank():
    assert cmp_rank({'bla': 3}, {'bla': 4}) == 1
    assert cmp_rank({'rank': 3}, {'bla': 4}) == -1
