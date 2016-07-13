import binascii
import os
import libtorrent as lt

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Utilities.twisted_thread import deferred, reactor
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.Test.test_as_server import TestAsServer, TESTS_DATA_DIR


class TestLibtorrentDownloadImpl(TestAsServer):
    """
    This class provides unit tests that test the LibtorrentDownloadImpl class.
    """

    def setUpPreSession(self):
        super(TestLibtorrentDownloadImpl, self).setUpPreSession()
        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(True)
        self.config.set_dispersy(True)
        self.config.set_mainline_dht(False)
        self.config.set_torrent_collecting(True)
        self.config.set_libtorrent(True)
        self.config.set_dht_torrent_collecting(False)
        self.config.set_videoplayer(False)
        self.config.set_torrent_collecting_dir(os.path.join(self.session_base_dir, 'torrent_collecting_dir'))

    def create_tdef(self):
        """
        create and save torrent definition used in this test file
        """
        tdef = TorrentDef()
        sourcefn = os.path.join(TESTS_DATA_DIR, 'video.avi')
        tdef.add_content(sourcefn)
        tdef.set_tracker("http://localhost/announce")
        tdef.finalize()

        torrentfn = os.path.join(self.session.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)

        return tdef

    @deferred(timeout=10)
    def test_can_create_engine_wrapper(self):
        impl = LibtorrentDownloadImpl(self.session, None)
        impl.cew_scheduled = False
        self.session.lm.ltmgr.is_dht_ready = lambda: True
        return impl.can_create_engine_wrapper()

    @deferred(timeout=15)
    def test_can_create_engine_wrapper_retry(self):
        impl = LibtorrentDownloadImpl(self.session, None)
        impl.cew_scheduled = True
        def set_cew_false():
            self.session.lm.ltmgr.is_dht_ready = lambda: True
            impl.cew_scheduled = False

        # Simulate Tribler changing the cew, the calllater should have fired by now
        # and before it executed the cew is false, firing the deferred.
        reactor.callLater(2, set_cew_false)
        return impl.can_create_engine_wrapper()

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

    @deferred(timeout=20)
    def test_setup(self):
        tdef = self.create_tdef()

        impl = LibtorrentDownloadImpl(self.session, tdef)
        def callback((ignored, ignored2)):
            pass

        deferred = impl.setup(None, None, None, 0)
        deferred.addCallback(callback)
        return deferred

    def test_restart(self):
        tdef = self.create_tdef()

        impl = LibtorrentDownloadImpl(self.session, tdef)
        impl.handle = MockObject()
        impl.handle.set_priority = lambda _: None
        impl.handle.set_sequential_download = lambda _: None
        impl.handle.resume = lambda: None
        impl.handle.status = lambda: fake_status
        fake_status = MockObject()
        fake_status.share_mode = False
        # Create a dummy download config
        impl.dlconfig = DownloadStartupConfig().dlconfig.copy()
        impl.session.lm.on_download_wrapper_created = lambda _: True
        impl.restart()

    @deferred(timeout=20)
    def test_multifile_torrent(self):
        tdef = TorrentDef()

        dn = os.path.join(TESTS_DATA_DIR, "contentdir")
        tdef.add_content(dn, "dirintorrent")

        fn = os.path.join(TESTS_DATA_DIR, "video.avi")
        tdef.add_content(fn, os.path.join("dirintorrent", "video.avi"))

        tdef.set_tracker("http://tribler.org/announce")
        tdef.finalize()

        impl = LibtorrentDownloadImpl(self.session, tdef)
        # Override the add_torrent because it will be called
        impl.ltmgr = MockObject()
        impl.ltmgr.add_torrent = lambda _, _dummy2: fake_handler
        impl.set_selected_files = lambda: None
        fake_handler = MockObject()
        fake_handler.is_valid = lambda: True
        fake_handler.status = lambda: fake_status
        fake_handler.set_share_mode = lambda _: None
        fake_handler.resume = lambda: None
        fake_handler.resolve_countries = lambda _: None
        fake_status = MockObject()
        fake_status.share_mode = False
        # Create a dummy download config
        impl.dlconfig = DownloadStartupConfig().dlconfig.copy()
        # Create a dummy pstate
        pstate = CallbackConfigParser()
        pstate.add_section("state")
        test_dict = dict()
        test_dict["a"] = "b"
        pstate.set("state", "engineresumedata", test_dict)
        return impl.network_create_engine_wrapper(pstate)

    @deferred(timeout=10)
    def test_save_resume(self):
        """
        testing call resume data alert
        """
        tdef = self.create_tdef()

        impl = LibtorrentDownloadImpl(self.session, tdef)

        def resume_ready(_):
            """
            check if resume data is ready
            """
            basename = binascii.hexlify(tdef.get_infohash()) + '.state'
            filename = os.path.join(self.session.get_downloads_pstate_dir(), basename)

            engine_data = CallbackConfigParser()
            engine_data.read_file(filename)

            self.assertEqual(tdef.get_infohash(), engine_data.get('state', 'engineresumedata').get('info-hash'))

        def callback(_):
            """
            callback after finishing setup in LibtorrentDownloadImpl
            """
            defer_alert = impl.save_resume_data()
            defer_alert.addCallback(resume_ready)
            return defer_alert

        result_deferred = impl.setup(None, None, None, 0)
        result_deferred.addCallback(callback)

        return result_deferred


class TestLibtorrentDownloadImplNoSession(TriblerCoreTest):

    def setUp(self, annotate=True):
        TriblerCoreTest.setUp(self, annotate=annotate)
        self.libtorrent_download_impl = LibtorrentDownloadImpl(None, None)
        mock_handle = MockObject()
        mock_status = MockObject()
        mock_handle.is_valid = lambda: True
        mock_handle.status = lambda: mock_status
        self.libtorrent_download_impl.handle = mock_handle

    def test_get_share_mode(self):
        """
        Test whether we return the right share mode when requested in the LibtorrentDownloadImpl
        """
        self.libtorrent_download_impl.handle.status().share_mode = False
        self.assertFalse(self.libtorrent_download_impl.get_share_mode())
        self.libtorrent_download_impl.handle.status().share_mode = True
        self.assertTrue(self.libtorrent_download_impl.get_share_mode())

    def test_set_priority(self):
        """
        Test whether setting the priority calls the right methods in LibtorrentDownloadImpl
        """
        def mocked_set_priority(prio):
            self.assertEqual(prio, 1234)
            mocked_set_priority.called = True

        mocked_set_priority.called = False
        self.libtorrent_download_impl.handle.set_priority = mocked_set_priority

        self.libtorrent_download_impl.set_priority(1234)
        self.assertTrue(mocked_set_priority.called)

    def test_dlconfig_cb_change(self):
        """
        Testing whether changing the configuration on runtime calls the right methods in LibtorrentDownloadImpl
        """
        def mocked_set_upload_limit(prio):
            self.assertEqual(prio, 3 * 1024)
            mocked_set_upload_limit.called = True

        mocked_set_upload_limit.called = False
        self.libtorrent_download_impl.handle.set_upload_limit = mocked_set_upload_limit

        def mocked_set_download_limit(prio):
            self.assertEqual(prio, 3 * 1024)
            mocked_set_download_limit.called = True

        mocked_set_download_limit.called = False
        self.libtorrent_download_impl.handle.set_download_limit = mocked_set_download_limit

        self.libtorrent_download_impl.dlconfig_changed_callback('downloadconfig', 'max_upload_rate', 3, 4)
        self.assertTrue(mocked_set_upload_limit)
        self.libtorrent_download_impl.dlconfig_changed_callback('downloadconfig', 'max_download_rate', 3, 4)
        self.assertTrue(mocked_set_download_limit)
        self.assertFalse(self.libtorrent_download_impl.dlconfig_changed_callback(
            'downloadconfig', 'super_seeder', 3, 4))

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

    def test_torrent_checked_alert(self):
        """
        Testing whether the right operations happen after a torrent checked alert is received
        """
        def mocked_pause_checkpoint():
            mocked_pause_checkpoint.called = True

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

    def test_get_length(self):
        """
        Testing whether the right length of the content of the download is returned
        """
        self.libtorrent_download_impl.length = 1234
        self.assertEqual(self.libtorrent_download_impl.get_length(), 1234)

    def test_get_dest_files(self):
        """
        Testing whether the right list of files is returned when fetching files from a download
        """
        self.libtorrent_download_impl.handle.file_priority = lambda _: 123
        mocked_file = MockObject()
        mocked_file.path = 'test'
        mock_torrent_info = MockObject()
        mock_torrent_info.files = lambda: [mocked_file]
        self.libtorrent_download_impl.handle.get_torrent_info = lambda: mock_torrent_info
        dest_files = self.libtorrent_download_impl.get_dest_files()
        self.assertIsInstance(dest_files[0], tuple)
        self.assertEqual(dest_files[0][0], 'test')

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
        self.libtorrent_download_impl.handle.status = lambda: None
        self.assertEqual(self.libtorrent_download_impl.get_piece_progress([3, 1]), 0.0)

    def test_setup_exception(self):
        """
        Testing whether an exception in the setup method of LibtorrentDownloadImpl is handled correctly
        """
        self.libtorrent_download_impl.setup()
        self.assertIsInstance(self.libtorrent_download_impl.error, Exception)

    def test_tracker_reply_alert(self):
        """
        Testing the tracker reply alert in LibtorrentDownloadImpl
        """
        mock_alert = MockObject()
        mock_alert.url = 'http://google.com'
        mock_alert.num_peers = 42
        self.libtorrent_download_impl.on_tracker_reply_alert(mock_alert)
        self.assertEqual(self.libtorrent_download_impl.tracker_status['http://google.com'], [42, 'Working'])

    def test_stop(self):
        """
        Testing whether the stop method in LibtorrentDownloadImpl invokes the correct method
        """
        def mocked_stop_remove(removestate, removecontent):
            self.assertFalse(removestate)
            self.assertFalse(removecontent)
            mocked_stop_remove.called = True

        mocked_stop_remove.called = False
        self.libtorrent_download_impl.stop_remove = mocked_stop_remove
        self.libtorrent_download_impl.stop()
        self.assertTrue(mocked_stop_remove.called)
