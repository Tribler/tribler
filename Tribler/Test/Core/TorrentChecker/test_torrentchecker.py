import socket
import time
from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler
from Tribler.Core.Category.Category import Category
from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Modules.tracker_manager import TrackerManager
from Tribler.Core.Session import Session
from Tribler.Core.TorrentChecker.session import HttpTrackerSession, UdpSocketManager
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.twisted_thread import deferred
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTorrentChecker(TriblerCoreTest):
    """
    This class contains tests which test the torrent checker class.
    """

    def setUp(self, annotate=True):
        super(TestTorrentChecker, self).setUp(annotate=annotate)

        config = TriblerConfig()
        config.set_state_dir(self.getStateDir())
        config.set_megacache_enabled(True)

        self.session = Session(config)
        self.session.start_database()
        self.session.lm.torrent_db = TorrentDBHandler(self.session)
        self.session.lm.torrent_checker = TorrentChecker(self.session)
        self.session.lm.tracker_manager = TrackerManager(self.session)

        self.torrent_checker = self.session.lm.torrent_checker
        self.torrent_checker._torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.torrent_checker._torrent_db.category = Category()

    @blocking_call_on_reactor_thread
    def test_initialize(self):
        """
        Test the initialization of the torrent checker
        """
        self.torrent_checker.initialize()
        self.assertIsNotNone(self.torrent_checker._torrent_db)
        self.assertTrue(self.torrent_checker.is_pending_task_active("torrent_checker_tracker_selection"))

    @blocking_call_on_reactor_thread
    def test_create_socket_or_schedule_fail(self):
        """
        Test creation of the UDP socket of the torrent checker when it fails
        """
        def mocked_listen_on_udp():
            raise socket.error("Something went wrong")

        self.torrent_checker.socket_mgr = UdpSocketManager()
        self.torrent_checker.listen_on_udp = mocked_listen_on_udp
        self.torrent_checker.create_socket_or_schedule()

        self.assertIsNone(self.torrent_checker.udp_port)
        self.assertTrue(self.torrent_checker.is_pending_task_active("listen_udp_port"))

    @blocking_call_on_reactor_thread
    def test_reschedule_tracker_select(self):
        """
        Test the rescheduling of the tracker select task
        """
        self.torrent_checker._reschedule_tracker_select()
        self.assertTrue(self.torrent_checker.is_pending_task_active("torrent_checker_tracker_selection"))

    @blocking_call_on_reactor_thread
    def test_add_gui_request_no_trackers(self):
        """
        Test whether adding a request to fetch health of a trackerless torrent fails
        """
        test_deferred = Deferred()
        self.torrent_checker._torrent_db.addExternalTorrentNoDef('a' * 20, 'ubuntu.iso', [['a.test', 1234]], [], 5)

        # Remove the DHT tracker
        self.torrent_checker._torrent_db._db.execute_write("DELETE FROM TorrentTrackerMapping",)

        self.torrent_checker.add_gui_request('a' * 20).addErrback(lambda _: test_deferred.callback(None))
        return test_deferred

    @blocking_call_on_reactor_thread
    def test_add_gui_request_cached(self):
        """
        Test whether cached results of a torrent are returned when fetching the health of a torrent
        """
        self.torrent_checker._torrent_db.addExternalTorrentNoDef('a' * 20, 'ubuntu.iso', [['a.test', 1234]], [], 5)
        self.torrent_checker._torrent_db.updateTorrentCheckResult(
            1, 'a' * 20, 5, 10, time.time(), time.time(), 'good', 0)

        def verify_response(result):
            self.assertTrue('db' in result)
            self.assertEqual(result['db']['seeders'], 5)
            self.assertEqual(result['db']['leechers'], 10)

        return self.torrent_checker.add_gui_request('a' * 20).addCallback(verify_response)

    @blocking_call_on_reactor_thread
    def test_add_gui_request_no_tor(self):
        """
        Test whether a Failure is raised when we try to fetch info about a torrent unknown to the database
        """
        test_deferred = Deferred()
        self.torrent_checker.add_gui_request('a' * 20).addErrback(lambda _: test_deferred.callback(None))
        return test_deferred

    @blocking_call_on_reactor_thread
    def test_task_select_no_tracker(self):
        self.torrent_checker._task_select_tracker()

    @blocking_call_on_reactor_thread
    def test_task_select_tracker(self):
        self.torrent_checker._torrent_db.addExternalTorrentNoDef(
            'a' * 20, 'ubuntu.iso', [['a.test', 1234]], ['http://google.com/announce'], 5)

        controlled_session = HttpTrackerSession(None, None, None, None)
        controlled_session.connect_to_tracker = lambda: Deferred()

        self.torrent_checker._create_session_for_request = lambda *args, **kwargs: controlled_session
        self.torrent_checker._task_select_tracker()

        self.assertEqual(len(controlled_session.infohash_list), 1)

    @deferred(timeout=30)
    def test_tracker_test_error_resolve(self):
        """
        Test whether we capture the error when a tracker check fails
        """
        def verify_cleanup(_):
            # Verify whether we successfully cleaned up the session after an error
            self.assertEqual(len(self.torrent_checker._session_list), 1)

        self.torrent_checker._torrent_db.addExternalTorrentNoDef(
            'a' * 20, 'ubuntu.iso', [['a.test', 1234]], ['udp://non123exiszzting456tracker89fle.abc:80/announce'], 5)
        return self.torrent_checker._task_select_tracker().addCallback(verify_cleanup)

    @deferred(timeout=30)
    def test_tracker_test_invalid_tracker(self):
        """
        Test whether we do nothing when tracker URL is invalid
        """
        tracker_url = u'udp://non123exiszzting456tracker89fle.abc:80'
        bad_tracker_url = u'xyz://non123exiszzting456tracker89fle.abc:80'

        self.torrent_checker._torrent_db.addExternalTorrentNoDef(
            'a' * 20, 'ubuntu.iso', [['a.test', 1234]], [tracker_url], 5)

        # Write invalid url to the database
        sql_stmt = u"UPDATE TrackerInfo SET tracker = ? WHERE tracker = ?"
        self.session.sqlite_db.execute(sql_stmt, (bad_tracker_url, tracker_url))

        def verify_response(resp):
            self.assertIsNone(resp)

        return self.torrent_checker._task_select_tracker().addCallback(verify_response)

    @deferred(timeout=10)
    def test_tracker_no_infohashes(self):
        """
        Test the check of a tracker without associated torrents
        """
        self.session.lm.tracker_manager.add_tracker('http://trackertest.com:80/announce')
        return self.torrent_checker._task_select_tracker()

    @inlineCallbacks
    @blocking_call_on_reactor_thread
    def tearDown(self, annotate=True):
        yield self.torrent_checker.shutdown()
        yield super(TestTorrentChecker, self).tearDown(annotate=annotate)
