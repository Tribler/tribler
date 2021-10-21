from unittest.mock import Mock

from aiohttp.web_app import Application

from ipv8.util import succeed

import pytest

from tribler_core.components.libtorrent.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from tribler_core.components.libtorrent.settings import DownloadDefaultsSettings
from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.rest_manager import error_middleware
from tribler_core.tests.tools.common import TESTS_DATA_DIR


@pytest.fixture
def endpoint():
    endpoint = CreateTorrentEndpoint()
    return endpoint


@pytest.fixture
def rest_api(loop, aiohttp_client, endpoint):  # pylint: disable=unused-argument
    app = Application(middlewares=[error_middleware])
    app.add_subapp('/createtorrent', endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


async def test_create_torrent(rest_api, tmp_path, endpoint):
    """
    Testing whether the API returns a proper base64 encoded torrent
    """

    def fake_create_torrent_file(*_, **__):
        with open(TESTS_DATA_DIR / "bak_single.torrent", mode='rb') as torrent_file:
            encoded_metainfo = torrent_file.read()
        return succeed({"metainfo": encoded_metainfo, "base_dir": str(tmp_path)})

    endpoint.download_manager = Mock()
    endpoint.download_manager.download_defaults = DownloadDefaultsSettings()
    endpoint.download_manager.create_torrent_file = fake_create_torrent_file
    endpoint.download_manager.start_download = start_download = Mock()

    torrent_path = tmp_path / "video.avi.torrent"
    post_data = {
        "files": [str(torrent_path / "video.avi"),
                  str(torrent_path / "video.avi.torrent")],
        "description": "Video of my cat",
        "trackers": "http://localhost/announce",
        "name": "test_torrent",
        "export_dir": str(tmp_path)
    }
    response_dict = await do_request(rest_api, 'createtorrent?download=1', expected_code=200, request_type='POST',
                                     post_data=post_data)
    assert response_dict["torrent"]
    assert start_download.call_args[1]['config'].get_hops() == DownloadDefaultsSettings(
    ).number_hops  # pylint: disable=unsubscriptable-object


async def test_create_torrent_io_error(rest_api, endpoint):
    """
    Testing whether the API returns a formatted 500 error if IOError is raised
    """

    def fake_create_torrent_file(*_, **__):
        raise OSError("test")

    endpoint.download_manager = Mock()
    endpoint.download_manager.create_torrent_file = fake_create_torrent_file

    post_data = {
        "files": ["non_existing_file.avi"]
    }
    error_response = await do_request(rest_api, 'createtorrent', expected_code=500, request_type='POST',
                                      post_data=post_data)
    expected_response = {
        "error": {
            "code": "OSError",
            "handled": True,
            "message": "test"
        }
    }
    assert expected_response == error_response


async def test_create_torrent_missing_files_parameter(rest_api):
    expected_json = {"error": "files parameter missing"}
    await do_request(rest_api, 'createtorrent', expected_code=400, expected_json=expected_json, request_type='POST')
