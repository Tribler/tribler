from asyncio import Future, sleep
from unittest import skipIf
from unittest.mock import Mock

import libtorrent as lt
from libtorrent import bencode

from tribler_common.simpledefs import DLMODE_VOD, DLSTATUS_DOWNLOADING

from tribler_core.exceptions import SaveResumeDataError
from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.libtorrent_download_impl import LibtorrentDownloadImpl
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities import path_util
from tribler_core.utilities.torrent_utils import get_info_from_handle
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import bdecode_compat, succeed


class TestLibtorrentDownloadImpl(TestAsServer):
    """
    This class provides unit tests that test the LibtorrentDownloadImpl class.
    """

    def setUpPreSession(self):
        super(TestLibtorrentDownloadImpl, self).setUpPreSession()
        self.config.set_torrent_checking_enabled(False)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_libtorrent_enabled(True)
        self.config.set_video_server_enabled(False)

    def create_tdef(self):
        """
        create and save torrent definition used in this test file
        """
        tdef = TorrentDef()
        sourcefn = TESTS_DATA_DIR / 'video.avi'
        tdef.add_content(sourcefn)
        tdef.set_tracker("http://localhost/announce")
        torrentfn = self.session.config.get_state_dir() / "gen.torrent"
        tdef.save(torrentfn)

        return tdef

    def test_get_magnet_link_none(self):
        tdef = self.create_tdef()

        impl = LibtorrentDownloadImpl(self.session, tdef)
        link = impl.get_magnet_link()
        self.assertEqual(None, link, "Magnet link was not none while it should be!")

    def test_get_tdef(self):
        tdef = self.create_tdef()

        impl = LibtorrentDownloadImpl(self.session, None)
        impl.set_def(tdef)
        self.assertEqual(impl.tdef, tdef, "Torrent definitions were not equal!")

    @timeout(20)
    async def test_setup(self):
        tdef = self.create_tdef()
        impl = LibtorrentDownloadImpl(self.session, tdef)
        impl.setup(None, 0)
        impl.cancel_all_pending_tasks()
        impl.stop()

    async def test_resume(self):
        tdef = self.create_tdef()
        impl = LibtorrentDownloadImpl(self.session, tdef)
        impl.config = Mock()
        impl.handle = Mock()
        impl.resume()
        impl.handle.resume.assert_called()

    async def test_resume_in_upload_mode(self):
        tdef = self.create_tdef()
        impl = LibtorrentDownloadImpl(self.session, tdef)
        impl.config = Mock()
        impl.handle = Mock()
        await impl.set_upload_mode(True)
        self.assertTrue(impl.get_upload_mode())
        impl.resume()
        impl.handle.resume.assert_called()
        impl.handle.set_upload_mode.assert_called_with(impl.get_upload_mode())

    @timeout(20)
    async def test_multifile_torrent(self):
        # Achtung! This test is completely and utterly broken, as is the whole libtorrent wrapper!
        # Don't try to understand it, it is a legacy thing!

        tdef = TorrentDef()

        tdef.add_content(TESTS_DATA_DIR / "video.avi")
        tdef.set_tracker("http://tribler.org/announce")
        tdef.save()

        fake_handler = MockObject()
        fake_handler.is_valid = lambda: True
        fake_handler.status = lambda: fake_status
        fake_handler.set_share_mode = lambda _: None
        fake_handler.set_priority = lambda _: None
        fake_handler.set_sequential_download = lambda _: None
        fake_handler.resume = lambda: None
        fake_handler.set_max_connections = lambda _: None
        fake_handler.apply_ip_filter = lambda _: None
        fake_handler.save_resume_data = lambda: None
        fake_status = MockObject()
        fake_status.share_mode = False
        impl = LibtorrentDownloadImpl(self.session, tdef)
        impl.set_selected_files = lambda: None
        impl.future_added = succeed(fake_handler)
        # Create a dummy download config
        impl.config = DownloadConfig()
        impl.config.set_engineresumedata({b"save_path": path_util.abspath(self.state_dir),
                                          b"info-hash": b'\x00' * 20})
        impl.setup()

        impl.config.set_engineresumedata({b"save_path": path_util.abspath(self.state_dir),
                                          b"info-hash": b'\x00' * 20})
        impl.setup()

        impl.config.set_engineresumedata({b"save_path": "some_local_dir",
                                          b"info-hash": b'\x00' * 20})
        impl.setup()

    @timeout(10)
    async def test_save_resume(self):
        """
        testing call resume data alert
        """
        tdef = self.create_tdef()
        alert = Mock(resume_data={b'info-hash': tdef.get_infohash()})
        impl = LibtorrentDownloadImpl(self.session, tdef)
        impl.setup()
        impl.handle = MockObject()
        impl.handle.is_valid = lambda: True
        impl.handle.save_resume_data = lambda: impl.register_task('post_alert', impl.process_alert, alert,
                                                                  'save_resume_data_alert', delay=0.1)
        await impl.save_resume_data()
        basename = hexlify(tdef.get_infohash()) + '.conf'
        filename = self.session.ltmgr.get_checkpoint_dir() / basename
        dcfg = DownloadConfig.load(filename)
        self.assertEqual(tdef.get_infohash(), dcfg.get_engineresumedata().get(b'info-hash'))

    @timeout(10)
    async def test_save_resume_disabled(self):
        """
        testing call resume data alert, if checkpointing is disabled
        """
        tdef = self.create_tdef()
        impl = LibtorrentDownloadImpl(self.session, tdef)

        # This should not cause a checkpoint
        impl.setup(None, 0, checkpoint_disabled=True)
        basename = hexlify(tdef.get_infohash()) + '.state'
        filename = self.session.ltmgr.get_checkpoint_dir() / basename
        self.assertFalse(filename.is_file())

        # This shouldn't either
        await impl.checkpoint()
        self.assertFalse(filename.is_file())
        impl.stop()


class TestLibtorrentDownloadImplNoSession(TriblerCoreTest):

    async def setUp(self):
        await TriblerCoreTest.setUp(self)
        self.libtorrent_download_impl = LibtorrentDownloadImpl(Mock(), None)
        mock_handle = MockObject()
        mock_status = MockObject()
        mock_status.pieces = [True, False, True, True, False]
        torrent_info = MockObject()
        file_info = MockObject()
        file_info.size = 1234
        torrent_info.file_at = lambda _: file_info
        map_file_result = MockObject()
        map_file_result.piece = 123
        torrent_info.map_file = lambda _dummy1, _dummy2, _dummy3: map_file_result
        torrent_info.num_pieces = lambda: 5

        mock_handle.is_valid = lambda: True
        mock_handle.status = lambda: mock_status
        mock_handle.get_torrent_info = lambda: torrent_info
        mock_handle.set_sequential_download = lambda _: None
        mock_handle.set_priority = lambda _: None
        mock_handle.prioritize_pieces = lambda _: None
        mock_handle.save_resume_data = lambda: None

        self.libtorrent_download_impl.handle = mock_handle

        # Create a fake tdef
        self.libtorrent_download_impl.tdef = MockObject()
        self.libtorrent_download_impl.tdef.get_name = lambda: "ubuntu.iso"
        self.libtorrent_download_impl.tdef.get_name_as_unicode = lambda: "ubuntu.iso"
        self.libtorrent_download_impl.tdef.get_infohash = lambda: b'a' * 20
        self.libtorrent_download_impl.tdef.is_multifile_torrent = lambda: False

        self.libtorrent_download_impl.config = DownloadConfig()

    async def tearDown(self):
        await self.libtorrent_download_impl.shutdown_task_manager()
        await super(TestLibtorrentDownloadImplNoSession, self).tearDown()

    def test_selected_files(self):
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
        self.libtorrent_download_impl.handle.prioritize_files = mocked_set_file_prios
        self.libtorrent_download_impl.handle.get_torrent_info = lambda: mock_torrent_info
        self.libtorrent_download_impl.handle.rename_file = lambda *_: None

        self.libtorrent_download_impl.get_share_mode = lambda: False
        self.libtorrent_download_impl.tdef.get_infohash = lambda: b'a' * 20
        self.libtorrent_download_impl.orig_files = ['my/a', 'my/b']
        self.libtorrent_download_impl.set_selected_files(['a'])
        self.assertTrue(mocked_set_file_prios.called)

        self.libtorrent_download_impl.get_share_mode = lambda: False
        mocked_set_file_prios.called = False
        self.assertFalse(mocked_set_file_prios.called)

    def test_selected_files_no_files(self):
        """
        Test that no files are selected if torrent info is not available.
        """
        def mocked_set_file_prios(_):
            mocked_set_file_prios.called = True

        mocked_set_file_prios.called = False

        mocked_file = MockObject()
        mocked_file.path = 'my/path'
        mock_torrent_info = MockObject()
        self.libtorrent_download_impl.handle.prioritize_files = mocked_set_file_prios
        self.libtorrent_download_impl.handle.get_torrent_info = lambda: mock_torrent_info
        self.libtorrent_download_impl.handle.rename_file = lambda *_: None
        self.libtorrent_download_impl.tdef.get_infohash = lambda: b'a' * 20
        self.libtorrent_download_impl.orig_files = ['a', 'b']

        # If share mode is not enabled and everything else is fine, file priority should be set
        # when set_selected_files() is called. But in this test, no files attribute is set in torrent info
        # in order to test AttributeError, therfore, no call to set file priority is expected.
        self.libtorrent_download_impl.get_share_mode = lambda: False
        self.libtorrent_download_impl.set_selected_files(['a'])
        self.assertFalse(mocked_set_file_prios.called)

    def test_get_share_mode(self):
        """
        Test whether we return the right share mode when requested in the LibtorrentDownloadImpl
        """
        self.libtorrent_download_impl.config.get_share_mode = lambda: False
        self.assertFalse(self.libtorrent_download_impl.get_share_mode())
        self.libtorrent_download_impl.config.get_share_mode = lambda: True
        self.assertTrue(self.libtorrent_download_impl.get_share_mode())

    async def test_set_share_mode(self):
        """
        Test whether we set the right share mode in LibtorrentDownloadImpl
        """
        def mocked_set_share_mode(val):
            self.assertTrue(val)
            mocked_set_share_mode.called = True

        mocked_set_share_mode.called = False
        self.libtorrent_download_impl.handle.set_share_mode = mocked_set_share_mode
        await self.libtorrent_download_impl.set_share_mode(True)
        self.assertTrue(mocked_set_share_mode.called)

    def test_get_num_connected_seeds_peers(self):
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
        self.libtorrent_download_impl.handle.get_peer_info = lambda: get_peer_info(mock_seeders, mock_leechers)

        num_seeds, num_peers = self.libtorrent_download_impl.get_num_connected_seeds_peers()
        self.assertEqual(num_seeds, mock_seeders, "Expected seeders differ")
        self.assertEqual(num_peers, mock_leechers, "Expected peers differ")

    async def test_set_priority(self):
        """
        Test whether setting the priority calls the right methods in LibtorrentDownloadImpl
        """
        def mocked_set_priority(prio):
            self.assertEqual(prio, 1234)
            mocked_set_priority.called = True

        mocked_set_priority.called = False
        self.libtorrent_download_impl.handle.set_priority = mocked_set_priority
        await self.libtorrent_download_impl.set_priority(1234)
        self.assertTrue(mocked_set_priority.called)

    def test_add_trackers(self):
        """
        Testing whether trackers are added to the libtorrent handler in LibtorrentDownloadImpl
        """
        def mocked_add_trackers(tracker_info):
            self.assertIsInstance(tracker_info, dict)
            self.assertEqual(tracker_info['url'], 'http://google.com')
            mocked_add_trackers.called = True

        mocked_add_trackers.called = False
        self.libtorrent_download_impl.handle.add_tracker = mocked_add_trackers
        self.libtorrent_download_impl.add_trackers(['http://google.com'])
        self.assertTrue(mocked_add_trackers.called)

    def test_process_error_alert(self):
        """
        Testing whether error alerts are processed correctly
        """
        url = "http://google.com"
        mock_alert = MockObject()
        mock_alert.msg = None
        mock_alert.category = lambda: lt.alert.category_t.error_notification
        mock_alert.status_code = 123
        mock_alert.url = url
        self.libtorrent_download_impl.process_alert(mock_alert, 'tracker_error_alert')
        self.assertEqual(self.libtorrent_download_impl.tracker_status[url][1], 'HTTP status code 123')

        mock_alert.status_code = 0
        self.libtorrent_download_impl.process_alert(mock_alert, 'tracker_error_alert')
        self.assertEqual(self.libtorrent_download_impl.tracker_status[url][1], 'Timeout')

    def test_tracker_warning_alert(self):
        """
        Test whether a tracking warning alert is processed correctly
        """
        url = "http://google.com"
        mock_alert = MockObject()
        mock_alert.category = lambda: lt.alert.category_t.error_notification
        mock_alert.url = url
        mock_alert.message = lambda: 'test'
        self.libtorrent_download_impl.process_alert(mock_alert, 'tracker_warning_alert')
        self.assertEqual(self.libtorrent_download_impl.tracker_status[url][1], 'Warning: test')

    @timeout(10)
    async def test_on_metadata_received_alert(self):
        """
        Testing whether the right operations happen when we receive metadata
        """
        test_future = Future()

        mocked_file = MockObject()
        mocked_file.path = 'test'

        self.libtorrent_download_impl.handle.trackers = lambda: []
        self.libtorrent_download_impl.handle.get_peer_info = lambda: []
        self.libtorrent_download_impl.handle.save_resume_data = lambda: test_future
        self.libtorrent_download_impl.handle.rename_file = lambda *_: None
        with open(TESTS_DATA_DIR / "bak_single.torrent", mode='rb') as torrent_file:
            encoded_metainfo = torrent_file.read()
        decoded_metainfo = bdecode_compat(encoded_metainfo)
        get_info_from_handle(self.libtorrent_download_impl.handle).metadata = lambda: bencode(decoded_metainfo[b'info'])
        get_info_from_handle(self.libtorrent_download_impl.handle).files = lambda: [mocked_file]

        self.libtorrent_download_impl.checkpoint = lambda: test_future.set_result(None)
        self.libtorrent_download_impl.session = MockObject()
        self.libtorrent_download_impl.session = MockObject()
        self.libtorrent_download_impl.session.torrent_db = None
        self.libtorrent_download_impl.handle.save_path = lambda: None
        self.libtorrent_download_impl.handle.prioritize_files = lambda _: None
        self.libtorrent_download_impl.get_share_mode = lambda: False
        self.libtorrent_download_impl.on_metadata_received_alert(None)

        await test_future

    def test_metadata_received_invalid_info(self):
        """
        Testing whether the right operations happen when we receive metadata but the torrent info is invalid
        """
        def mocked_checkpoint():
            raise RuntimeError("This code should not be reached!")

        self.libtorrent_download_impl.checkpoint = mocked_checkpoint
        self.libtorrent_download_impl.handle.get_torrent_info = lambda: None
        self.libtorrent_download_impl.on_metadata_received_alert(None)

    def test_metadata_received_invalid_torrent_with_value_error(self):
        """
        Testing whether the right operations happen when we receive metadata but the torrent info is invalid and throws
        Value Error
        """
        def mocked_checkpoint():
            raise RuntimeError("This code should not be reached!")

        mocked_file = MockObject()
        mocked_file.path = 'test'

        # The line below should trigger Value Error
        self.libtorrent_download_impl.handle.trackers = lambda: [{'url': 'no-DHT'}]
        self.libtorrent_download_impl.handle.get_peer_info = lambda: []

        get_info_from_handle(self.libtorrent_download_impl.handle).metadata = lambda: lt.bencode({})
        get_info_from_handle(self.libtorrent_download_impl.handle).files = lambda: [mocked_file]

        self.libtorrent_download_impl.checkpoint = mocked_checkpoint
        self.libtorrent_download_impl.on_metadata_received_alert(None)

    def test_torrent_checked_alert(self):
        """
        Testing whether the right operations happen after a torrent checked alert is received
        """
        def mocked_pause_checkpoint():
            mocked_pause_checkpoint.called = True
            return succeed(None)

        mocked_pause_checkpoint.called = False
        self.libtorrent_download_impl.handle.pause = mocked_pause_checkpoint
        self.libtorrent_download_impl.checkpoint = mocked_pause_checkpoint

        mock_alert = MockObject()
        mock_alert.category = lambda: lt.alert.category_t.error_notification
        self.libtorrent_download_impl.pause_after_next_hashcheck = True
        self.libtorrent_download_impl.process_alert(mock_alert, 'torrent_checked_alert')
        self.assertFalse(self.libtorrent_download_impl.pause_after_next_hashcheck)
        self.assertTrue(mocked_pause_checkpoint.called)

        mocked_pause_checkpoint.called = False
        self.libtorrent_download_impl.checkpoint_after_next_hashcheck = True
        self.libtorrent_download_impl.process_alert(mock_alert, 'torrent_checked_alert')
        self.assertFalse(self.libtorrent_download_impl.checkpoint_after_next_hashcheck)
        self.assertTrue(mocked_pause_checkpoint.called)

    def test_get_vod_fileindex(self):
        """
        Testing whether the right vod file index is returned in LibtorrentDownloadImpl
        """
        self.libtorrent_download_impl.vod_index = None
        self.assertEqual(self.libtorrent_download_impl.get_vod_fileindex(), -1)
        self.libtorrent_download_impl.vod_index = 42
        self.assertEqual(self.libtorrent_download_impl.get_vod_fileindex(), 42)

    def test_get_vod_filesize(self):
        """
        Testing whether the right vod file size is returned in LibtorrentDownloadImpl
        """
        mock_file_entry = MockObject()
        mock_file_entry.size = 42
        mock_torrent_info = MockObject()
        mock_torrent_info.file_at = lambda _: mock_file_entry
        self.libtorrent_download_impl.handle.get_torrent_info = lambda: mock_torrent_info

        self.libtorrent_download_impl.vod_index = None
        self.assertEqual(self.libtorrent_download_impl.get_vod_filesize(), 0)
        self.libtorrent_download_impl.vod_index = 42
        self.assertEqual(self.libtorrent_download_impl.get_vod_filesize(), 42)

    def test_get_piece_progress(self):
        """
        Testing whether the right piece progress is returned in LibtorrentDownloadImpl
        """
        self.assertEqual(self.libtorrent_download_impl.get_piece_progress(None), 1.0)

        self.libtorrent_download_impl.handle.status().pieces = [True, False]
        self.assertEqual(self.libtorrent_download_impl.get_piece_progress([0, 1], True), 0.5)

        self.libtorrent_download_impl.handle.status = lambda: None
        self.assertEqual(self.libtorrent_download_impl.get_piece_progress([3, 1]), 0.0)

    def test_get_byte_progress(self):
        """
        Testing whether the right byte progress is returned in LibtorrentDownloadImpl
        """
        self.assertEqual(self.libtorrent_download_impl.get_byte_progress([(-1, 0, 0)], False), 1.0)

        # Scenario: we have a file with 4 pieces, 250 bytes in each piece.
        def map_file(_dummy1, start_byte, _dummy2):
            res = MockObject()
            res.piece = int(start_byte / 250)
            return res

        self.libtorrent_download_impl.handle.get_torrent_info().num_pieces = lambda: 4
        self.libtorrent_download_impl.handle.get_torrent_info().map_file = map_file
        self.assertEqual(self.libtorrent_download_impl.get_byte_progress([(0, 10, 270)], True), 0.5)

    def test_setup_exception(self):
        """
        Testing whether an exception in the setup method of LibtorrentDownloadImpl is handled correctly
        """
        with self.assertRaises(Exception):
            self.libtorrent_download_impl.setup()

    def test_tracker_reply_alert(self):
        """
        Testing the tracker reply alert in LibtorrentDownloadImpl
        """
        mock_alert = MockObject()
        mock_alert.url = 'http://google.com'
        mock_alert.num_peers = 42
        self.libtorrent_download_impl.on_tracker_reply_alert(mock_alert)
        self.assertEqual(self.libtorrent_download_impl.tracker_status['http://google.com'], [42, 'Working'])

    def test_download_finish_alert(self):
        """
        Testing whether the right operations are performed when we get a torrent finished alert
        """
        status = self.libtorrent_download_impl.handle.status()
        status.paused = False
        status.state = DLSTATUS_DOWNLOADING
        status.progress = 0.9
        status.error = None
        status.total_wanted = 33
        status.download_payload_rate = 928
        status.upload_payload_rate = 928
        status.all_time_upload = 42
        status.all_time_download = 43
        status.finished_time = 1234
        status.total_download = 0

        # Scenario: we have a file with 4 pieces, 250 bytes in each piece.
        def map_file(_dummy1, start_byte, _dummy2):
            res = MockObject()
            res.piece = int(start_byte / 250)
            return res

        self.libtorrent_download_impl.handle.get_torrent_info().num_pieces = lambda: 4
        self.libtorrent_download_impl.handle.get_torrent_info().map_file = map_file
        self.libtorrent_download_impl.handle.piece_priorities = lambda: [0, 0, 0, 0]
        self.libtorrent_download_impl.handle.save_resume_data = lambda: None
        self.libtorrent_download_impl.handle.need_save_resume_data = lambda: None

        self.libtorrent_download_impl.set_vod_mode(True)
        self.libtorrent_download_impl.config.set_mode(DLMODE_VOD)
        self.libtorrent_download_impl.on_torrent_finished_alert(None)

        has_priorities_task = False
        for task_name in self.libtorrent_download_impl._pending_tasks:
            if 'reset_priorities' in task_name:
                has_priorities_task = True
        self.assertTrue(has_priorities_task)

    def test_get_pieces_bitmask(self):
        """
        Testing whether a correct pieces bitmask is returned when requested
        """
        self.libtorrent_download_impl.handle.status().pieces = [True, False, True, False, False]
        self.assertEqual(self.libtorrent_download_impl.get_pieces_base64(), b"oA==")

        self.libtorrent_download_impl.handle.status().pieces = [True * 16]
        self.assertEqual(self.libtorrent_download_impl.get_pieces_base64(), b"gA==")

    async def test_resume_data_failed(self):
        """
        Testing whether the correct operations happen when an error is raised during resume data saving
        """
        mock_alert = Mock(msg="test error")
        impl = self.libtorrent_download_impl
        impl.register_task('post_alert', impl.process_alert, mock_alert, 'save_resume_data_failed_alert', delay=0.1)
        with self.assertRaises(SaveResumeDataError):
            await impl.wait_for_alert('save_resume_data_alert', None,
                                      'save_resume_data_failed_alert', lambda _: SaveResumeDataError())

    def test_on_state_changed(self):
        self.libtorrent_download_impl.handle.status = lambda: Mock(error=None)
        self.libtorrent_download_impl.tdef.get_infohash = lambda: b'a' * 20
        self.libtorrent_download_impl.config.set_hops(1)
        self.libtorrent_download_impl.apply_ip_filter = Mock()
        self.libtorrent_download_impl.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=4)))
        self.libtorrent_download_impl.apply_ip_filter.assert_called_with(False)

        self.libtorrent_download_impl.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=5)))
        self.libtorrent_download_impl.apply_ip_filter.assert_called_with(True)

        self.libtorrent_download_impl.config.set_hops(0)
        self.libtorrent_download_impl.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=4)))
        self.libtorrent_download_impl.apply_ip_filter.assert_called_with(False)

        self.libtorrent_download_impl.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=5)))
        self.libtorrent_download_impl.apply_ip_filter.assert_called_with(False)

    async def test_checkpoint_timeout(self):
        """
        Testing whether making a checkpoint times out when we receive no alert from libtorrent
        """
        self.libtorrent_download_impl._on_resume_err = Mock()
        self.libtorrent_download_impl.futures['save_resume_data'] = [Future()]
        task = self.libtorrent_download_impl.save_resume_data(timeout=.01)
        self.libtorrent_download_impl.futures['save_resume_data'].pop(0)
        await sleep(0.2)
        self.assertTrue(task.done())
