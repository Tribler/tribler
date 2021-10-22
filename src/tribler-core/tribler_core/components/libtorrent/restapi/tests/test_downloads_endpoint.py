import collections
import os
from unittest.mock import Mock

from aiohttp.web_app import Application

from ipv8.util import fail, succeed

import pytest

from tribler_common.simpledefs import DLSTATUS_CIRCUITS, DLSTATUS_DOWNLOADING, DLSTATUS_EXIT_NODES, DLSTATUS_STOPPED

from tribler_core.components.libtorrent.download_manager.download_state import DownloadState
from tribler_core.components.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint, get_extended_status
from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.rest_manager import error_middleware
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
def rest_api(loop, aiohttp_client, mock_dlmgr, metadata_store):  # pylint: disable=unused-argument

    endpoint = DownloadsEndpoint()
    endpoint.download_manager = mock_dlmgr

    app = Application(middlewares=[error_middleware])
    app.add_subapp('/downloads', endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


def get_hex_infohash(tdef):
    return hexlify(tdef.get_infohash())


ExtendedStatusConfig = collections.namedtuple("ExtendedStatusConfig",
                                              ["hops", "candidates", "has_status"],
                                              defaults=[0, 0, True])


@pytest.fixture(name="mock_extended_status", scope="function")
def fixture_extended_status(request, mock_lt_status) -> int:
    """
    Fixture to provide an extended status for a DownloadState that uses a mocked TunnelCommunity and a mocked Download.

    Parameterization options:

     - Set Tribler's configured hops through the ``hops`` parameter.
     - Set the numer of exit candidates for the ``TunnelCommunity`` through the ``candidates`` parameter.
     - Set whether the DownloadState has a ``lt_status``, that is not ``None``, through the ``has_status``.

    :param request: PyTest's parameterization of this test, using ExtendedStatusConfig.
    :type request: SubRequest
    :param mock_lt_status: fixture that provides a mocked libtorrent status.
    """
    tunnel_community = Mock()
    download = Mock()
    state = DownloadState(download, mock_lt_status, None)
    download.get_state = lambda: state

    # Test parameterization
    download.config.get_hops = lambda: request.param.hops
    if not request.param.has_status:
        state.lt_status = None
    tunnel_community.get_candidates = lambda _: request.param.candidates

    return get_extended_status(tunnel_community, download)


@pytest.mark.parametrize("mock_extended_status",
                         [ExtendedStatusConfig(hops=0, candidates=0, has_status=True)],
                         indirect=["mock_extended_status"])
def test_get_extended_status_downloading_nohops_nocandidates(mock_extended_status):
    """
    Testing whether a non-anonymous download with state is considered "DOWNLOADING" without candidates.
    """
    assert mock_extended_status == DLSTATUS_DOWNLOADING


@pytest.mark.parametrize("mock_extended_status",
                         [ExtendedStatusConfig(hops=0, candidates=1, has_status=True)],
                         indirect=["mock_extended_status"])
def test_get_extended_status_downloading_nohops_candidates(mock_extended_status):
    """
    Testing whether a non-anonymous download with state is considered "DOWNLOADING" with candidates.
    """
    assert mock_extended_status == DLSTATUS_DOWNLOADING


@pytest.mark.parametrize("mock_extended_status",
                         [ExtendedStatusConfig(hops=1, candidates=0, has_status=True)],
                         indirect=["mock_extended_status"])
def test_get_extended_status_downloading_hops_nocandidates(mock_extended_status):
    """
    Testing whether an anonymous download with state is considered "DOWNLOADING" without candidates.
    """
    assert mock_extended_status == DLSTATUS_DOWNLOADING


@pytest.mark.parametrize("mock_extended_status",
                         [ExtendedStatusConfig(hops=1, candidates=1, has_status=True)],
                         indirect=["mock_extended_status"])
def test_get_extended_status_downloading_hops_candidates(mock_extended_status):
    """
    Testing whether an anonymous download with state is considered "DOWNLOADING" with candidates.
    """
    assert mock_extended_status == DLSTATUS_DOWNLOADING


@pytest.mark.parametrize("mock_extended_status",
                         [ExtendedStatusConfig(hops=0, candidates=0, has_status=False)],
                         indirect=["mock_extended_status"])
def test_get_extended_status_stopped(mock_extended_status):
    """
    Testing whether a non-anonymous download without state is considered "STOPPED" without candidates.
    """
    assert mock_extended_status == DLSTATUS_STOPPED


@pytest.mark.parametrize("mock_extended_status",
                         [ExtendedStatusConfig(hops=0, candidates=1, has_status=False)],
                         indirect=["mock_extended_status"])
def test_get_extended_status_stopped_hascandidates(mock_extended_status):
    """
    Testing whether a non-anonymous download without state is considered "STOPPED" with candidates.
    """
    assert mock_extended_status == DLSTATUS_STOPPED


@pytest.mark.parametrize("mock_extended_status",
                         [ExtendedStatusConfig(hops=1, candidates=0, has_status=False)],
                         indirect=["mock_extended_status"])
def test_get_extended_status_exit_nodes(mock_extended_status):
    """
    Testing whether an anonymous download without state is considered looking for "EXIT_NODES" without candidates.
    """
    assert mock_extended_status == DLSTATUS_EXIT_NODES


@pytest.mark.parametrize("mock_extended_status",
                         [ExtendedStatusConfig(hops=1, candidates=1, has_status=False)],
                         indirect=["mock_extended_status"])
def test_get_extended_status_circuits(mock_extended_status):
    """
    Testing whether an anonymous download without state is considered looking for "CIRCUITS" with candidates.
    """
    assert mock_extended_status == DLSTATUS_CIRCUITS


async def test_get_downloads_no_downloads(mock_dlmgr, rest_api):
    """
    Testing whether the API returns an empty list when downloads are fetched but no downloads are active
    """
    result = await do_request(rest_api, 'downloads?get_peers=1&get_pieces=1',
                              expected_code=200, expected_json={"downloads": []})
    assert result["downloads"] == []


async def test_get_downloads(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns the right download when a download is added
    """
    mock_dlmgr.get_downloads = lambda: [test_download]
    downloads = await do_request(rest_api, 'downloads?get_peers=1&get_pieces=1', expected_code=200)
    assert len(downloads["downloads"]) == 1


async def test_start_download_no_uri(rest_api):
    """
    Testing whether an error is returned when we start a torrent download and do not pass any URI
    """
    await do_request(rest_api, 'downloads', expected_code=400, request_type='PUT')


async def test_start_download_bad_params(rest_api):
    """
    Testing whether an error is returned when we start a torrent download and pass wrong data
    """
    post_data = {'anon_hops': 1, 'safe_seeding': 0, 'uri': 'abcd'}
    await do_request(rest_api, 'downloads', expected_code=400, request_type='PUT', post_data=post_data)


async def test_start_download_from_file(test_download, mock_dlmgr, rest_api):
    """
    Testing whether we can start a download from a file
    """
    mock_dlmgr.start_download_from_uri = lambda *_, **__: succeed(test_download)

    post_data = {'uri': f"file:{TESTS_DATA_DIR / 'video.avi.torrent'}"}
    expected_json = {'started': True, 'infohash': 'c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5'}
    await do_request(rest_api, 'downloads', expected_code=200, request_type='PUT',
                     post_data=post_data, expected_json=expected_json)


async def test_start_download_with_selected_files(test_download, mock_dlmgr, rest_api):
    """
    Testing whether we can start a download with the selected_files parameter set
    """
    def mocked_start_download(*_, config=None):
        assert config.get_selected_files() == [0]
        return succeed(test_download)

    mock_dlmgr.start_download_from_uri = mocked_start_download

    post_data = {'uri': f"file:{TESTS_DATA_DIR / 'video.avi.torrent'}", 'selected_files': [0]}
    expected_json = {'started': True, 'infohash': 'c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5'}
    await do_request(rest_api, 'downloads', expected_code=200, request_type='PUT',
                     post_data=post_data, expected_json=expected_json)


async def test_get_peers_illegal_fields_ascii(test_download, mock_dlmgr, mock_lt_status, rest_api):
    """
    Testing whether illegal fields are stripped from the Libtorrent download info response.
    """
    mock_dlmgr.get_downloads = lambda: [test_download]

    ds = DownloadState(test_download, mock_lt_status, None)
    ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': 'uTorrent 1.6.1'}]
    test_download.get_state = lambda: ds

    response_dict = await do_request(rest_api, 'downloads?get_peers=1&get_pieces=1', expected_code=200)
    assert "downloads" in response_dict
    assert len(response_dict["downloads"]) == 1
    assert "peers" in response_dict["downloads"][0]
    assert len(response_dict["downloads"][0]["peers"]) == 1
    assert 'have' not in response_dict["downloads"][0]["peers"][0]
    assert response_dict["downloads"][0]["peers"][0]['extended_version'] == 'uTorrent 1.6.1'


async def test_get_peers_illegal_fields_unknown(test_download, mock_dlmgr, mock_lt_status, rest_api):
    """
    Testing whether illegal fields are stripped from the Libtorrent download info response.
    """
    mock_dlmgr.get_downloads = lambda: [test_download]

    ds = DownloadState(test_download, mock_lt_status, None)
    ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': None}]
    test_download.get_state = lambda: ds

    response_dict = await do_request(rest_api, 'downloads?get_peers=1&get_pieces=1', expected_code=200)
    assert response_dict["downloads"][0]["peers"][0]['extended_version'] == ''


async def test_start_invalid_download(mock_dlmgr, rest_api):
    """
    Testing whether an Exception triggered in start_download_from_uri is correctly handled
    """
    def mocked_start_download(*_, **__):
        raise Exception("test")

    mock_dlmgr.start_download_from_uri = mocked_start_download

    post_data = {'uri': 'http://localhost:1234/test.torrent'}
    result = await do_request(rest_api, 'downloads', expected_code=500, request_type='PUT', post_data=post_data)
    assert result["error"] == "test"


async def test_remove_no_remove_data_param(rest_api):
    """
    Testing whether the API returns error 400 if the remove_data parameter is not passed
    """
    await do_request(rest_api, 'downloads/abcd', expected_code=400, request_type='DELETE')


async def test_remove_wrong_infohash(mock_dlmgr, rest_api):
    """
    Testing whether the API returns error 404 if a non-existent download is removed
    """
    mock_dlmgr.get_download = lambda _: None
    await do_request(rest_api, 'downloads/abcd', post_data={"remove_data": True},
                     expected_code=404, request_type='DELETE')


async def test_remove(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns 200 if a download is being removed
    """
    mock_dlmgr.get_download = lambda _: test_download
    mock_dlmgr.remove_download = lambda *_, **__: succeed(None)

    await do_request(rest_api, f'downloads/{test_download.infohash}', post_data={"remove_data": False},
                     expected_code=200, request_type='DELETE',
                     expected_json={"removed": True, "infohash": test_download.infohash})


async def test_stop_download_wrong_infohash(mock_dlmgr, rest_api):
    """
    Testing whether the API returns error 404 if a non-existent download is stopped
    """
    mock_dlmgr.get_download = lambda _: None
    await do_request(rest_api, 'downloads/abcd', expected_code=404, post_data={"state": "stop"}, request_type='PATCH')


async def test_stop_download(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns 200 if a download is being stopped
    """
    mock_dlmgr.get_download = lambda _: test_download

    def mocked_stop(*_, **__):
        test_download.should_stop = True
        return succeed(None)
    test_download.stop = mocked_stop

    await do_request(rest_api, f'downloads/{test_download.infohash}', post_data={"state": "stop"},
                     expected_code=200, request_type='PATCH',
                     expected_json={"modified": True, "infohash": test_download.infohash})
    assert test_download.should_stop


async def test_select_download_file_range(mock_dlmgr, test_download, rest_api):
    """
    Testing whether an error is returned when we toggle a file for inclusion out of range
    """
    mock_dlmgr.get_download = lambda _: test_download

    await do_request(rest_api, f'downloads/{test_download.infohash}', expected_code=400,
                     post_data={"selected_files": [1234]}, request_type='PATCH')


async def test_select_download_file(mock_dlmgr, test_download, rest_api):
    """
    Testing whether files can be correctly toggled in a download
    """
    mock_dlmgr.get_download = lambda _: test_download
    test_download.set_selected_files = Mock()

    await do_request(rest_api, f'downloads/{test_download.infohash}', post_data={"selected_files": [0]},
                     expected_code=200, request_type='PATCH',
                     expected_json={"modified": True, "infohash": test_download.infohash})
    test_download.set_selected_files.assert_called_with([0])


async def test_load_checkpoint_wrong_infohash(mock_dlmgr, rest_api):
    """
    Testing whether the API returns error 404 if a non-existent download is resumed
    """
    mock_dlmgr.get_download = lambda _: None
    await do_request(rest_api, 'downloads/abcd', expected_code=404, post_data={"state": "resume"}, request_type='PATCH')


async def test_resume_download(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns 200 if a download is being resumed
    """
    mock_dlmgr.get_download = lambda _: test_download

    def mocked_resume():
        test_download.should_resume = True
    test_download.resume = mocked_resume

    await do_request(rest_api, f'downloads/{test_download.infohash}', post_data={"state": "resume"},
                     expected_code=200, request_type='PATCH',
                     expected_json={"modified": True, "infohash": test_download.infohash})
    assert test_download.should_resume


async def test_recheck_download(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns 200 if a download is being rechecked
    """
    mock_dlmgr.get_download = lambda _: test_download
    test_download.force_recheck = Mock()

    await do_request(rest_api, f'downloads/{test_download.infohash}', post_data={"state": "recheck"},
                     expected_code=200, request_type='PATCH',
                     expected_json={"modified": True, "infohash": test_download.infohash})
    test_download.force_recheck.assert_called_once()


async def test_download_unknown_state(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns error 400 if an unknown state is passed when modifying a download
    """
    mock_dlmgr.get_download = lambda _: test_download

    await do_request(rest_api, f'downloads/{test_download.infohash}', expected_code=400,
                     post_data={"state": "abc"}, request_type='PATCH',
                     expected_json={"error": "unknown state parameter"})


async def test_change_hops_error(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns 400 if we supply both anon_hops and another parameter
    """
    mock_dlmgr.get_download = lambda _: True
    await do_request(rest_api, f'downloads/{test_download.infohash}', post_data={"state": "resume", 'anon_hops': 1},
                     expected_code=400, request_type='PATCH')


async def test_move_to_non_existing_dir(mock_dlmgr, test_download, rest_api, tmp_path):
    """
    Testing whether moving the torrent storage to a non-existing directory works as expected.
    """
    mock_dlmgr.get_download = lambda _: test_download

    dest_dir = tmp_path / "non-existing"
    assert not dest_dir.exists()
    data = {"state": "move_storage", "dest_dir": str(dest_dir)}

    response_dict = await do_request(rest_api, f'downloads/{test_download.infohash}',
                                     expected_code=200, post_data=data, request_type='PATCH')
    assert "error" in response_dict
    assert f"Target directory ({dest_dir}) does not exist" == response_dict["error"]


async def test_move_to_existing_dir(mock_dlmgr, test_download, rest_api, tmp_path):
    """
    Testing whether moving the torrent storage to an existing directory works as expected.
    """
    mock_dlmgr.get_download = lambda _: test_download

    dest_dir = tmp_path / "existing"
    os.mkdir(dest_dir)
    data = {"state": "move_storage", "dest_dir": str(dest_dir)}

    response_dict = await do_request(rest_api, f'downloads/{test_download.infohash}',
                                     expected_code=200, post_data=data, request_type='PATCH')
    assert response_dict.get("modified", False)
    assert test_download.infohash == response_dict["infohash"]


async def test_export_unknown_download(mock_dlmgr, rest_api):
    """
    Testing whether the API returns error 404 if a non-existent download is exported
    """
    mock_dlmgr.get_download = lambda _: None
    await do_request(rest_api, 'downloads/abcd/torrent', expected_code=404, request_type='GET')


async def test_export_download(mock_dlmgr, mock_handle, test_download, rest_api):
    """
    Testing whether the API returns the contents of the torrent file if a download is exported
    """
    test_download.get_torrent_data = lambda: 'a' * 20
    mock_dlmgr.get_download = lambda _: test_download
    await do_request(rest_api, f'downloads/{test_download.infohash}/torrent',
                     expected_code=200, request_type='GET', json_response=False)


async def test_get_files_unknown_download(mock_dlmgr, rest_api):
    """
    Testing whether the API returns error 404 if the files of a non-existent download are requested
    """
    mock_dlmgr.get_download = lambda _: None
    await do_request(rest_api, 'downloads/abcd/files', expected_code=404, request_type='GET')


async def test_get_download_files(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns file information of a specific download when requested
    """
    mock_dlmgr.get_download = lambda _: test_download

    response_dict = await do_request(rest_api, f'downloads/{test_download.infohash}/files',
                                     expected_code=200, request_type='GET')
    assert 'files' in response_dict
    assert response_dict['files']


async def test_stream_unknown_download(mock_dlmgr, rest_api):
    """
    Testing whether the API returns error 404 if we stream a non-existent download
    """
    mock_dlmgr.get_download = lambda _: None
    await do_request(rest_api, f'downloads/abcd/stream/0',
                     headers={'range': 'bytes=0-'}, expected_code=404, request_type='GET')


async def test_stream_download_out_of_bounds_file(mock_dlmgr, mock_handle, test_download, rest_api):
    """
    Testing whether the API returns code 404 if we stream with a file index out of bounds
    """
    mock_dlmgr.get_download = lambda _: test_download
    await do_request(rest_api, f'downloads/{test_download.infohash}/stream/100',
                     headers={'range': 'bytes=0-'}, expected_code=500, request_type='GET')


async def test_stream_download(mock_dlmgr, mock_handle, test_download, rest_api, tmp_path):
    """
    Testing whether the API returns code 206 if we stream a non-existent download
    """
    mock_dlmgr.get_download = lambda _: test_download

    with open(tmp_path / "dummy.txt", "w") as stream_file:
        stream_file.write("a" * 500)

    # Prepare a mocked stream
    stream = Mock()
    stream.seek = lambda _: succeed(None)
    stream.closed = False
    stream.filename = tmp_path / "dummy.txt"
    stream.enable = lambda *_, **__: succeed(None)
    stream.filesize = 500
    stream.piecelen = 32
    stream.seek = lambda _: succeed(None)
    stream.iterpieces = lambda *_, **__: [1]
    stream.prebuffsize = 0
    stream.lastpiece = 1
    stream.bytetopiece = lambda _: 1
    stream.pieceshave = [1, 2]
    stream.updateprios = lambda: succeed(None)
    stream.cursorpiecemap = {}
    stream.get_byte_progress = lambda _: 1
    stream.read = lambda _: succeed('a' * 500)
    test_download.stream = stream

    await do_request(rest_api, f'downloads/{test_download.infohash}/stream/0',
                     headers={'range': 'bytes=0-'}, expected_code=206, json_response=False)


async def test_change_hops(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns 200 if we change the amount of hops of a download
    """
    mock_dlmgr.get_download = lambda _: test_download
    mock_dlmgr.update_hops = lambda *_: succeed(None)

    await do_request(rest_api, f'downloads/{test_download.infohash}', post_data={'anon_hops': 1},
                     expected_code=200, request_type='PATCH',
                     expected_json={'modified': True, "infohash": test_download.infohash})


async def test_change_hops_fail(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns 500 if changing the number of hops in a download fails
    """
    mock_dlmgr.get_download = lambda _: test_download
    mock_dlmgr.update_hops = lambda *_: fail(RuntimeError)

    await do_request(rest_api, f'downloads/{test_download.infohash}', post_data={'anon_hops': 1},
                     expected_code=500, request_type='PATCH',
                     expected_json={'error': {'message': '', 'code': 'RuntimeError', 'handled': True}})
