from unittest.mock import Mock

from ipv8.util import succeed

import pytest

from tribler_core.restapi.base_api_test import do_request
from tribler_core.tests.tools.common import TESTS_DATA_DIR


@pytest.mark.asyncio
async def test_create_torrent(enable_api, tmpdir, mock_dlmgr, session):
    """
    Testing whether the API returns a proper base64 encoded torrent
    """
    def fake_create_torrent_file(*_, **__):
        with open(TESTS_DATA_DIR / "bak_single.torrent", mode='rb') as torrent_file:
            encoded_metainfo = torrent_file.read()
        return succeed({"metainfo": encoded_metainfo, "base_dir": str(tmpdir)})

    session.dlmgr.create_torrent_file = fake_create_torrent_file
    session.dlmgr.start_download = start_download = Mock()

    torrent_path = tmpdir / "video.avi.torrent"
    post_data = {
        "files": [str(torrent_path / "video.avi"),
                  str(torrent_path / "video.avi.torrent")],
        "description": "Video of my cat",
        "trackers": "http://localhost/announce",
        "name": "test_torrent",
        "export_dir": str(tmpdir)
    }
    response_dict = await do_request(session, 'createtorrent?download=1', expected_code=200, request_type='POST',
                                     post_data=post_data)
    assert response_dict["torrent"]
    assert start_download.call_args[1]['config'].get_hops() == session.config.get_default_number_hops()

@pytest.mark.asyncio
async def test_create_torrent_io_error(enable_api, mock_dlmgr, session):
    """
    Testing whether the API returns a formatted 500 error if IOError is raised
    """
    def fake_create_torrent_file(*_, **__):
        raise IOError("test")

    session.dlmgr.create_torrent_file = fake_create_torrent_file

    post_data = {
        "files": ["non_existing_file.avi"]
    }
    error_response = await do_request(session, 'createtorrent', expected_code=500, request_type='POST',
                                      post_data=post_data)
    expected_response = {
        "error": {
            "code": "OSError",
            "handled": True,
            "message": "test"
        }
    }
    assert expected_response == error_response


@pytest.mark.asyncio
async def test_create_torrent_missing_files_parameter(enable_api, session):
    expected_json = {"error": "files parameter missing"}
    await do_request(session, 'createtorrent', expected_code=400, expected_json=expected_json, request_type='POST')
