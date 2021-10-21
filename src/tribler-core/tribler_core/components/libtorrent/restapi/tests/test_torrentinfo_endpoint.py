import json
import shutil
import urllib
from binascii import unhexlify
from unittest.mock import Mock, patch
from urllib.parse import quote_plus, unquote_plus

from aiohttp.web_app import Application

from ipv8.util import succeed

import pytest

from tribler_common.simpledefs import NTFY

from tribler_core.components.libtorrent.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from tribler_core.components.libtorrent.torrentdef import TorrentDef
from tribler_core.components.metadata_store.db.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.rest_manager import error_middleware
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TESTS_DIR, TORRENT_UBUNTU_FILE, UBUNTU_1504_INFOHASH
from tribler_core.utilities.unicode import hexlify

SAMPLE_CHANNEL_FILES_DIR = TESTS_DIR / "data" / "sample_channel"


@pytest.fixture
def endpoint():
    endpoint = TorrentInfoEndpoint()
    return endpoint


@pytest.fixture
def rest_api(loop, aiohttp_client, endpoint):  # pylint: disable=unused-argument
    app = Application(middlewares=[error_middleware])
    app.add_subapp('/torrentinfo', endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


async def test_get_torrentinfo(mock_dlmgr, tmp_path, rest_api, endpoint):
    """
    Testing whether the API returns a correct dictionary with torrent info.
    """
    endpoint.download_manager = mock_dlmgr

    shutil.copyfile(TORRENT_UBUNTU_FILE, tmp_path / 'ubuntu.torrent')

    def verify_valid_dict(json_data):
        metainfo_dict = json.loads(unhexlify(json_data['metainfo']))
        # FIXME: This check is commented out because json.dump garbles pieces binary data during transfer.
        # To fix it, we must switch to some encoding scheme that is able to encode and decode raw binary
        # fields in the dicts.
        # However, for this works fine at the moment because we never use pieces data in the GUI.
        # assert TorrentDef.load_from_dict(metainfo_dict)
        assert 'info' in metainfo_dict

    def path_to_url(path):
        return urllib.request.pathname2url(str(path))

    mock_dlmgr.downloads = {}
    mock_dlmgr.metainfo_requests = {}
    mock_dlmgr.get_channel_downloads = lambda: []
    mock_dlmgr.shutdown = lambda: succeed(None)
    mock_dlmgr.notifier = Mock()

    await do_request(rest_api, 'torrentinfo', expected_code=400)
    await do_request(rest_api, 'torrentinfo?uri=def', expected_code=400)

    path = "file:" + path_to_url(TESTS_DATA_DIR / "bak_single.torrent")
    verify_valid_dict(await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200))

    # Corrupt file
    path = "file:" + path_to_url(TESTS_DATA_DIR / "test_rss.xml")
    await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=500)

    path = "http://localhost:1234/ubuntu.torrent"

    async def mock_http_query(*_):
        with open(tmp_path / "ubuntu.torrent", 'rb') as f:
            return f.read()

    with patch("tribler_core.components.libtorrent.restapi.torrentinfo_endpoint.query_http_uri", new=mock_http_query):
        verify_valid_dict(await do_request(rest_api, f'torrentinfo?uri={quote_plus(path)}', expected_code=200))

    path = quote_plus(f'magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}'
                      f'&dn=test torrent&tr=http://ubuntu.org/ann')

    hops_list = []

    with open(TESTS_DATA_DIR / "ubuntu-15.04-desktop-amd64.iso.torrent", mode='rb') as torrent_file:
        torrent_data = torrent_file.read()
        tdef = TorrentDef.load_from_memory(torrent_data)
    metainfo_dict = tdef_to_metadata_dict(TorrentDef.load_from_memory(torrent_data))

    def get_metainfo(infohash, timeout=20, hops=None, url=None):
        if hops is not None:
            hops_list.append(hops)
        assert url
        assert url == unquote_plus(path)
        return succeed(tdef.get_metainfo())

    mock_dlmgr.get_metainfo = get_metainfo
    verify_valid_dict(await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200))

    path = 'magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1'  # No infohash
    await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=400)

    path = quote_plus(f"magnet:?xt=urn:btih:{'a' * 40}&dn=test torrent")
    mock_dlmgr.get_metainfo = lambda *_, **__: succeed(None)
    await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=500)

    # Ensure that correct torrent metadata was sent through notifier (to MetadataStore)
    mock_dlmgr.notifier.notify.assert_called_with(NTFY.TORRENT_METADATA_ADDED, metainfo_dict)

    mock_dlmgr.get_metainfo = get_metainfo
    verify_valid_dict(await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200))

    await do_request(rest_api, f'torrentinfo?uri={path}&hops=0', expected_code=200)
    assert [0] == hops_list

    await do_request(rest_api, f'torrentinfo?uri={path}&hops=foo', expected_code=400)

    path = 'http://fdsafksdlafdslkdksdlfjs9fsafasdf7lkdzz32.n38/324.torrent'
    await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=500)

    mock_download = Mock()
    path = quote_plus(f'magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}&dn=test torrent')
    mock_dlmgr.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    result = await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200)
    assert result["download_exists"]

    # Check that we do not return "downloads_exists" if the download is metainfo only download
    mock_dlmgr.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    mock_dlmgr.metainfo_requests = {UBUNTU_1504_INFOHASH: [mock_download]}
    result = await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200)
    assert not result["download_exists"]

    # Check that we return "downloads_exists" if there is a metainfo download for the infohash,
    # but there is also a regular download for the same infohash
    mock_dlmgr.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    mock_dlmgr.metainfo_requests = {UBUNTU_1504_INFOHASH: [Mock()]}
    result = await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=200)
    assert result["download_exists"]

async def test_on_got_invalid_metainfo(mock_dlmgr, rest_api):
    """
    Test whether the right operations happen when we receive an invalid metainfo object
    """
    def get_metainfo(*_, **__):
        return succeed("abcd")

    mock_dlmgr.get_metainfo = get_metainfo
    mock_dlmgr.shutdown = lambda: succeed(None)
    mock_dlmgr.shutdown_downloads = lambda: succeed(None)
    mock_dlmgr.checkpoint_downloads = lambda: succeed(None)
    path = f"magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}&dn={quote_plus('test torrent')}"

    res = await do_request(rest_api, f'torrentinfo?uri={path}', expected_code=500)
    assert "error" in res
