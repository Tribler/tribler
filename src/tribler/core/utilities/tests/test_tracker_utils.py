import pytest

from tribler_core.utilities.tracker_utils import (
    MalformedTrackerURLException,
    get_uniformed_tracker_url,
    parse_tracker_url,
)


def test_uniform_scheme_correct_udp():
    result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com:80")
    assert result == "udp://tracker.openbittorrent.com:80"


def test_uniform_scheme_correct_http():
    result = get_uniformed_tracker_url("http://torrent.ubuntu.com:6969/announce")
    assert result == "http://torrent.ubuntu.com:6969/announce"


def test_uniform_scheme_correct_http_training_slash():
    result = get_uniformed_tracker_url("http://torrent.ubuntu.com:6969/announce/")
    assert result == "http://torrent.ubuntu.com:6969/announce"


def test_uniform_scheme_unknown():
    result = get_uniformed_tracker_url("unknown://tracker.openbittorrent.com/announce")
    assert not result


def test_uniform_http_no_path():
    result = get_uniformed_tracker_url("http://tracker.openbittorrent.com")
    assert not result


def test_uniform_udp_no_port():
    result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com")
    assert not result


def test_uniform_udp_remove_path():
    result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com:6969/announce")
    assert result == "udp://tracker.openbittorrent.com:6969"


def test_uniform_http_no_path_nbsp():
    result = get_uniformed_tracker_url("http://google.nl\xa0")
    assert not result


def test_uniform_http_default_port():
    result = get_uniformed_tracker_url("http://torrent.ubuntu.com/announce")
    assert result == "http://torrent.ubuntu.com/announce"


def test_uniform_http_default_port_given():
    result = get_uniformed_tracker_url("http://torrent.ubuntu.com:80/announce")
    assert result == "http://torrent.ubuntu.com/announce"


def test_uniform_trailing_zero_hex():
    result = get_uniformed_tracker_url("udp://tracker.1337x.org:80\x00")
    assert result == "udp://tracker.1337x.org:80"


def test_uniform_trailing_hex():
    result = get_uniformed_tracker_url("udp://tracker.1337x.org:80\xff")
    assert not result


def test_uniform_bad_urlenc():
    result = get_uniformed_tracker_url("http://btjunkie.org/?do=upload")
    assert not result


def test_uniform_empty():
    result = get_uniformed_tracker_url('')
    assert not result


def test_skip_truncated_url():
    result = get_uniformed_tracker_url("http://tracker.1337x.org:80/anno...")
    assert not result


def test_skip_wrong_url_scheme():
    result = get_uniformed_tracker_url("wss://tracker.1337x.org:80/announce")
    assert not result


def test_skip_value_error():
    result = get_uniformed_tracker_url("ftp://tracker.1337\xffx.org:80/announce")
    assert not result


def test_skip_split_error():
    result = get_uniformed_tracker_url(";")
    assert not result


def test_parse_scheme_correct_udp():
    result = parse_tracker_url("udp://tracker.openbittorrent.com:80")
    assert result == ("udp", ("tracker.openbittorrent.com", 80), '')


def test_parse_scheme_correct_http():
    result = parse_tracker_url("http://torrent.ubuntu.com:6969/announce")
    assert result == ("http", ("torrent.ubuntu.com", 6969), "/announce")


def test_parse_scheme_unknown():
    with pytest.raises(MalformedTrackerURLException):
        parse_tracker_url("unknown://ipv6.torrent.ubuntu.com:6969/announce")


def test_parse_bad_url():
    with pytest.raises(MalformedTrackerURLException):
        parse_tracker_url("http://foo.com:6969/announce( %(")


def test_parse_scheme():
    with pytest.raises(MalformedTrackerURLException):
        parse_tracker_url("http://torrent.ubuntu.com:80")


def test_parse_http_no_announce_path():
    with pytest.raises(MalformedTrackerURLException):
        parse_tracker_url("unknown://ipv6.torrent.ubuntu.com:6969")


def test_parse_udp_no_port():
    with pytest.raises(MalformedTrackerURLException):
        parse_tracker_url("udp://tracker.openbittorrent.com")


def test_parse_http_no_port():
    result = parse_tracker_url("http://tracker.openbittorrent.com/announce")
    assert result == ("http", ("tracker.openbittorrent.com", 80), "/announce")


def test_parse_http_non_standard_port():
    result = parse_tracker_url("http://ipv6.torrent.ubuntu.com:6969/announce")
    assert result == ("http", ("ipv6.torrent.ubuntu.com", 6969), "/announce")
