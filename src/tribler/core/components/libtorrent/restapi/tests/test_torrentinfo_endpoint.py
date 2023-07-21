import json
import shutil
from asyncio.exceptions import TimeoutError as AsyncTimeoutError
from binascii import unhexlify
from ssl import SSLError
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from urllib.parse import quote_plus, unquote_plus

import pytest
from aiohttp import ServerConnectionError, ClientResponseError, ClientConnectorError
from ipv8.util import succeed

from tribler.core import notifications
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from tribler.core.components.libtorrent.settings import DownloadDefaultsSettings, LibtorrentSettings
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.metadata_store.db.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.components.restapi.rest.rest_endpoint import HTTP_INTERNAL_SERVER_ERROR
from tribler.core.tests.tools.common import TESTS_DATA_DIR, TESTS_DIR, TORRENT_UBUNTU_FILE, UBUNTU_1504_INFOHASH
from tribler.core.utilities.rest_utils import path_to_url
from tribler.core.utilities.unicode import hexlify

SAMPLE_CHANNEL_FILES_DIR = TESTS_DIR / "data" / "sample_channel"


# pylint: disable=redefined-outer-name

@pytest.fixture
def download_manager(state_dir):
    dlmgr = MagicMock()
    dlmgr.config = LibtorrentSettings()
    dlmgr.download_defaults = DownloadDefaultsSettings()
    dlmgr.shutdown = lambda: succeed(None)
    checkpoints_dir = state_dir / 'dlcheckpoints'
    checkpoints_dir.mkdir()
    dlmgr.get_checkpoint_dir = lambda: checkpoints_dir
    dlmgr.state_dir = state_dir
    dlmgr.get_downloads = lambda: []
    dlmgr.downloads = {}
    dlmgr.metainfo_requests = {}
    dlmgr.get_channel_downloads = lambda: []
    dlmgr.shutdown = lambda: succeed(None)
    dlmgr.notifier = MagicMock()
    return dlmgr


@pytest.fixture
def endpoint(download_manager: DownloadManager):
    return TorrentInfoEndpoint(download_manager)


async def test_get_torrentinfo_escaped_characters(tmp_path, rest_api):
    # test for the bug fix: https://github.com/Tribler/tribler/issues/6700
    source = TORRENT_UBUNTU_FILE
    destination = tmp_path / 'ubuntu%20%21 15.04.torrent'
    shutil.copyfile(source, destination)
    uri = path_to_url(destination)
    response = await do_request(rest_api, url='torrentinfo', params={'uri': uri}, expected_code=200)

    assert 'metainfo' in response


async def test_get_torrentinfo(tmp_path, rest_api, download_manager: DownloadManager):
    """
    Testing whether the API returns a correct dictionary with torrent info.
    """

    def _path(file):
        return path_to_url(TESTS_DATA_DIR / file)

    shutil.copyfile(TORRENT_UBUNTU_FILE, tmp_path / 'ubuntu.torrent')

    def verify_valid_dict(json_data):
        metainfo_dict = json.loads(unhexlify(json_data['metainfo']))
        assert 'info' in metainfo_dict

    url = 'torrentinfo'
    await do_request(rest_api, url, expected_code=400)
    await do_request(rest_api, url, params={'uri': 'def'}, expected_code=400)

    response = await do_request(rest_api, url, params={'uri': _path('bak_single.torrent')}, expected_code=200)
    verify_valid_dict(response)

    # Corrupt file
    await do_request(rest_api, url, params={'uri': _path('test_rss.xml')}, expected_code=500)

    # Non-existing file
    await do_request(rest_api, url, params={'uri': _path('non_existing.torrent')}, expected_code=500)

    path = "http://localhost:1234/ubuntu.torrent"

    async def mock_http_query(*_):
        with open(tmp_path / "ubuntu.torrent", 'rb') as f:
            return f.read()

    with patch("tribler.core.components.libtorrent.restapi.torrentinfo_endpoint.query_http_uri", new=mock_http_query):
        verify_valid_dict(await do_request(rest_api, url, params={'uri': path}, expected_code=200))

    path = quote_plus(f'magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}'
                      f'&dn=test torrent&tr=http://ubuntu.org/ann')

    hops_list = []

    with open(TESTS_DATA_DIR / "ubuntu-15.04-desktop-amd64.iso.torrent", mode='rb') as torrent_file:
        torrent_data = torrent_file.read()
        tdef = TorrentDef.load_from_memory(torrent_data)
    metainfo_dict = tdef_to_metadata_dict(TorrentDef.load_from_memory(torrent_data))

    async def get_metainfo(infohash, timeout=20, hops=None, url=None):  # pylint: disable=unused-argument
        if hops is not None:
            hops_list.append(hops)
        assert url
        assert url == unquote_plus(path)
        return tdef.get_metainfo()

    download_manager.get_metainfo = get_metainfo
    verify_valid_dict(await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200))

    path = 'magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1'  # No infohash
    await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=400)

    path = quote_plus(f"magnet:?xt=urn:btih:{'a' * 40}&dn=test torrent")
    download_manager.get_metainfo = lambda *_, **__: succeed(None)
    await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=500)

    # Ensure that correct torrent metadata was sent through notifier (to MetadataStore)
    download_manager.notifier[notifications.torrent_metadata_added].assert_called_with(metainfo_dict)

    download_manager.get_metainfo = get_metainfo
    verify_valid_dict(await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200))

    await do_request(rest_api, f'torrentinfo?uri={path}&hops=0', expected_code=200)
    assert [0] == hops_list

    await do_request(rest_api, f'torrentinfo?uri={path}&hops=foo', expected_code=400)

    path = 'http://fdsafksdlafdslkdksdlfjs9fsafasdf7lkdzz32.n38/324.torrent'
    await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=500)

    mock_download = MagicMock(
        stop=AsyncMock(),
        shutdown=AsyncMock()
    )
    path = quote_plus(f'magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}&dn=test torrent')
    download_manager.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    result = await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200)
    assert result["download_exists"]

    # Check that we do not return "downloads_exists" if the download is metainfo only download
    download_manager.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    download_manager.metainfo_requests = {UBUNTU_1504_INFOHASH: [mock_download]}
    result = await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200)
    assert not result["download_exists"]

    # Check that we return "downloads_exists" if there is a metainfo download for the infohash,
    # but there is also a regular download for the same infohash
    download_manager.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    download_manager.metainfo_requests = {UBUNTU_1504_INFOHASH: [MagicMock()]}
    result = await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200)
    assert result["download_exists"]


async def test_on_got_invalid_metainfo(rest_api):
    """
    Test whether the right operations happen when we receive an invalid metainfo object
    """

    path = f"magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}&dn={quote_plus('test torrent')}"
    res = await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=500)
    assert "error" in res

# These are the exceptions that are handled by torrent info endpoint when querying an HTTP URI.
caught_exceptions = [
        ServerConnectionError(),
        ClientResponseError(Mock(), Mock()),
        SSLError(),
        ClientConnectorError(Mock(), Mock()),
        AsyncTimeoutError()
    ]


@patch("tribler.core.components.libtorrent.restapi.torrentinfo_endpoint.query_http_uri")
@pytest.mark.parametrize("exception", caught_exceptions)
async def test_torrentinfo_endpoint_timeout_error(mocked_query_http_uri: AsyncMock, exception: Exception):
    # Test that in the case of exceptions related to querying HTTP URI specified in this tests,
    # no exception is raised.
    mocked_query_http_uri.side_effect = exception

    endpoint = TorrentInfoEndpoint(MagicMock())
    request = MagicMock(query={'uri': 'http://some_torrent_url'})

    info = await endpoint.get_torrent_info(request)

    assert info.status == HTTP_INTERNAL_SERVER_ERROR
