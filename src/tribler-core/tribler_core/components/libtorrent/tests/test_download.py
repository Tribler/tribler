from asyncio import Future, sleep
from pathlib import Path
from unittest.mock import Mock

from ipv8.util import succeed

import libtorrent as lt
from libtorrent import bencode

import pytest

from tribler_core.exceptions import SaveResumeDataError
from tribler_core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.components.libtorrent.utils.torrent_utils import get_info_from_handle
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import bdecode_compat


def test_download_properties(test_download, test_tdef):
    assert not test_download.get_magnet_link()
    assert test_download.tdef, test_tdef


def test_download_get_atp(mock_dlmgr, test_download):
    assert isinstance(test_download.get_atp(), dict)


def test_download_resume(mock_handle, mock_download_config, test_download):
    test_download.resume()
    test_download.handle.resume.assert_called()


@pytest.mark.asyncio
async def test_download_resume_in_upload_mode(mock_handle, mock_download_config, test_download):
    await test_download.set_upload_mode(True)
    test_download.resume()
    test_download.handle.set_upload_mode.assert_called_with(test_download.get_upload_mode())


@pytest.mark.asyncio
async def test_save_resume(mock_handle, test_download, test_tdef):
    """
    testing call resume data alert
    """
    mock_handle.is_valid = lambda: True
    mock_handle.save_resume_data = lambda: test_download.register_task('post_alert', test_download.process_alert, alert,
                                                                       'save_resume_data_alert', delay=0.1)

    alert = Mock(resume_data={b'info-hash': test_tdef.get_infohash()})
    await test_download.save_resume_data()
    basename = hexlify(test_tdef.get_infohash()) + '.conf'
    filename = test_download.dlmgr.get_checkpoint_dir() / basename
    dcfg = DownloadConfig.load(str(filename))
    assert test_tdef.get_infohash(), dcfg.get_engineresumedata().get(b'info-hash')


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


@pytest.mark.asyncio
async def test_save_checkpoint(test_download, test_tdef):
    await test_download.checkpoint()
    basename = hexlify(test_tdef.get_infohash()) + '.conf'
    filename = Path(test_download.dlmgr.get_checkpoint_dir() / basename)
    assert filename.is_file()


def test_selected_files(mock_handle, test_download):
    """
    Test whether the selected files are set correctly
    """
    def mocked_set_file_prios(_):
        mocked_set_file_prios.called = True

    mocked_set_file_prios.called = False

    mocked_file = MockObject()
    mocked_file.path = 'my/path'
    mock_torrent_info = MockObject()
    mock_torrent_info.files = lambda: [mocked_file, mocked_file]
    test_download.handle.prioritize_files = mocked_set_file_prios
    test_download.handle.get_torrent_info = lambda: mock_torrent_info
    test_download.handle.rename_file = lambda *_: None

    test_download.get_share_mode = lambda: False
    test_download.tdef.get_infohash = lambda: b'a' * 20
    test_download.set_selected_files([0])
    assert mocked_set_file_prios.called

    test_download.get_share_mode = lambda: False
    mocked_set_file_prios.called = False
    assert not mocked_set_file_prios.called


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


@pytest.mark.asyncio
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
            seeder.flags = 140347   # some value where seed flag(1024) is true
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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

    test_download.handle.status().pieces = [True * 16]
    assert test_download.get_pieces_base64() == b"gA=="


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_checkpoint_timeout(test_download):
    """
    Testing whether making a checkpoint times out when we receive no alert from libtorrent
    """
    test_download.futures['save_resume_data'] = [Future()]
    task = test_download.save_resume_data(timeout=.01)
    test_download.futures['save_resume_data'].pop(0)
    await sleep(0.2)
    assert task.done()
