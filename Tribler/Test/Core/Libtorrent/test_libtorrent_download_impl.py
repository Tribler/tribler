import binascii
import os

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
        impl.handle = None
        # Create a dummy download config
        impl.dlconfig = DownloadStartupConfig().dlconfig.copy()
        impl.session.lm.on_download_wrapper_created = lambda _: True
        impl.restart()

    @deferred(timeout=20)
    def test_multifile_torrent(self):
        t = TorrentDef()

        dn = os.path.join(TESTS_DATA_DIR, "contentdir")
        t.add_content(dn, "dirintorrent")

        fn = os.path.join(TESTS_DATA_DIR, "video.avi")
        t.add_content(fn, os.path.join("dirintorrent", "video.avi"))

        t.set_tracker("http://tribler.org/announce")
        t.finalize()

        impl = LibtorrentDownloadImpl(self.session, t)
        # Override the addtorrent because it will be called
        impl.ltmgr = self.session.lm.ltmgr
        impl.ltmgr.add_torrent = lambda ignored, ignored2: False
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
