import pytest

from tribler.core.utilities.tracker_utils import (
    MalformedTrackerURLException,
    get_uniformed_tracker_url,
    parse_tracker_url,
)

TRACKER_HOST = 'tracker.example.com'

EXPECTED_UNIFORM_URLS = [
    (f'udp://{TRACKER_HOST}:80', f'udp://{TRACKER_HOST}:80'),  # Proper UDP URL
    (f'udp://{TRACKER_HOST}', None),  # UDP no port
    (f'udp://{TRACKER_HOST}:6969/announce', f'udp://{TRACKER_HOST}:6969'),  # UDP remove path
    (f'udp://{TRACKER_HOST}:80\x00', f'udp://{TRACKER_HOST}:80'),  # Trailing zero hex
    (f'udp://{TRACKER_HOST}:80\xff', None),  # Trailing non-zero hex

    (f'http://{TRACKER_HOST}:6969/announce', f'http://{TRACKER_HOST}:6969/announce'),  # Correct HTTP URL
    (f'http://{TRACKER_HOST}:6969/announce/', f'http://{TRACKER_HOST}:6969/announce'),  # Trailing /
    (f'http://{TRACKER_HOST}', None),  # HTTP no path
    (f'http://{TRACKER_HOST}\xa0', None),  # HTTP no path nbsp
    (f'http://{TRACKER_HOST}/announce', f'http://{TRACKER_HOST}/announce'),  # HTTP default port
    (f'http://{TRACKER_HOST}:80/announce', f'http://{TRACKER_HOST}/announce'),  # HTTP default port given
    (f'http://{TRACKER_HOST}/?do=upload', None),  # Bad URL encoding
    (f'http://{TRACKER_HOST}:80/anno...', None),  # Truncated URL

    (f'https://{TRACKER_HOST}/announce', f'https://{TRACKER_HOST}/announce'),  # HTTPS default port
    (f'https://{TRACKER_HOST}:443/announce', f'https://{TRACKER_HOST}/announce'),  # HTTPS default port given

    (f'unknown://{TRACKER_HOST}/announce', None),  # Unknown scheme
    (f'wss://{TRACKER_HOST}:80/announce', None),  # Wrong URL scheme
    ('ftp://tracker.examp\xffle.org:80/announce', None),  # Wrong URL scheme
    (';', None),  # Split error
    ('', None),  # Empty URL
]


@pytest.mark.parametrize("given_url, expected_uniform_url", EXPECTED_UNIFORM_URLS)
def test_get_uniformed_tracker_url(given_url, expected_uniform_url):
    uniform_url = get_uniformed_tracker_url(given_url)
    assert uniform_url == expected_uniform_url


PARSED_TRACKER_URLS = [
    # UDP with port
    (f'udp://{TRACKER_HOST}:80', ("udp", (f"{TRACKER_HOST}", 80), '')),
    # HTTP(S) with port
    (f'http://{TRACKER_HOST}:6969/announce', ("http", (f"{TRACKER_HOST}", 6969), "/announce")),
    (f'https://{TRACKER_HOST}:6969/announce', ("https", (f"{TRACKER_HOST}", 6969), "/announce")),
    # HTTP(S) no port
    (f'http://{TRACKER_HOST}/announce', ("http", (f"{TRACKER_HOST}", 80), "/announce")),
    (f'https://{TRACKER_HOST}/announce', ("https", (f"{TRACKER_HOST}", 443), "/announce")),
    # HTTP(S) non-standard port
    (f'http://ipv6.{TRACKER_HOST}:6969/announce', ("http", (f"ipv6.{TRACKER_HOST}", 6969), "/announce")),
    (f'https://ipv6.{TRACKER_HOST}:6969/announce', ("https", (f"ipv6.{TRACKER_HOST}", 6969), "/announce"))
]


@pytest.mark.parametrize("given_url, expected_parsed_url_tuple", PARSED_TRACKER_URLS)
def test_parse_tracker_url(given_url, expected_parsed_url_tuple):
    parsed_url_tuple = parse_tracker_url(given_url)
    assert parsed_url_tuple == expected_parsed_url_tuple


PARSED_TRACKER_URLS_WITH_FAILURE = [
    f'unknown://ipv6.{TRACKER_HOST}:6969/announce',  # Unknown scheme
    f'http://{TRACKER_HOST}:6969/announce( %(',  # Bad URL
    f'https://{TRACKER_HOST}:6969/announce( %(',  # Bad URL
    f'unknown://{TRACKER_HOST}:80',  # Unknown scheme, no announce path
    f'http://ipv6.{TRACKER_HOST}:6969',  # HTTP no announce path
    f'https://ipv6.{TRACKER_HOST}:6969',  # HTTPS no announce path
    f'udp://{TRACKER_HOST}',  # UDP no port
]


@pytest.mark.parametrize("given_url", PARSED_TRACKER_URLS_WITH_FAILURE)
def test_parse_tracker_url_with_error(given_url):
    with pytest.raises(MalformedTrackerURLException):
        parse_tracker_url(given_url)
