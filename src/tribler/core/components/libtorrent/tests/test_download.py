from asyncio import Future, sleep
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import libtorrent as lt
import pytest
from _pytest.logging import LogCaptureFixture
from ipv8.util import succeed
from libtorrent import bencode

from tribler.core import notifications
from tribler.core.components.libtorrent.download_manager.download import Download, IllegalFileIndex
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.components.libtorrent.utils.torrent_utils import get_info_from_handle
from tribler.core.components.reporter.exception_handler import NoCrashException
from tribler.core.exceptions import SaveResumeDataError
from tribler.core.tests.tools.base_test import MockObject
from tribler.core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE, TORRENT_VIDEO_FILE
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import bdecode_compat


@pytest.fixture(name="minifile_download")
async def fixture_minifile_download(mock_dlmgr) -> Generator[Download, None, None]:
    """
    A download with multiple files that fit into a single piece.
    """
    tdef = TorrentDef({
        b'info': {
            b'name': 'data',
            b'files': [{b'path': [b'a.txt'], b'length': 1}, {b'path': [b'b.txt'], b'length': 1}],
            b'piece length': 128,  # Note: both a.txt (length 1) and b.txt (length 1) fit in one piece
            b'pieces': b'\x00' * 20
        }
    })
    config = DownloadConfig(state_dir=mock_dlmgr.state_dir)
    download = Download(tdef, download_manager=mock_dlmgr, config=config)
    download.infohash = hexlify(tdef.get_infohash())
    yield download

    await download.shutdown()


def test_download_properties(test_download, test_tdef):
    assert not test_download.get_magnet_link()
    assert test_download.tdef, test_tdef


def test_download_get_atp(mock_dlmgr, test_download):
    assert isinstance(test_download.get_atp(), dict)


def test_download_resume(mock_handle, test_download):
    test_download.config = MagicMock()

    test_download.resume()
    test_download.handle.resume.assert_called()


async def test_download_resume_in_upload_mode(mock_handle, test_download):  # pylint: disable=unused-argument
    test_download.config = MagicMock()

    await test_download.set_upload_mode(True)
    test_download.resume()
    test_download.handle.set_upload_mode.assert_called_with(test_download.get_upload_mode())


async def test_save_resume(mock_handle, test_download: Download, test_tdef):
    """
    testing call resume data alert
    """
    test_download.handle.is_valid = lambda: True
    test_download.handle.save_resume_data = lambda: test_download.register_task('post_alert',
                                                                                test_download.process_alert, alert,
                                                                                'save_resume_data_alert', delay=0.1)

    alert = Mock(resume_data={b'info-hash': test_tdef.get_infohash()})
    await test_download.save_resume_data()
    basename = hexlify(test_tdef.get_infohash()) + '.conf'
    filename = test_download.download_manager.get_checkpoint_dir() / basename
    dcfg = DownloadConfig.load(str(filename))
    assert test_tdef.get_infohash() == dcfg.get_engineresumedata().get(b'info-hash')


def test_move_storage(mock_handle, test_download, test_tdef, test_tdef_no_metainfo):
    """
    Test that move_storage method works as expected by Libtorrent
    """
    result = []

    def mock_move(s):
        result.append(s)

    test_download.handle.move_storage = mock_move

    test_download.move_storage(Path("some_path"))
    assert result[0] == "some_path"
    assert test_download.config.get_dest_dir().name == "some_path"

    # Check the same thing, this time for TorrentDefNoMetainfo (nothing should happen)
    test_download.tdef = test_tdef_no_metainfo
    test_download.move_storage(Path("some_path2"))
    assert len(result) == 1


async def test_save_checkpoint(test_download, test_tdef):
    await test_download.checkpoint()
    basename = hexlify(test_tdef.get_infohash()) + '.conf'
    filename = Path(test_download.download_manager.get_checkpoint_dir() / basename)
    assert filename.is_file()


def test_selected_files_default(minifile_download: Download):
    """
    Test whether the default selected files are no files.
    """
    minifile_download.handle = Mock(file_priorities=Mock(return_value=[0, 0]))
    assert [] == minifile_download.config.get_selected_files()
    assert [0, 0] == minifile_download.get_file_priorities()


def test_selected_files_last(minifile_download: Download):
    """
    Test whether the last selected file in a list of files gets correctly selected.
    """
    minifile_download.handle = Mock(file_priorities=Mock(return_value=[0, 4]))
    minifile_download.set_selected_files([1])
    minifile_download.handle.prioritize_files.assert_called_with([0, 4])
    assert [1] == minifile_download.config.get_selected_files()
    assert [0, 4] == minifile_download.get_file_priorities()


def test_selected_files_first(minifile_download: Download):
    """
    Test whether the first selected file in a list of files gets correctly selected.
    """
    minifile_download.handle = Mock(file_priorities=Mock(return_value=[4, 0]))
    minifile_download.set_selected_files([0])
    minifile_download.handle.prioritize_files.assert_called_with([4, 0])
    assert [0] == minifile_download.config.get_selected_files()
    assert [4, 0] == minifile_download.get_file_priorities()


def test_selected_files_all(minifile_download: Download):
    """
    Test whether all files can be selected.
    """
    minifile_download.handle = Mock(file_priorities=Mock(return_value=[4, 4]))
    minifile_download.set_selected_files([0, 1])
    minifile_download.handle.prioritize_files.assert_called_with([4, 4])
    assert [0, 1] == minifile_download.config.get_selected_files()
    assert [4, 4] == minifile_download.get_file_priorities()


def test_selected_files_all_through_none(minifile_download: Download):
    """
    Test whether all files can be selected by selecting None.
    """
    minifile_download.handle = Mock(file_priorities=Mock(return_value=[4, 4]))
    minifile_download.set_selected_files()
    minifile_download.handle.prioritize_files.assert_called_with([4, 4])
    assert [] == minifile_download.config.get_selected_files()
    assert [4, 4] == minifile_download.get_file_priorities()


def test_selected_files_all_through_empty_list(minifile_download: Download):
    """
    Test whether all files can be selected by selecting an empty list
    """
    minifile_download.handle = Mock(file_priorities=Mock(return_value=[4, 4]))
    minifile_download.set_selected_files([])
    minifile_download.handle.prioritize_files.assert_called_with([4, 4])
    assert [] == minifile_download.config.get_selected_files()
    assert [4, 4] == minifile_download.get_file_priorities()


def test_selected_files_no_files(mock_handle, test_download):
    """
    Test that no files are selected if torrent info is not available.
    """

    def mocked_set_file_prios(_):
        mocked_set_file_prios.called = True

    mocked_set_file_prios.called = False

    mocked_file = Mock()
    mocked_file.path = 'my/path'
    test_download.handle.prioritize_files = mocked_set_file_prios
    test_download.handle.torrent_file = lambda: None
    test_download.handle.rename_file = lambda *_: None
    test_download.handle.is_valid = lambda: False
    test_download.tdef.get_infohash = lambda: b'a' * 20

    # If share mode is not enabled and everything else is fine, file priority should be set
    # when set_selected_files() is called. But in this test, no files attribute is set in torrent info
    # in order to test AttributeError, therfore, no call to set file priority is expected.
    test_download.get_share_mode = lambda: False
    test_download.set_selected_files([0])
    assert not mocked_set_file_prios.called


def test_get_share_mode(test_download):
    """
    Test whether we return the right share mode when requested in the Download
    """
    test_download.config.get_share_mode = lambda: False
    assert not test_download.get_share_mode()
    test_download.config.get_share_mode = lambda: True
    assert test_download.get_share_mode()


async def test_set_share_mode(mock_handle, test_download):
    """
    Test whether we set the right share mode in Download
    """

    def mocked_set_share_mode(val):
        assert val
        mocked_set_share_mode.called = True

    mocked_set_share_mode.called = False
    test_download.handle.set_share_mode = mocked_set_share_mode
    await test_download.set_share_mode(True)
    assert mocked_set_share_mode.called


def test_get_num_connected_seeds_peers(mock_handle, test_download):
    """
    Test whether connected peers and seeds are correctly returned
    """

    def get_peer_info(seeders, leechers):
        peer_info = []
        for _ in range(seeders):
            seeder = MockObject()
            seeder.flags = 140347  # some value where seed flag(1024) is true
            seeder.seed = 1024
            peer_info.append(seeder)
        for _ in range(leechers):
            leecher = MockObject()
            leecher.flags = 131242  # some value where seed flag(1024) is false
            leecher.seed = 1024
            peer_info.append(leecher)
        return peer_info

    mock_seeders = 15
    mock_leechers = 6
    test_download.handle.get_peer_info = lambda: get_peer_info(mock_seeders, mock_leechers)

    num_seeds, num_peers = test_download.get_num_connected_seeds_peers()
    assert num_seeds == mock_seeders, "Expected seeders differ"
    assert num_peers == mock_leechers, "Expected peers differ"


async def test_set_priority(mock_handle, test_download):
    """
    Test whether setting the priority calls the right methods in Download
    """

    def mocked_set_priority(prio):
        assert prio == 1234
        mocked_set_priority.called = True

    mocked_set_priority.called = False
    test_download.handle.set_priority = mocked_set_priority
    await test_download.set_priority(1234)
    assert mocked_set_priority.called


def test_add_trackers(mock_handle, test_download):
    """
    Testing whether trackers are added to the libtorrent handler in Download
    """

    def mocked_add_trackers(tracker_info):
        assert isinstance(tracker_info, dict)
        assert tracker_info['url'] == 'http://google.com'
        mocked_add_trackers.called = True

    mocked_add_trackers.called = False
    test_download.handle.add_tracker = mocked_add_trackers
    test_download.add_trackers(['http://google.com'])
    assert mocked_add_trackers.called


def test_process_error_alert(test_download):
    """
    Testing whether error alerts are processed correctly
    """
    url = "http://google.com"
    mock_alert = MockObject()
    mock_alert.msg = None
    mock_alert.category = lambda: lt.alert.category_t.error_notification
    mock_alert.status_code = 123
    mock_alert.url = url
    test_download.process_alert(mock_alert, 'tracker_error_alert')
    assert test_download.tracker_status[url][1] == 'HTTP status code 123'

    mock_alert.status_code = 0
    test_download.process_alert(mock_alert, 'tracker_error_alert')
    assert test_download.tracker_status[url][1] == 'Timeout'


def test_tracker_error_alert_unicode_decode_error(test_download: Download, caplog: LogCaptureFixture):
    # This exception in alert.__repr__() should be handled by the safe_repr() function
    exception1 = UnicodeDecodeError('utf-8', b'\xc3\x28', 0, 1, 'invalid continuation byte (exception in __repr__)')

    # Another exception in alert.url should be handled by the Download.process_alert() code
    exception2 = UnicodeDecodeError('utf-8', b'\xc3\x28', 0, 1, 'invalid continuation byte (exception in .url)')

    mock_alert = MagicMock(__repr__=Mock(side_effect=exception1))
    type(mock_alert).url = PropertyMock(side_effect=exception2)

    test_download.process_alert(mock_alert, 'tracker_error_alert')

    mock_expected_safe_repr = (f"<Repr of {object.__repr__(mock_alert)} raises UnicodeDecodeError: "
                               "'utf-8' codec can't decode byte 0xc3 in position 0: invalid continuation byte "
                               "(exception in __repr__)>")

    assert len(caplog.messages) == 2

    # The first exception in self._logger.error(f'On tracker error alert: {safe_repr(alert)}')
    # is converted to the following warning message:
    assert caplog.messages[0] == f'On tracker error alert: {mock_expected_safe_repr}'

    # The second exception in alert.url is converted to the following error message:
    assert caplog.messages[1] == ("UnicodeDecodeError in on_tracker_error_alert: "
                                  "'utf-8' codec can't decode byte 0xc3 in position 0: invalid continuation byte "
                                  "(exception in .url)")


def test_tracker_error_alert_has_msg(test_download: Download):
    alert = MagicMock(__repr__=Mock(return_value='<ALERT_REPR>'), url='<ALERT_URL>', msg='<ALERT_MSG>')
    assert alert.url not in test_download.tracker_status
    test_download.on_tracker_error_alert(alert)
    assert test_download.tracker_status[alert.url] == [0, 'Error: <ALERT_MSG>']


def test_tracker_error_alert_has_positive_status_code(test_download: Download):
    alert = MagicMock(__repr__=Mock(return_value='<ALERT_REPR>'), url='<ALERT_URL>', msg=None, status_code=123)
    assert alert.url not in test_download.tracker_status
    test_download.on_tracker_error_alert(alert)
    assert test_download.tracker_status[alert.url] == [0, 'HTTP status code 123']


def test_tracker_error_alert_has_status_code_zero(test_download: Download):
    alert = MagicMock(__repr__=Mock(return_value='<ALERT_REPR>'), url='<ALERT_URL>', msg=None, status_code=0)
    assert alert.url not in test_download.tracker_status
    test_download.on_tracker_error_alert(alert)
    assert test_download.tracker_status[alert.url] == [0, 'Timeout']


def test_tracker_error_alert_has_negative_status_code(test_download: Download):
    alert = MagicMock(__repr__=Mock(return_value='<ALERT_REPR>'), url='<ALERT_URL>', msg=None, status_code=-1)
    assert alert.url not in test_download.tracker_status
    test_download.on_tracker_error_alert(alert)
    assert test_download.tracker_status[alert.url] == [0, 'Not working']


def test_tracker_warning_alert(test_download):
    """
    Test whether a tracking warning alert is processed correctly
    """
    url = "http://google.com"
    mock_alert = MockObject()
    mock_alert.category = lambda: lt.alert.category_t.error_notification
    mock_alert.url = url
    mock_alert.message = lambda: 'test'
    test_download.process_alert(mock_alert, 'tracker_warning_alert')
    assert test_download.tracker_status[url][1] == 'Warning: test'


async def test_on_metadata_received_alert(mock_handle, test_download):
    """
    Testing whether the right operations happen when we receive metadata
    """
    test_future = Future()

    mocked_file = Mock()
    mocked_file.path = 'test'

    test_download.handle.trackers = lambda: []
    test_download.handle.get_peer_info = lambda: []
    test_download.handle.save_resume_data = lambda: test_future
    test_download.handle.rename_file = lambda *_: None
    with open(TESTS_DATA_DIR / "bak_single.torrent", mode='rb') as torrent_file:
        encoded_metainfo = torrent_file.read()
    decoded_metainfo = bdecode_compat(encoded_metainfo)
    get_info_from_handle(test_download.handle).metadata = lambda: bencode(decoded_metainfo[b'info'])
    get_info_from_handle(test_download.handle).files = lambda: [mocked_file]

    test_download.checkpoint = lambda: test_future.set_result(None)
    test_download.session = MockObject()
    test_download.session.torrent_db = None
    test_download.handle.save_path = lambda: None
    test_download.handle.prioritize_files = lambda _: None
    test_download.get_share_mode = lambda: False
    test_download.on_metadata_received_alert(None)

    await test_future


def test_metadata_received_invalid_info(mock_handle, test_download):
    """
    Testing whether the right operations happen when we receive metadata but the torrent info is invalid
    """

    def mocked_checkpoint():
        raise RuntimeError("This code should not be reached!")

    test_download.checkpoint = mocked_checkpoint
    test_download.handle.torrent_file = lambda: None
    test_download.on_metadata_received_alert(None)


def test_on_metadata_received_alert_unicode_error(test_download, dual_movie_tdef):
    """ Test the the case the field 'url' is not unicode compatible. In this case no exceptions should be raised.

    See: https://github.com/Tribler/tribler/issues/7223
    """
    test_download.tdef = dual_movie_tdef
    tracker = {'url': Mock(encode=Mock(side_effect=UnicodeDecodeError('', b'', 0, 0, '')))}
    test_download.handle = MagicMock(trackers=Mock(return_value=[tracker]),
                                     torrent_file=lambda: dual_movie_tdef.torrent_info)

    test_download.on_metadata_received_alert(MagicMock())


def test_metadata_received_invalid_torrent_with_value_error(mock_handle, test_download):
    """
    Testing whether the right operations happen when we receive metadata but the torrent info is invalid and throws
    Value Error
    """

    def mocked_checkpoint():
        raise RuntimeError("This code should not be reached!")

    mocked_file = Mock()
    mocked_file.path = 'test'

    # The line below should trigger Value Error
    test_download.handle.trackers = lambda: [{'url': 'no-DHT'}]
    test_download.handle.get_peer_info = lambda: []

    get_info_from_handle(test_download.handle).metadata = lambda: lt.bencode({})
    get_info_from_handle(test_download.handle).files = lambda: [mocked_file]

    test_download.checkpoint = mocked_checkpoint
    test_download.on_metadata_received_alert(None)


def test_torrent_checked_alert(mock_handle, test_download):
    """
    Testing whether the right operations happen after a torrent checked alert is received
    """

    def mocked_pause_checkpoint():
        mocked_pause_checkpoint.called = True
        return succeed(None)

    mocked_pause_checkpoint.called = False
    test_download.handle.pause = mocked_pause_checkpoint
    test_download.checkpoint = mocked_pause_checkpoint

    mock_alert = MockObject()
    mock_alert.category = lambda: lt.alert.category_t.error_notification
    test_download.pause_after_next_hashcheck = True
    test_download.process_alert(mock_alert, 'torrent_checked_alert')
    assert not test_download.pause_after_next_hashcheck
    assert mocked_pause_checkpoint.called

    mocked_pause_checkpoint.called = False
    test_download.checkpoint_after_next_hashcheck = True
    test_download.process_alert(mock_alert, 'torrent_checked_alert')
    assert not test_download.checkpoint_after_next_hashcheck
    assert mocked_pause_checkpoint.called


def test_tracker_reply_alert(test_download):
    """
    Testing the tracker reply alert in Download
    """
    mock_alert = Mock()
    mock_alert.url = 'http://google.com'
    mock_alert.num_peers = 42
    test_download.on_tracker_reply_alert(mock_alert)
    assert test_download.tracker_status['http://google.com'] == [42, 'Working']


def test_get_pieces_bitmask(mock_handle, test_download):
    """
    Testing whether a correct pieces bitmask is returned when requested
    """
    test_download.handle.status().pieces = [True, False, True, False, False]
    assert test_download.get_pieces_base64() == b"oA=="

    test_download.handle.status().pieces = [True] * 16
    assert test_download.get_pieces_base64() == b"//8="


async def test_resume_data_failed(test_download):
    """
    Testing whether the correct operations happen when an error is raised during resume data saving
    """
    mock_alert = Mock(msg="test error")
    test_download.register_task('post_alert', test_download.process_alert, mock_alert,
                                'save_resume_data_failed_alert', delay=0.1)
    with pytest.raises(SaveResumeDataError):
        await test_download.wait_for_alert('save_resume_data_alert', None,
                                           'save_resume_data_failed_alert', lambda _: SaveResumeDataError())


def test_on_state_changed(mock_handle, test_download):
    test_download.handle.status = lambda: Mock(error=None)
    test_download.tdef.get_infohash = lambda: b'a' * 20
    test_download.config.set_hops(1)
    test_download.apply_ip_filter = Mock()
    test_download.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=4)))
    test_download.apply_ip_filter.assert_called_with(False)

    test_download.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=5)))
    test_download.apply_ip_filter.assert_called_with(True)

    test_download.config.set_hops(0)
    test_download.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=4)))
    test_download.apply_ip_filter.assert_called_with(False)

    test_download.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=5)))
    test_download.apply_ip_filter.assert_called_with(False)


async def test_apply_ip_filter(test_download, mock_handle):  # pylint: disable=unused-argument
    test_download.handle.status = lambda: Mock(error=None)
    test_download.tdef.get_infohash = lambda: b'a' * 20
    test_download.config.set_hops(1)

    assert not isinstance(test_download.tdef, TorrentDefNoMetainfo)
    await test_download.apply_ip_filter(True)
    test_download.handle.apply_ip_filter.assert_called_with(True)

    test_download.tdef = TorrentDefNoMetainfo(b'a' * 20, b'metainfo request')
    test_download.handle.reset_mock()
    test_download.apply_ip_filter(False)
    test_download.handle.apply_ip_filter.assert_not_called()


async def test_checkpoint_timeout(test_download):
    """
    Testing whether making a checkpoint times out when we receive no alert from libtorrent
    """
    test_download.futures['save_resume_data'] = [Future()]
    task = test_download.save_resume_data(timeout=.01)
    test_download.futures['save_resume_data'].pop(0)
    await sleep(0.2)
    assert task.done()


@patch.object(DownloadConfig, 'write', new_callable=MagicMock)
@patch('tribler.core.components.libtorrent.download_manager.download.hexlify', Mock(return_value=''))
def test_on_save_resume_data_alert_permission_denied(mocked_write: Mock, test_download):
    """
    Test that the `on_save_resume_data_alert` method doesn't raises an Exception in the case `DownloadConfig.write()`
    raises a PermissionError
    """
    mocked_write.side_effect = PermissionError()
    test_download.on_save_resume_data_alert(MagicMock())
    assert mocked_write.called


def test_get_tracker_status_unicode_decode_error(test_download: Download):
    """
    Sometimes a tracker entry raises UnicodeDecodeError while accessing it's values.
    The reason for this is unknown.
    In this test we ensures that this types of bugs don't affect `get_tracker_status` method.
    See: https://github.com/Tribler/tribler/issues/7036
    """

    test_download.handle = MagicMock(trackers=MagicMock(side_effect=UnicodeDecodeError('', b'', 0, 0, '')))
    test_download.get_tracker_status()

    assert test_download.handle.trackers.called


def test_process_alert_no_crash_exception(test_download: Download):
    """Test that in the case of an error in the method `process_alert`, NoCrashException raises"""
    with pytest.raises(NoCrashException):
        # `process_alert` raises "AttributeError: 'str' object has no attribute 'category'" first
        # because the alert 'alert' has wrong type.
        test_download.process_alert('alert', 'type')


def test_get_tracker_status_get_peer_info_error(test_download: Download):
    """ Test that in the case `handle.get_peer_info()` raises an exception, the
    result of `download.get_tracker_status()` be returned but without a piece of
    information about peers.
    """
    test_download.handle = MagicMock(
        is_valid=Mock(return_value=True),
        get_peer_info=Mock(side_effect=RuntimeError)
    )
    status = test_download.get_tracker_status()
    assert status


async def test_shutdown(test_download: Download):
    """ Test that the `shutdown` method closes the stream and clears the `futures` list."""
    test_download.stream = Mock()
    assert len(test_download.futures) == 4

    await test_download.shutdown()

    assert not test_download.futures
    assert test_download.stream.close.called


def test_file_piece_range_flat(test_download: Download) -> None:
    """
    Test if the piece range of a single-file torrent is correctly determined.
    """
    total_pieces = test_download.tdef.torrent_info.num_pieces()

    piece_range = test_download.file_piece_range(Path("video.avi"))

    assert piece_range == list(range(total_pieces))


def test_file_piece_range_minifiles(minifile_download: Download) -> None:
    """
    Test if the piece range of a file is correctly determined if multiple files exist in the same piece.
    """
    piece_range_a = minifile_download.file_piece_range(Path("data") / "a.txt")
    piece_range_b = minifile_download.file_piece_range(Path("data") / "b.txt")

    assert [0] == piece_range_a
    assert [0] == piece_range_b


def test_file_piece_range_wide(dual_movie_tdef: TorrentDef) -> None:
    """
    Test if the piece range of a two-file torrent is correctly determined.

    The torrent is no longer flat after adding content! Data is now in the "data" directory.
    """
    download = Download(dual_movie_tdef, checkpoint_disabled=True)

    piece_range_video = download.file_piece_range(Path("data") / TORRENT_VIDEO_FILE.name)
    piece_range_ubuntu = download.file_piece_range(Path("data") / TORRENT_UBUNTU_FILE.name)
    last_piece = piece_range_video[-1] + 1

    assert 0 < last_piece < download.tdef.torrent_info.num_pieces()
    assert piece_range_video == list(range(0, last_piece))
    assert piece_range_ubuntu == list(range(last_piece, download.tdef.torrent_info.num_pieces()))


def test_file_piece_range_nonexistent(test_download: Download) -> None:
    """
    Test if the piece range of a single-file torrent is correctly determined.
    """
    piece_range = test_download.file_piece_range(Path("I don't exist"))

    assert piece_range == []


def test_file_completion_full(test_download: Download) -> None:
    """
    Test if a complete file shows 1.0 completion.
    """
    test_download.handle = MagicMock(have_piece=Mock(return_value=True))

    assert 1.0 == test_download.get_file_completion(Path("video.avi"))


def test_file_completion_nonexistent(test_download: Download) -> None:
    """
    Test if an unknown path (does not exist in a torrent) shows 1.0 completion.
    """
    test_download.handle = MagicMock(have_piece=Mock(return_value=True))

    assert 1.0 == test_download.get_file_completion(Path("I don't exist"))


def test_file_completion_directory(dual_movie_tdef: TorrentDef) -> None:
    """
    Test if a directory (does not exist in a torrent) shows 1.0 completion.
    """
    download = Download(dual_movie_tdef, checkpoint_disabled=True)
    download.handle = MagicMock(have_piece=Mock(return_value=True))

    assert 1.0 == download.get_file_completion(Path("data"))


def test_file_completion_nohandle(test_download: Download) -> None:
    """
    Test if a file shows 0.0 completion if the torrent handle is not valid.
    """
    test_download.handle = MagicMock(is_valid=Mock(return_value=False))

    assert 0.0 == test_download.get_file_completion(Path("video.avi"))


def test_file_completion_partial(test_download: Download) -> None:
    """
    Test if a file shows 0.0 completion if the torrent handle is not valid.
    """
    total_pieces = test_download.tdef.torrent_info.num_pieces()
    expected = (total_pieces // 2) / total_pieces

    def fake_has_piece(piece_index: int) -> bool:
        return piece_index > total_pieces / 2  # total_pieces // 2 will return True

    test_download.handle = MagicMock(have_piece=fake_has_piece)

    result = test_download.get_file_completion(Path("video.avi"))

    assert round(expected, 4) == round(result, 4)  # Round to make sure we don't get float rounding errors


def test_file_length(test_download: Download) -> None:
    """
    Test if we can get the length of a file.
    """
    assert 1942100 == test_download.get_file_length(Path("video.avi"))


def test_file_length_two(dual_movie_tdef: TorrentDef) -> None:
    """
    Test if we can get the length of a file in a two-file torrent.
    """
    download = Download(dual_movie_tdef, checkpoint_disabled=True)

    assert 291888 == download.get_file_length(Path("data") / TORRENT_VIDEO_FILE.name)
    assert 44258 == download.get_file_length(Path("data") / TORRENT_UBUNTU_FILE.name)


def test_file_length_nonexistent(test_download: Download) -> None:
    """
    Test if the length of a non-existent file is 0.
    """
    assert 0 == test_download.get_file_length(Path("I don't exist"))


def test_file_index_unloaded(test_download: Download) -> None:
    """
    Test if a non-existent path leads to the special unloaded index.
    """
    assert IllegalFileIndex.unloaded.value == test_download.get_file_index(Path("I don't exist"))


def test_file_index_directory_collapsed(dual_movie_tdef: TorrentDef) -> None:
    """
    Test if a collapsed-dir path leads to the special collapsed dir index.
    """
    download = Download(dual_movie_tdef, checkpoint_disabled=True)

    assert IllegalFileIndex.collapsed_dir.value == download.get_file_index(Path("data"))


def test_file_index_directory_expanded(dual_movie_tdef: TorrentDef) -> None:
    """
    Test if a expanded-dir path leads to the special expanded dir index.
    """
    download = Download(dual_movie_tdef, checkpoint_disabled=True)
    download.tdef.torrent_file_tree.expand(Path("data"))

    assert IllegalFileIndex.expanded_dir.value == download.get_file_index(Path("data"))


def test_file_index_file(test_download: Download) -> None:
    """
    Test if we can get the index of a file.
    """
    assert 0 == test_download.get_file_index(Path("video.avi"))


def test_file_selected_nonexistent(test_download: Download) -> None:
    """
    Test if a non-existent file does not register as selected.
    """
    assert not test_download.is_file_selected(Path("I don't exist"))


def test_file_selected_realfile(test_download: Download) -> None:
    """
    Test if a file starts off as selected.
    """
    assert test_download.is_file_selected(Path("video.avi"))


def test_file_selected_directory(dual_movie_tdef: TorrentDef) -> None:
    """
    Test if a directory does not register as selected.
    """
    download = Download(dual_movie_tdef, checkpoint_disabled=True)

    assert not download.is_file_selected(Path("data"))


def test_on_torrent_finished_alert(test_download: Download):
    """ Test if the torrent_finished notification is called when the torrent finishes."""

    test_download.handle = Mock(is_valid=Mock(return_value=True))
    test_download.notifier = MagicMock()
    test_download.stream = Mock()
    test_download.get_state = Mock(return_value=Mock(total_download=1))

    test_download.on_torrent_finished_alert(Mock())

    # Check if the notification was called
    assert test_download.notifier[notifications.torrent_finished].called_with(
        infohash=test_download.tdef.get_infohash().hex(),
        name=test_download.tdef.get_name_as_unicode(),
        hidden=test_download.hidden
    )
