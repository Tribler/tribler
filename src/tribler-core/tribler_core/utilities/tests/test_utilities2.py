from aiohttp import ClientSession

import pytest

from tribler_core.utilities.utilities import (
    is_channel_public_key,
    is_infohash,
    is_simple_match_query,
    is_valid_url,
    parse_magnetlink,
)


def test_parse_magnetlink_lowercase():
    """
    Test if a lowercase magnet link can be parsed
    """
    _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:apctqfwnowubxzoidazgaj2ba6fs6juc')

    assert hashed == b"\x03\xc58\x16\xcdu\xa8\x1b\xe5\xc8\x182`'A\x07\x8b/&\x82"


def test_parse_magnetlink_uppercase():
    """
    Test if an uppercase magnet link can be parsed
    """
    _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:APCTQFWNOWUBXZOIDAZGAJ2BA6FS6JUC')

    assert hashed == b"\x03\xc58\x16\xcdu\xa8\x1b\xe5\xc8\x182`'A\x07\x8b/&\x82"


def test_valid_url():
    """ Test if the URL is valid """
    test_url = "http://anno nce.torrentsmd.com:8080/announce"
    assert not is_valid_url(test_url)

    test_url2 = "http://announce.torrentsmd.com:8080/announce "
    assert is_valid_url(test_url2)

    test_url3 = "http://localhost:1920/announce"
    assert is_valid_url(test_url3)

    test_url4 = "udp://localhost:1264"
    assert is_valid_url(test_url4)


@pytest.mark.asyncio
async def test_http_get_with_redirect(magnet_redirect_server):
    """
    Test if http_get is working properly if url redirects to a magnet link.
    """
    # Setup a redirect server which redirects to a magnet link
    magnet_link = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"

    test_url = "http://localhost:%d" % magnet_redirect_server
    async with ClientSession() as session:
        response = await session.get(test_url, allow_redirects=False)
    assert response.headers['Location'] == magnet_link


def test_simple_search_query():
    query = '"\xc1ubuntu"* AND "debian"*'
    assert is_simple_match_query(query)

    query = '""* AND "Petersburg"*'
    assert not is_simple_match_query(query)

    query2 = '"\xc1ubuntu"* OR "debian"*'
    assert not is_simple_match_query(query2)


def test_is_infohash():
    hex_40 = "DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    assert is_infohash(hex_40)

    hex_not_40 = "DC4B96CF85A85CEEDB8ADC4B96CF85"
    assert not is_infohash(hex_not_40)

    not_hex = "APPLE6CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    assert not is_infohash(not_hex)


def test_is_channel_public_key():
    hex_128 = "224b20c30b90d0fc7b2cf844f3d651de4481e21c7cdbbff258fa737d117d2c4ac7536de5cc93f4e9d5" \
              "1012a1ae0c46e9a05505bd017f0ecb78d8eec4506e848a"
    assert is_channel_public_key(hex_128)

    hex_not_128 = "DC4B96CF85A85CEEDB8ADC4B96CF85"
    assert not is_channel_public_key(hex_not_128)

    not_hex = "APPLE6CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    assert not is_channel_public_key(not_hex)
