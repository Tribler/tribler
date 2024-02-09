import math
from unittest.mock import Mock

import pytest

from tribler.core.components.libtorrent.download_manager.download_state import DownloadState
from tribler.core.utilities.simpledefs import DOWNLOAD, DownloadStatus, UPLOAD


@pytest.fixture
def mock_tdef():
    tdef = Mock(
        get_name=Mock(return_value='test'),
        get_length=Mock(return_value=43)
    )
    return tdef


@pytest.fixture
def mock_download(mock_tdef):
    download = Mock(
        get_def=Mock(return_value=mock_tdef)
    )
    return download


def test_getters_setters_1(mock_download):
    """
    Testing various getters and setters in DownloadState
    """
    mock_download.get_peer_list = Mock(return_value=[])
    mock_download.dlmgr.tunnel_community.get_candidates = Mock(return_value=[])
    mock_download.config.get_hops = Mock(return_value=0)
    download_state = DownloadState(mock_download, None, None)

    assert download_state.get_download() == mock_download
    assert download_state.get_progress() == 0
    assert download_state.get_error() is None
    assert download_state.get_current_speed(UPLOAD) == 0
    assert download_state.total_upload == 0
    assert download_state.total_download == 0
    assert download_state.total_payload_download == 0
    assert download_state.total_payload_upload == 0
    assert download_state.all_time_upload == 0
    assert download_state.all_time_download == 0
    assert download_state.get_num_seeds_peers() == (0, 0)
    assert download_state.get_peer_list() == []


def test_getters_setters_2(mock_download, mock_lt_status):
    """
    Testing various getters and setters in DownloadState
    """
    download_state = DownloadState(mock_download, mock_lt_status, None)

    assert download_state.get_status() == DownloadStatus.DOWNLOADING
    assert download_state.get_current_speed(UPLOAD) == 123
    assert download_state.get_current_speed(DOWNLOAD) == 43
    assert download_state.total_upload == 100
    assert download_state.total_download == 200

    assert download_state.total_payload_upload == 30
    assert download_state.total_payload_download == 100

    assert download_state.all_time_upload == 200
    assert download_state.all_time_download == 1000

    assert download_state.get_eta() == 0.25
    assert download_state.get_num_seeds_peers() == (5, 5)
    assert download_state.get_pieces_complete() == []
    assert download_state.get_pieces_total_complete() == (0, 0)
    assert download_state.get_seeding_time() == 10

    mock_lt_status.num_pieces = 6
    mock_lt_status.pieces = [1, 1, 1, 0, 0, 0]
    assert download_state.get_pieces_complete() == [1, 1, 1, 0, 0, 0]
    assert download_state.get_pieces_total_complete() == (6, 3)

    mock_download.config.get_selected_files = lambda: ['test']
    assert download_state.get_selected_files() == ['test']
    assert download_state.get_progress() == 0.75


def test_all_time_ratio_no_lt_status():
    # Test when lt_status is None
    state = DownloadState(
        download=Mock(),
        lt_status=None,
    )
    assert state.get_all_time_ratio() == 0


def test_all_time_ratio():
    # Test all time ratio formula
    state = DownloadState(
        download=Mock(),
        lt_status=Mock(
            all_time_upload=200,
            all_time_download=1000,
        ),
    )
    assert state.get_all_time_ratio() == 0.2


def test_all_time_ratio_no_all_time_download():
    # Test all time ratio formula when all_time_download is 0 and all_time_upload is 0
    state = DownloadState(
        download=Mock(),
        lt_status=Mock(
            all_time_upload=0,
            all_time_download=0,
        ),
    )
    assert state.get_all_time_ratio() == 0


def test_all_time_ratio_no_all_time_download_inf():
    # Test all time ratio formula when all_time_download is 0 and all_time_upload is not 0
    state = DownloadState(
        download=Mock(),
        lt_status=Mock(
            all_time_upload=200,
            all_time_download=0,
        ),
    )
    assert state.get_all_time_ratio() == math.inf


def test_get_files_completion(mock_download, mock_tdef):
    """
    Testing whether the right completion of files is returned
    """
    mock_tdef.get_files_with_length = lambda: [("test.txt", 100)]

    handle = Mock()
    handle.file_progress = lambda **_: [60]
    handle.is_valid = lambda: True
    mock_download.handle = handle

    download_state = DownloadState(mock_download, Mock(), None)
    assert download_state.get_files_completion() == [('test.txt', 0.6)]
    handle.file_progress = lambda **_: [0]
    assert download_state.get_files_completion() == [('test.txt', 0.0)]
    handle.file_progress = lambda **_: [100]
    assert download_state.get_files_completion() == [('test.txt', 1.0)]
    mock_tdef.get_files_with_length = lambda: []
    handle.file_progress = lambda **_: []
    assert download_state.get_files_completion() == []

    # Test a file with a length of zero
    mock_tdef.get_files_with_length = lambda: [("test.txt", 0)]
    handle.file_progress = lambda **_: [0]
    assert download_state.get_files_completion() == [('test.txt', 1.0)]

    # Test a file with empty file progress
    mock_tdef.get_files_with_length = lambda: [("test.txt", 0)]
    handle.file_progress = lambda **_: []
    assert download_state.get_files_completion() == []


def test_get_availability(mock_download):
    """
    Testing whether the right availability of a file is returned
    """
    mock_ltstate = Mock()
    mock_ltstate.pieces = [True]
    download_state = DownloadState(mock_download, mock_ltstate, 0.6)
    download_state.get_peer_list = lambda: []

    assert download_state.get_availability() == 0
    download_state.get_peer_list = lambda: [{'completed': 1.0}]
    assert download_state.get_availability() == 1.0
    download_state.get_peer_list = lambda: [{'completed': 0.6}]
    assert download_state.get_availability() == 0.0
    download_state.lt_status.pieces = [0, 0, 0, 0, 0]
    download_state.get_peer_list = lambda: [{'completed': 0}, {'have': [1, 1, 1, 1, 0]}]
    assert download_state.get_availability() == 0.8

    # Test whether inaccurate piece information from other peers is ignored
    download_state.get_peer_list = lambda: [{'completed': 0.5, 'have': [1, 0]},
                                            {'completed': 0.9, 'have': [1, 0, 1]}]
    assert download_state.get_availability() == 0.0


def test_get_files_completion_semivalid_handle(mock_download, mock_tdef):
    """
    Testing whether no file completion is returned for valid handles that have invalid file_progress.

    This case mirrors https://github.com/Tribler/tribler/issues/6454
    """
    mock_tdef.get_files_with_length = lambda: [("test.txt", 100)]

    def file_progress(flags: int):
        raise RuntimeError("invalid torrent handle used")

    handle = Mock()
    handle.file_progress = file_progress
    handle.is_valid = lambda: True
    mock_download.handle = handle

    download_state = DownloadState(mock_download, Mock(), None)
    assert download_state.get_files_completion() == []
