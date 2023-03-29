from binascii import unhexlify
from unittest.mock import patch, AsyncMock

import pytest

from tribler.core.components.torrent_checker.torrent_checker.trackers import TrackerException
from tribler.core.components.torrent_checker.torrent_checker.trackers.http import HttpTracker

SAMPLE_INFOHASH = unhexlify("2c6b6858d61da9543d4231a71db4b1c9264b0685")  # Ubuntu 20.04
SAMPLE_VALID_TRACKER_RESPONSE = b'd5:filesd20:,khX\xd6\x1d\xa9T=B1\xa7\x1d\xb4\xb1\xc9&K\x06\x85d8' \
                          b':completei5e10:downloadedi0e10:incompletei0eeee'
SAMPLE_INVALID_TRACKER_RESPONSE = b'd8:announce36:http://tracker.example.com/invalid\n17' \
                                  b':failure reason23:invalid announce url - 1e'


async def test_get_tracker_response():
    tracker_url = 'http://tracker.example.com/announce'

    with patch('aiohttp.ClientSession') as mock_session:
        http_tracker = HttpTracker()
        http_tracker._get_url_response = AsyncMock(return_value=SAMPLE_VALID_TRACKER_RESPONSE)
        response = await http_tracker.get_tracker_response(tracker_url, [SAMPLE_INFOHASH], timeout=0.01)
        assert response.url == tracker_url
        assert len(response.torrent_health_list) == 1


def test_process_body_invalid_response():
    http_tracker = HttpTracker()
    with pytest.raises(TrackerException, match="Invalid bencoded response"):
        http_tracker._process_body(b'invalid bencoded response')


def test_process_body_no_response():
    http_tracker = HttpTracker()
    with pytest.raises(TrackerException, match="No response body"):
        http_tracker._process_body(None)


def test_process_body_failure():
    http_tracker = HttpTracker()
    with pytest.raises(TrackerException, match="Invalid bencoded response"):
        http_tracker._process_body(SAMPLE_INVALID_TRACKER_RESPONSE)


def test_process_body_success():
    http_tracker = HttpTracker()
    health_list = http_tracker._process_body(SAMPLE_VALID_TRACKER_RESPONSE)

    assert len(health_list) == 1
    assert health_list[0].infohash == SAMPLE_INFOHASH
    assert health_list[0].seeders == 5
    assert health_list[0].leechers == 0
