from unittest.mock import Mock

import pytest

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING, DOWNLOAD, UPLOAD

from tribler_core.components.libtorrent.download_manager.download_state import DownloadState


@pytest.fixture
def mock_tdef():
    mocked_tdef = Mock()
    mocked_tdef.get_name = lambda: "test"
    mocked_tdef.get_length = lambda: 43
    return mocked_tdef


@pytest.fixture
def mock_download(mock_tdef):
    mock_download = Mock()
    mock_download.get_def = lambda: mock_tdef
    return mock_download


def test_getters_setters_1(mock_download):
    """
    Testing various getters and setters in DownloadState
    """
    mock_download.get_peerlist = lambda: []
    mock_download.dlmgr.tunnel_community.get_candidates = lambda _: []
    mock_download.config.get_hops = lambda: 0
    download_state = DownloadState(mock_download, None, None)

    assert download_state.get_download() == mock_download
    assert download_state.get_progress() == 0
    assert download_state.get_error() is None
    assert download_state.get_current_speed(UPLOAD) == 0
    assert download_state.get_total_transferred(UPLOAD) == 0
    assert download_state.get_num_seeds_peers() == (0, 0)
    assert download_state.get_peerlist() == []


def test_getters_setters_2(mock_download, mock_lt_status):
    """
    Testing various getters and setters in DownloadState
    """
    download_state = DownloadState(mock_download, mock_lt_status, None)

    assert download_state.get_status() == DLSTATUS_DOWNLOADING
    assert download_state.get_current_speed(UPLOAD) == 123
    assert download_state.get_current_speed(DOWNLOAD) == 43
    assert download_state.get_total_transferred(UPLOAD) == 100
    assert download_state.get_total_transferred(DOWNLOAD) == 200
    assert download_state.get_seeding_ratio() == 0.5
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


def test_get_availability(mock_download):
    """
    Testing whether the right availability of a file is returned
    """
    mock_ltstate = Mock()
    mock_ltstate.pieces = [True]
    download_state = DownloadState(mock_download, mock_ltstate, 0.6)
    download_state.get_peerlist = lambda: []

    assert download_state.get_availability() == 0
    download_state.get_peerlist = lambda: [{'completed': 1.0}]
    assert download_state.get_availability() == 1.0
    download_state.get_peerlist = lambda: [{'completed': 0.6}]
    assert download_state.get_availability() == 0.0
    download_state.lt_status.pieces = [0, 0, 0, 0, 0]
    download_state.get_peerlist = lambda: [{'completed': 0}, {'have': [1, 1, 1, 1, 0]}]
    assert download_state.get_availability() == 0.8

    # Test whether inaccurate piece information from other peers is ignored
    download_state.get_peerlist = lambda: [{'completed': 0.5, 'have': [1, 0]},
                                           {'completed': 0.9, 'have': [1, 0, 1]}]
    assert download_state.get_availability() == 0.0
