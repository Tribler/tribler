from asyncio import Future, sleep
from unittest.mock import Mock

import libtorrent as lt
from libtorrent import bencode

from tribler_core.exceptions import SaveResumeDataError
from tribler_core.modules.libtorrent.download import Download
from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities import path_util
from tribler_core.utilities.torrent_utils import get_info_from_handle
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import bdecode_compat, succeed


class TestDownload(TestAsServer):
    """
    This class provides unit tests that test the Download class.
    """

    def setUpPreSession(self):
        super(TestDownload, self).setUpPreSession()
        self.config.set_torrent_checking_enabled(False)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_libtorrent_enabled(True)

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

        dl = Download(self.session, tdef)
        link = dl.get_magnet_link()
        self.assertEqual(None, link, "Magnet link was not none while it should be!")

    def test_get_tdef(self):
        tdef = self.create_tdef()

        dl = Download(self.session, None)
        dl.set_def(tdef)
        self.assertEqual(dl.tdef, tdef, "Torrent definitions were not equal!")

    @timeout(20)
    async def test_setup(self):
        tdef = self.create_tdef()
        dl = Download(self.session, tdef)
        dl.setup(None, 0)
        dl.cancel_all_pending_tasks()
        dl.stop()

    async def test_resume(self):
        tdef = self.create_tdef()
        dl = Download(self.session, tdef)
        dl.config = Mock()
        dl.handle = Mock()
        dl.resume()
        dl.handle.resume.assert_called()

    async def test_resume_in_upload_mode(self):
        tdef = self.create_tdef()
        dl = Download(self.session, tdef)
        dl.config = Mock()
        dl.handle = Mock()
        await dl.set_upload_mode(True)
        self.assertTrue(dl.get_upload_mode())
        dl.resume()
        dl.handle.resume.assert_called()
        dl.handle.set_upload_mode.assert_called_with(dl.get_upload_mode())

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
        dl = Download(self.session, tdef)
        dl.set_selected_files = lambda: None
        dl.future_added = succeed(fake_handler)
        # Create a dummy download config
        dl.config = DownloadConfig()
        dl.config.set_engineresumedata({b"save_path": path_util.abspath(self.state_dir),
                                        b"info-hash": b'\x00' * 20})
        dl.setup()

        dl.config.set_engineresumedata({b"save_path": path_util.abspath(self.state_dir),
                                        b"info-hash": b'\x00' * 20})
        dl.setup()

        dl.config.set_engineresumedata({b"save_path": "some_local_dir",
                                        b"info-hash": b'\x00' * 20})
        dl.setup()

    @timeout(10)
    async def test_save_resume(self):
        """
        testing call resume data alert
        """
        tdef = self.create_tdef()
        alert = Mock(resume_data={b'info-hash': tdef.get_infohash()})
        dl = Download(self.session, tdef)
        dl.setup()
        dl.handle = MockObject()
        dl.handle.is_valid = lambda: True
        dl.handle.save_resume_data = lambda: dl.register_task('post_alert', dl.process_alert, alert,
                                                              'save_resume_data_alert', delay=0.1)
        await dl.save_resume_data()
        basename = hexlify(tdef.get_infohash()) + '.conf'
        filename = self.session.dlmgr.get_checkpoint_dir() / basename
        dcfg = DownloadConfig.load(filename)
        self.assertEqual(tdef.get_infohash(), dcfg.get_engineresumedata().get(b'info-hash'))

    @timeout(10)
    async def test_save_resume_disabled(self):
        """
        testing call resume data alert, if checkpointing is disabled
        """
        tdef = self.create_tdef()
        dl = Download(self.session, tdef)

        # This should not cause a checkpoint
        dl.setup(None, 0, checkpoint_disabled=True)
        basename = hexlify(tdef.get_infohash()) + '.state'
        filename = self.session.dlmgr.get_checkpoint_dir() / basename
        self.assertFalse(filename.is_file())

        # This shouldn't either
        await dl.checkpoint()
        self.assertFalse(filename.is_file())
        dl.stop()


class TestDownloadNoSession(TriblerCoreTest):

    async def setUp(self):
        await TriblerCoreTest.setUp(self)
        self.download = Download(Mock(), None)
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

        self.download.handle = mock_handle

        # Create a fake tdef
        self.download.tdef = MockObject()
        self.download.tdef.get_name = lambda: "ubuntu.iso"
        self.download.tdef.get_name_as_unicode = lambda: "ubuntu.iso"
        self.download.tdef.get_infohash = lambda: b'a' * 20
        self.download.tdef.is_multifile_torrent = lambda: False

        self.download.config = DownloadConfig()

    async def tearDown(self):
        await self.download.shutdown_task_manager()
        await super(TestDownloadNoSession, self).tearDown()

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
        self.download.handle.prioritize_files = mocked_set_file_prios
        self.download.handle.get_torrent_info = lambda: mock_torrent_info
        self.download.handle.rename_file = lambda *_: None

        self.download.get_share_mode = lambda: False
        self.download.tdef.get_infohash = lambda: b'a' * 20
        self.download.set_selected_files([0])
        self.assertTrue(mocked_set_file_prios.called)

        self.download.get_share_mode = lambda: False
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
        self.download.handle.prioritize_files = mocked_set_file_prios
        self.download.handle.get_torrent_info = lambda: mock_torrent_info
        self.download.handle.rename_file = lambda *_: None
        self.download.tdef.get_infohash = lambda: b'a' * 20

        # If share mode is not enabled and everything else is fine, file priority should be set
        # when set_selected_files() is called. But in this test, no files attribute is set in torrent info
        # in order to test AttributeError, therfore, no call to set file priority is expected.
        self.download.get_share_mode = lambda: False
        self.download.set_selected_files([0])
        self.assertFalse(mocked_set_file_prios.called)

    def test_get_share_mode(self):
        """
        Test whether we return the right share mode when requested in the Download
        """
        self.download.config.get_share_mode = lambda: False
        self.assertFalse(self.download.get_share_mode())
        self.download.config.get_share_mode = lambda: True
        self.assertTrue(self.download.get_share_mode())

    async def test_set_share_mode(self):
        """
        Test whether we set the right share mode in Download
        """
        def mocked_set_share_mode(val):
            self.assertTrue(val)
            mocked_set_share_mode.called = True

        mocked_set_share_mode.called = False
        self.download.handle.set_share_mode = mocked_set_share_mode
        await self.download.set_share_mode(True)
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
        self.download.handle.get_peer_info = lambda: get_peer_info(mock_seeders, mock_leechers)

        num_seeds, num_peers = self.download.get_num_connected_seeds_peers()
        self.assertEqual(num_seeds, mock_seeders, "Expected seeders differ")
        self.assertEqual(num_peers, mock_leechers, "Expected peers differ")

    async def test_set_priority(self):
        """
        Test whether setting the priority calls the right methods in Download
        """
        def mocked_set_priority(prio):
            self.assertEqual(prio, 1234)
            mocked_set_priority.called = True

        mocked_set_priority.called = False
        self.download.handle.set_priority = mocked_set_priority
        await self.download.set_priority(1234)
        self.assertTrue(mocked_set_priority.called)

    def test_add_trackers(self):
        """
        Testing whether trackers are added to the libtorrent handler in Download
        """
        def mocked_add_trackers(tracker_info):
            self.assertIsInstance(tracker_info, dict)
            self.assertEqual(tracker_info['url'], 'http://google.com')
            mocked_add_trackers.called = True

        mocked_add_trackers.called = False
        self.download.handle.add_tracker = mocked_add_trackers
        self.download.add_trackers(['http://google.com'])
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
        self.download.process_alert(mock_alert, 'tracker_error_alert')
        self.assertEqual(self.download.tracker_status[url][1], 'HTTP status code 123')

        mock_alert.status_code = 0
        self.download.process_alert(mock_alert, 'tracker_error_alert')
        self.assertEqual(self.download.tracker_status[url][1], 'Timeout')

    def test_tracker_warning_alert(self):
        """
        Test whether a tracking warning alert is processed correctly
        """
        url = "http://google.com"
        mock_alert = MockObject()
        mock_alert.category = lambda: lt.alert.category_t.error_notification
        mock_alert.url = url
        mock_alert.message = lambda: 'test'
        self.download.process_alert(mock_alert, 'tracker_warning_alert')
        self.assertEqual(self.download.tracker_status[url][1], 'Warning: test')

    @timeout(10)
    async def test_on_metadata_received_alert(self):
        """
        Testing whether the right operations happen when we receive metadata
        """
        test_future = Future()

        mocked_file = MockObject()
        mocked_file.path = 'test'

        self.download.handle.trackers = lambda: []
        self.download.handle.get_peer_info = lambda: []
        self.download.handle.save_resume_data = lambda: test_future
        self.download.handle.rename_file = lambda *_: None
        with open(TESTS_DATA_DIR / "bak_single.torrent", mode='rb') as torrent_file:
            encoded_metainfo = torrent_file.read()
        decoded_metainfo = bdecode_compat(encoded_metainfo)
        get_info_from_handle(self.download.handle).metadata = lambda: bencode(decoded_metainfo[b'info'])
        get_info_from_handle(self.download.handle).files = lambda: [mocked_file]

        self.download.checkpoint = lambda: test_future.set_result(None)
        self.download.session = MockObject()
        self.download.session = MockObject()
        self.download.session.torrent_db = None
        self.download.handle.save_path = lambda: None
        self.download.handle.prioritize_files = lambda _: None
        self.download.get_share_mode = lambda: False
        self.download.on_metadata_received_alert(None)

        await test_future

    def test_metadata_received_invalid_info(self):
        """
        Testing whether the right operations happen when we receive metadata but the torrent info is invalid
        """
        def mocked_checkpoint():
            raise RuntimeError("This code should not be reached!")

        self.download.checkpoint = mocked_checkpoint
        self.download.handle.get_torrent_info = lambda: None
        self.download.on_metadata_received_alert(None)

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
        self.download.handle.trackers = lambda: [{'url': 'no-DHT'}]
        self.download.handle.get_peer_info = lambda: []

        get_info_from_handle(self.download.handle).metadata = lambda: lt.bencode({})
        get_info_from_handle(self.download.handle).files = lambda: [mocked_file]

        self.download.checkpoint = mocked_checkpoint
        self.download.on_metadata_received_alert(None)

    def test_torrent_checked_alert(self):
        """
        Testing whether the right operations happen after a torrent checked alert is received
        """
        def mocked_pause_checkpoint():
            mocked_pause_checkpoint.called = True
            return succeed(None)

        mocked_pause_checkpoint.called = False
        self.download.handle.pause = mocked_pause_checkpoint
        self.download.checkpoint = mocked_pause_checkpoint

        mock_alert = MockObject()
        mock_alert.category = lambda: lt.alert.category_t.error_notification
        self.download.pause_after_next_hashcheck = True
        self.download.process_alert(mock_alert, 'torrent_checked_alert')
        self.assertFalse(self.download.pause_after_next_hashcheck)
        self.assertTrue(mocked_pause_checkpoint.called)

        mocked_pause_checkpoint.called = False
        self.download.checkpoint_after_next_hashcheck = True
        self.download.process_alert(mock_alert, 'torrent_checked_alert')
        self.assertFalse(self.download.checkpoint_after_next_hashcheck)
        self.assertTrue(mocked_pause_checkpoint.called)

    def test_setup_exception(self):
        """
        Testing whether an exception in the setup method of Download is handled correctly
        """
        with self.assertRaises(Exception):
            self.download.setup()

    def test_tracker_reply_alert(self):
        """
        Testing the tracker reply alert in Download
        """
        mock_alert = MockObject()
        mock_alert.url = 'http://google.com'
        mock_alert.num_peers = 42
        self.download.on_tracker_reply_alert(mock_alert)
        self.assertEqual(self.download.tracker_status['http://google.com'], [42, 'Working'])

    def test_get_pieces_bitmask(self):
        """
        Testing whether a correct pieces bitmask is returned when requested
        """
        self.download.handle.status().pieces = [True, False, True, False, False]
        self.assertEqual(self.download.get_pieces_base64(), b"oA==")

        self.download.handle.status().pieces = [True * 16]
        self.assertEqual(self.download.get_pieces_base64(), b"gA==")

    async def test_resume_data_failed(self):
        """
        Testing whether the correct operations happen when an error is raised during resume data saving
        """
        mock_alert = Mock(msg="test error")
        dl = self.download
        dl.register_task('post_alert', dl.process_alert, mock_alert, 'save_resume_data_failed_alert', delay=0.1)
        with self.assertRaises(SaveResumeDataError):
            await dl.wait_for_alert('save_resume_data_alert', None,
                                    'save_resume_data_failed_alert', lambda _: SaveResumeDataError())

    def test_on_state_changed(self):
        self.download.handle.status = lambda: Mock(error=None)
        self.download.tdef.get_infohash = lambda: b'a' * 20
        self.download.config.set_hops(1)
        self.download.apply_ip_filter = Mock()
        self.download.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=4)))
        self.download.apply_ip_filter.assert_called_with(False)

        self.download.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=5)))
        self.download.apply_ip_filter.assert_called_with(True)

        self.download.config.set_hops(0)
        self.download.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=4)))
        self.download.apply_ip_filter.assert_called_with(False)

        self.download.on_state_changed_alert(type('state_changed_alert', (object,), dict(state=5)))
        self.download.apply_ip_filter.assert_called_with(False)

    async def test_checkpoint_timeout(self):
        """
        Testing whether making a checkpoint times out when we receive no alert from libtorrent
        """
        self.download._on_resume_err = Mock()
        self.download.futures['save_resume_data'] = [Future()]
        task = self.download.save_resume_data(timeout=.01)
        self.download.futures['save_resume_data'].pop(0)
        await sleep(0.2)
        self.assertTrue(task.done())
