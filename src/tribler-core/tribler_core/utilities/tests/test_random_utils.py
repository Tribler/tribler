from tribler_core.utilities.random_utils import random_infohash, random_string, random_utf8_string


def test_random_string():
    test_string = random_string()
    assert test_string
    assert len(test_string) == 6

    text_length = 16
    test_string2 = random_string(size=text_length)
    assert len(test_string2) == text_length


def test_random_utf8_string():
    test_string = random_utf8_string()
    assert test_string
    assert isinstance(test_string, str)
    assert len(test_string) == 6

    text_length = 16
    test_string2 = random_utf8_string(length=text_length)
    assert isinstance(test_string, str)
    assert len(test_string2) == text_length


def test_random_infohash():
    test_infohash = random_infohash()
    assert test_infohash
    assert isinstance(test_infohash, bytes)
    assert len(test_infohash) == 20
