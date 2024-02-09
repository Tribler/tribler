import copy
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from ipv8.messaging.anonymization.tunnel import CIRCUIT_ID_PORT
from ipv8.util import fail, succeed

from tribler.core.components.libtorrent.download_manager.download import Download, IllegalFileIndex
from tribler.core.components.libtorrent.download_manager.download_state import DownloadState
from tribler.core.components.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint
from tribler.core.components.libtorrent.torrent_file_tree import TorrentFileTree
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.utilities.rest_utils import HTTP_SCHEME, path_to_url
from tribler.core.utilities.simpledefs import DownloadStatus
from tribler.core.utilities.unicode import hexlify

TARGET = 'tribler.core.components.libtorrent.restapi.downloads_endpoint'


@pytest.fixture
def endpoint(mock_dlmgr, metadata_store):
    return DownloadsEndpoint(download_manager=mock_dlmgr, metadata_store=metadata_store, tunnel_community=MagicMock())


@patch.object(DownloadState, 'get_status', Mock(return_value=DownloadStatus.DOWNLOADING))
def test_get_extended_status_not_stopped(endpoint: DownloadsEndpoint, test_download: Download):
    # Test `_get_extended_status` when the download is not stopped
    actual = endpoint._get_extended_status(test_download)
    assert actual == DownloadStatus.DOWNLOADING


@patch.object(Download, 'lt_status', PropertyMock(), create=True)
@patch.object(DownloadState, 'get_status', Mock(return_value=DownloadStatus.STOPPED))
def test_get_extended_status_stopped_no_hops(endpoint: DownloadsEndpoint, test_download: Download):
    # Test `_get_extended_status` when the download is stopped and has no hops

    test_download.lt_status.paused = False
    test_download.config.get_hops = Mock(
        wraps=test_download.config.get_hops  # wraps is used to call the original method
    )
    test_download.config.set_hops(0)

    actual = endpoint._get_extended_status(test_download)

    assert actual == DownloadStatus.STOPPED
    assert test_download.config.get_hops.called


@patch.object(Download, 'lt_status', PropertyMock(), create=True)
@patch.object(DownloadState, 'get_status', Mock(return_value=DownloadStatus.STOPPED))
def test_get_extended_status_stopped_not_by_user(endpoint: DownloadsEndpoint, test_download: Download):
    # Test `_get_extended_status` when the download is stopped and not by the user
    test_download.lt_status.paused = True  # this is an indicator that the download was stopped by the user
    test_download.config.get_hops = Mock(
        wraps=test_download.config.get_hops  # wraps is used to call the original method
    )

    actual = endpoint._get_extended_status(test_download)

    assert actual == DownloadStatus.STOPPED
    assert not test_download.config.get_hops.called


@patch.object(Download, 'lt_status', PropertyMock(), create=True)
@patch.object(DownloadState, 'get_status', Mock(return_value=DownloadStatus.STOPPED))
def test_get_extended_status_stopped_hops_no_candidates(endpoint: DownloadsEndpoint, test_download: Download):
    # Test `_get_extended_status` when the download is stopped and has hops but no candidates
    test_download.lt_status.paused = False
    test_download.config.set_hops(1)
    endpoint.tunnel_community.get_candidates = Mock(return_value=[])

    actual = endpoint._get_extended_status(test_download)

    assert actual == DownloadStatus.EXIT_NODES


@patch.object(Download, 'lt_status', PropertyMock(), create=True)
@patch.object(DownloadState, 'get_status', Mock(return_value=DownloadStatus.STOPPED))
def test_get_extended_status_stopped_hops_candidates(endpoint: DownloadsEndpoint, test_download: Download):
    # Test `_get_extended_status` when the download is stopped and has hops and candidates
    test_download.lt_status.paused = False
    test_download.config.set_hops(1)
    endpoint.tunnel_community.get_candidates = Mock(return_value=[Mock()])

    actual = endpoint._get_extended_status(test_download)

    assert actual == DownloadStatus.CIRCUITS


@patch(f"{TARGET}.ensure_unicode", Mock(side_effect=UnicodeDecodeError("", b"", 0, 0, "")))
def test_safe_extended_peer_info(endpoint: DownloadsEndpoint):
    """
    Test that we return the string mapped by `chr` in the case of `UnicodeDecodeError`
    """
    extended_peer_info = endpoint._safe_extended_peer_info(b"abcd")
    assert extended_peer_info == "abcd"


async def test_get_downloads_if_checkpoints_are_not_loaded(mock_dlmgr, rest_api):
    mock_dlmgr.checkpoints_count = 10
    mock_dlmgr.checkpoints_loaded = 5
    mock_dlmgr.all_checkpoints_are_loaded = False

    expected_json = {"downloads": [], "checkpoints": {"total": 10, "loaded": 5, "all_loaded": False}}
    await do_request(rest_api, "downloads?get_peers=1&get_pieces=1", expected_code=200, expected_json=expected_json)


async def test_get_downloads_no_downloads(mock_dlmgr, rest_api):
    """
    Testing whether the API returns an empty list when downloads are fetched but no downloads are active
    """
    mock_dlmgr.checkpoints_count = 0
    mock_dlmgr.checkpoints_loaded = 0
    mock_dlmgr.all_checkpoints_are_loaded = True

    expected_json = {"downloads": [], "checkpoints": {"total": 0, "loaded": 0, "all_loaded": True}}
    await do_request(rest_api, "downloads?get_peers=1&get_pieces=1", expected_code=200, expected_json=expected_json)


async def test_get_downloads(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns the right download when a download is added
    """
    mock_dlmgr.get_downloads = lambda: [test_download]

    downloads = await do_request(rest_api, 'downloads?get_peers=1', expected_code=200)
    assert len(downloads["downloads"]) == 1
    assert "peers" in downloads["downloads"][0]  # Unfiltered with get_peers=1
    assert "pieces" not in downloads["downloads"][0]  # Unfiltered with get_pieces=0
    assert downloads["checkpoints"] == {"total": 1, "loaded": 1, "all_loaded": True}


async def test_get_downloads_circuit_peer(mock_dlmgr, test_download, rest_api, endpoint):
    """
    Testing whether circuit peers are correctly returned from downloads.
    """
    mock_dlmgr.get_downloads = Mock(return_value=[test_download])
    endpoint.tunnel_community = Mock()
    endpoint.tunnel_community.ip_to_circuit_id = Mock(return_value=42)
    test_download.get_peer_list = Mock(
        return_value=[
            {
                'ip': "127.0.0.1",
                'port': CIRCUIT_ID_PORT,
                'circuit': 42
            },
        ]
    )

    downloads = await do_request(rest_api, 'downloads?get_peers=1', expected_code=200)
    assert len(downloads["downloads"]) == 1
    assert "peers" in downloads["downloads"][0]  # Unfiltered with get_peers=1
    assert "pieces" not in downloads["downloads"][0]  # Unfiltered with get_pieces=0
    assert downloads["checkpoints"] == {"total": 1, "loaded": 1, "all_loaded": True}
    assert downloads["downloads"][0]["peers"][0]["port"] == CIRCUIT_ID_PORT
    assert downloads["downloads"][0]["peers"][0]["circuit"] == 42


async def test_get_downloads_with_passing_filter(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns all downloads even if the infohash filter passes.
    """
    mock_dlmgr.get_downloads = lambda: [test_download]

    downloads = await do_request(rest_api, 'downloads?get_peers=1&get_pieces=1&infohash=' + test_download.infohash,
                                 expected_code=200)

    assert len(downloads["downloads"]) == 1
    assert "peers" in downloads["downloads"][0]  # Filter passes with get_peers=1
    assert "pieces" in downloads["downloads"][0]  # Filter passes with get_pieces=1
    assert downloads["checkpoints"] == {"total": 1, "loaded": 1, "all_loaded": True}


async def test_get_downloads_with_excluding_filter(mock_dlmgr, test_download, test_tdef, rest_api):
    # In this test, we will create two downloads (test_download and another_download ) and we will exclude
    # another_download from the list of downloads returned by the API.

    def create_another_download():
        another_tdef = copy.deepcopy(test_tdef)
        another_tdef.infohash = b'2' * 20
        another_tdef._infohash_hex = hexlify(another_tdef.infohash)

        return Download(
            tdef=another_tdef,
            download_manager=mock_dlmgr,
            config=test_download.config
        )

    another_download = create_another_download()
    mock_dlmgr.get_downloads = Mock(return_value=[test_download, another_download])

    # test that without the filter, both downloads are returned
    result = await do_request(rest_api, 'downloads')
    assert len(result['downloads']) == 2

    # test that with the filter, only one download is returned
    result = await do_request(rest_api, 'downloads', params={'excluded': another_download.tdef.get_infohash_hex()})
    assert len(result['downloads']) == 1


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
    uri = path_to_url(TESTS_DATA_DIR / 'video.avi.torrent')
    expected_json = {'started': True, 'infohash': 'c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5'}
    await do_request(rest_api, 'downloads', expected_code=200, request_type='PUT',
                     post_data={'uri': uri}, expected_json=expected_json)


async def test_start_download_with_selected_files(test_download, mock_dlmgr, rest_api):
    """
    Testing whether we can start a download with the selected_files parameter set
    """

    def mocked_start_download(*_, config=None):
        assert config.get_selected_files() == [0]
        return succeed(test_download)

    mock_dlmgr.start_download_from_uri = mocked_start_download
    uri = path_to_url(TESTS_DATA_DIR / 'video.avi.torrent')
    post_data = {'uri': uri, 'selected_files': [0]}
    expected_json = {'started': True, 'infohash': 'c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5'}
    await do_request(rest_api, 'downloads', expected_code=200, request_type='PUT',
                     post_data=post_data, expected_json=expected_json)


async def test_get_peers_illegal_fields_ascii(test_download, mock_dlmgr, mock_lt_status, rest_api):
    """
    Testing whether illegal fields are stripped from the Libtorrent download info response.
    """
    mock_dlmgr.get_downloads = Mock(return_value=[test_download])

    ds = DownloadState(test_download, mock_lt_status, None)
    ds.get_peer_list = Mock(
        return_value=[
            {
                'id': '1234',
                'extended_version': 'uTorrent 1.6.1'
            }
        ]
    )
    test_download.get_state = Mock(return_value=ds)

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
    mock_dlmgr.get_downloads = Mock(return_value=[test_download])

    ds = DownloadState(test_download, mock_lt_status, None)
    ds.get_peer_list = Mock(
        return_value=[
            {
                'id': '1234',
                'extended_version': None
            }
        ]
    )
    test_download.get_state = Mock(return_value=ds)

    response_dict = await do_request(rest_api, 'downloads?get_peers=1&get_pieces=1', expected_code=200)
    assert response_dict["downloads"][0]["peers"][0]['extended_version'] == ''


async def test_start_invalid_download(mock_dlmgr, rest_api):
    """
    Testing whether an Exception triggered in start_download_from_uri is correctly handled
    """

    def mocked_start_download(*_, **__):
        raise Exception("test")

    mock_dlmgr.start_download_from_uri = mocked_start_download

    post_data = {'uri': f'{HTTP_SCHEME}://localhost:1234/test.torrent'}
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
    await do_request(rest_api, f'downloads/{test_download.infohash}/torrent', expected_code=200, request_type='GET',
                     json_response=False)


async def test_get_files_unknown_download(mock_dlmgr, rest_api):
    """
    Testing whether the API returns error 404 if the files of a non-existent download are requested
    """
    mock_dlmgr.get_download = lambda _: None
    await do_request(rest_api, 'downloads/abcd/files', expected_code=404, request_type='GET')


async def test_get_files_from_view_start_loading(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns the special loading state from a given start path.
    """
    mock_dlmgr.get_download = lambda _: test_download
    expected_file = {'index': IllegalFileIndex.unloaded.value, 'name': 'loading...', 'size': 0, 'included': False,
                     'progress': 0.0}

    result = await do_request(rest_api, f'downloads/{test_download.infohash}/files', params={"view_start_path": "."})

    assert 'infohash' in result
    assert result['infohash'] == test_download.infohash
    assert 'files' in result
    assert len(result['files']) == 1
    assert expected_file == result['files'][0]


async def test_get_files_from_view_start(mock_dlmgr, test_download, rest_api):
    """
    Testing whether the API returns files from a given start path.
    """
    mock_dlmgr.get_download = lambda _: test_download
    test_download.tdef.load_torrent_info()
    expected_file = {'index': 0, 'name': 'video.avi', 'size': 1942100, 'included': True, 'progress': 0.0}

    result = await do_request(rest_api, f'downloads/{test_download.infohash}/files', params={"view_start_path": "."})

    assert 'infohash' in result
    assert result['infohash'] == test_download.infohash
    assert 'files' in result
    assert len(result['files']) == 1
    assert expected_file == result['files'][0]


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
    await do_request(rest_api, 'downloads/abcd/stream/0', headers={'range': 'bytes=0-'}, expected_code=404,
                     request_type='GET')


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


async def test_expand(mock_dlmgr, mock_handle, test_download, rest_api):
    """
    Testing if a call to expand is correctly propagated to the underlying torrent file tree.
    """
    tree = TorrentFileTree(None)
    tree.root.directories = {"testdir": TorrentFileTree.Directory(collapsed=True)}

    test_download.tdef.torrent_file_tree = tree
    mock_dlmgr.get_download = lambda _: test_download

    await do_request(rest_api, f'downloads/{test_download.infohash}/files/expand', params={"path": "testdir"},
                     expected_code=200)
    assert not tree.find(Path("testdir")).collapsed


async def test_expand_unknown_download(mock_dlmgr, rest_api):
    """
    Testing for 404 when expanding a valid path for a non-existent download.
    """
    mock_dlmgr.get_download = lambda _: None

    await do_request(rest_api, f'downloads/{"00" * 20}/files/expand', params={"path": "."}, expected_code=404)


async def test_collapse(mock_dlmgr, mock_handle, test_download, rest_api):
    """
    Testing if a call to collapse is correctly propagated to the underlying torrent file tree.
    """
    tree = TorrentFileTree(None)
    tree.root.directories = {"testdir": TorrentFileTree.Directory(collapsed=False)}

    test_download.tdef.torrent_file_tree = tree
    mock_dlmgr.get_download = lambda _: test_download

    await do_request(rest_api, f'downloads/{test_download.infohash}/files/collapse', params={"path": "testdir"},
                     expected_code=200)
    assert tree.find(Path("testdir")).collapsed


async def test_collapse_unknown_download(mock_dlmgr, rest_api):
    """
    Testing for 404 when collapsing a valid path for a non-existent download.
    """
    mock_dlmgr.get_download = lambda _: None

    await do_request(rest_api, f'downloads/{"00" * 20}/files/collapse', params={"path": "."}, expected_code=404)


async def test_select(mock_dlmgr, mock_handle, test_download, rest_api):
    """
    Testing if a call to select is correctly propagated to the underlying torrent file tree.
    """
    test_file = TorrentFileTree.File("somefile.trib", 0, 1, selected=False)
    tree = TorrentFileTree(None)
    tree.root.directories = {"testdir": TorrentFileTree.Directory(files=[test_file], collapsed=False)}

    test_download.tdef.torrent_file_tree = tree
    mock_dlmgr.get_download = lambda _: test_download

    await do_request(rest_api, f'downloads/{test_download.infohash}/files/select',
                     params={"path": "testdir/somefile.trib"}, expected_code=200)
    assert test_file.selected


async def test_select_unknown_download(mock_dlmgr, rest_api):
    """
    Testing for 404 when selecting a valid path for a non-existent download.
    """
    mock_dlmgr.get_download = lambda _: None

    await do_request(rest_api, f'downloads/{"00" * 20}/files/select', params={"path": "."}, expected_code=404)


async def test_deselect(mock_dlmgr, mock_handle, test_download, rest_api):
    """
    Testing if a call to deselect is correctly propagated to the underlying torrent file tree.
    """
    test_file = TorrentFileTree.File("somefile.trib", 0, 1, selected=True)
    tree = TorrentFileTree(None)
    tree.root.directories = {"testdir": TorrentFileTree.Directory(files=[test_file], collapsed=False)}

    test_download.tdef.torrent_file_tree = tree
    mock_dlmgr.get_download = lambda _: test_download

    await do_request(rest_api, f'downloads/{test_download.infohash}/files/deselect',
                     params={"path": "testdir/somefile.trib"}, expected_code=200)
    assert not test_file.selected


async def test_deselect_unknown_download(mock_dlmgr, rest_api):
    """
    Testing for 404 when deselecting a valid path for a non-existent download.
    """
    mock_dlmgr.get_download = lambda _: None

    await do_request(rest_api, f'downloads/{"00" * 20}/files/deselect', params={"path": "."}, expected_code=404)


async def test_get_availability(mock_dlmgr, test_download, rest_api):
    # Test if the availability is returned when requested
    mock_dlmgr.get_downloads = Mock(return_value=[test_download])

    response = await do_request(
        rest_api,
        url='downloads',
        params={
            'infohash': test_download.infohash,
        }
    )
    download = response['downloads'][0]
    assert 'availability' not in download

    response = await do_request(
        rest_api,
        url='downloads',
        params={
            'infohash': test_download.infohash,
            'get_availability': 1,
        }
    )

    download = response['downloads'][0]
    assert 'availability' in download
