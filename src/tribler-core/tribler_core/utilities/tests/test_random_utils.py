from tribler_core.utilities.random_utils import random_infohash


def test_random_infohash():
    test_infohash = random_infohash()
    assert test_infohash
    assert isinstance(test_infohash, bytes)
    assert len(test_infohash) == 20
