from __future__ import absolute_import

import socket
import time
from binascii import hexlify

from pony.orm import db_session
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.python.failure import Failure

from Tribler.Core.Modules.tracker_manager import TrackerManager
from Tribler.Core.TorrentChecker.session import HttpTrackerSession, UdpSocketManager
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout


class TestTorrentChecker(TestAsServer):
    """
    This class contains tests which test the torrent checker class.
    """

    def setUpPreSession(self):
        super(TestTorrentChecker, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @inlineCallbacks
    def setUp(self):
        yield super(TestTorrentChecker, self).setUp()

        self.session.lm.torrent_checker = TorrentChecker(self.session)
        self.session.lm.tracker_manager = TrackerManager(self.session)
        self.session.lm.popularity_community = MockObject()

        self.torrent_checker = self.session.lm.torrent_checker
        self.torrent_checker.listen_on_udp = lambda: None

        def get_metainfo(infohash, callback, **_):
            callback({"seeders": 1, "leechers": 2})

        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo
        self.session.lm.ltmgr.shutdown = lambda: None

    @inlineCallbacks
    def tearDown(self):
        yield self.torrent_checker.shutdown()
        yield super(TestTorrentChecker, self).tearDown()

    def test_initialize(self):
        """
        Test the initialization of the torrent checker
        """
        self.torrent_checker.initialize()
        self.assertTrue(self.torrent_checker.is_pending_task_active("torrent_checker_tracker_selection"))

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

    def test_reschedule_tracker_select(self):
        """
        Test the rescheduling of the tracker select task
        """
        self.torrent_checker._reschedule_tracker_select()
        self.assertTrue(self.torrent_checker.is_pending_task_active("torrent_checker_tracker_selection"))

    def test_add_gui_request_no_trackers(self):
        """
        Test whether adding a request to fetch health of a trackerless torrent fails
        """
        test_deferred = Deferred()
        with db_session:
            self.session.lm.mds.TorrentState(infohash='a' * 20)

        self.torrent_checker.add_gui_request('a' * 20).addErrback(lambda _: test_deferred.callback(None))
        return test_deferred

    def test_add_gui_request_cached(self):
        """
        Test whether cached results of a torrent are returned when fetching the health of a torrent
        """
        with db_session:
            tracker = self.session.lm.mds.TrackerState(url="http://localhost/tracker")
            self.session.lm.mds.TorrentState(infohash='a' * 20, seeders=5, leechers=10, trackers={tracker},
                                             last_check=int(time.time()))

        def verify_response(result):
            self.assertTrue('db' in result)
            self.assertEqual(result['db']['seeders'], 5)
            self.assertEqual(result['db']['leechers'], 10)

        return self.torrent_checker.add_gui_request('a' * 20).addCallback(verify_response)

    def test_add_gui_request_no_tor(self):
        """
        Test whether a Failure is raised when we try to fetch info about a torrent unknown to the database
        """
        test_deferred = Deferred()
        self.torrent_checker.add_gui_request('a' * 20).addErrback(lambda _: test_deferred.callback(None))
        return test_deferred

    @trial_timeout(10)
    def test_task_select_no_tracker(self):
        return self.torrent_checker._task_select_tracker()

    def test_task_select_tracker(self):
        with db_session:
            tracker = self.session.lm.mds.TrackerState(url="http://localhost/tracker")
            self.session.lm.mds.TorrentState(infohash='a' * 20, seeders=5, leechers=10, trackers={tracker})

        controlled_session = HttpTrackerSession(None, None, None, None)
        controlled_session.connect_to_tracker = lambda: Deferred()

        self.torrent_checker._create_session_for_request = lambda *args, **kwargs: controlled_session
        self.torrent_checker._task_select_tracker()

        self.assertEqual(len(controlled_session.infohash_list), 1)

    @trial_timeout(30)
    def test_tracker_test_error_resolve(self):
        """
        Test whether we capture the error when a tracker check fails
        """

        def verify_cleanup(_):
            # Verify whether we successfully cleaned up the session after an error
            self.assertEqual(len(self.torrent_checker._session_list), 1)

        with db_session:
            tracker = self.session.lm.mds.TrackerState(url="http://localhost/tracker")
            self.session.lm.mds.TorrentState(infohash='a' * 20, seeders=5, leechers=10, trackers={tracker},
                                             last_check=int(time.time()))
        return self.torrent_checker._task_select_tracker().addCallback(verify_cleanup)

    @trial_timeout(10)
    def test_tracker_no_infohashes(self):
        """
        Test the check of a tracker without associated torrents
        """
        self.session.lm.tracker_manager.add_tracker('http://trackertest.com:80/announce')
        return self.torrent_checker._task_select_tracker()

    def test_get_valid_next_tracker_for_auto_check(self):
        """ Test if only valid tracker url is used for auto check """
        test_tracker_list = ["http://anno nce.torrentsmd.com:8080/announce",
                             "http://announce.torrentsmd.com:8080/announce"]

        def get_next_tracker_for_auto_check():
            return test_tracker_list[0] if test_tracker_list else None

        def remove_tracker(tracker_url):
            test_tracker_list.remove(tracker_url)

        self.torrent_checker.get_next_tracker_for_auto_check = get_next_tracker_for_auto_check
        self.torrent_checker.remove_tracker = remove_tracker

        next_tracker_url = self.torrent_checker.get_valid_next_tracker_for_auto_check()
        self.assertEqual(len(test_tracker_list), 1)
        self.assertEqual(next_tracker_url, "http://announce.torrentsmd.com:8080/announce")

    def test_publish_torrent_result(self):
        MSG_ZERO_SEED_TORRENT = "Not publishing zero seeded torrents"
        MSG_NO_popularity_community = "Popular community not available to publish torrent checker result"

        def _fake_logger_info(torrent_checker, msg):
            if msg == MSG_ZERO_SEED_TORRENT:
                torrent_checker.zero_seed_torrent = True
            if msg == MSG_NO_popularity_community:
                torrent_checker.popularity_community_not_found = True

        original_logger_info = self.torrent_checker._logger.info
        self.torrent_checker._logger.info = lambda msg: _fake_logger_info(self.torrent_checker, msg)

        def popularity_community_queue_content(torrent_checker, _):
            torrent_checker.popularity_community_queue_content_called = True

        self.torrent_checker.tribler_session.lm.popularity_community.queue_content = lambda _content: \
            popularity_community_queue_content(self.torrent_checker, _content)

        # Case1: Fake torrent checker response, seeders:0
        fake_response = {'infohash': 'a' * 20, 'seeders': 0, 'leechers': 0, 'last_check': time.time()}
        self.torrent_checker.publish_torrent_result(fake_response)
        self.assertTrue(self.torrent_checker.zero_seed_torrent)

        # Case2: Positive seeders
        fake_response['seeders'] = 5
        self.torrent_checker.popularity_community_queue_content_called = False
        self.torrent_checker.popularity_community_queue_content_called_type = None

        self.torrent_checker.publish_torrent_result(fake_response)
        self.assertTrue(self.torrent_checker.popularity_community_queue_content_called)

        # Case3: Popular community is None
        self.torrent_checker.tribler_session.lm.popularity_community = None
        self.torrent_checker.publish_torrent_result(fake_response)
        self.assertTrue(self.torrent_checker.popularity_community_not_found)

        self.torrent_checker._logger.info = original_logger_info

    def test_on_gui_request_completed(self):
        tracker1 = 'udp://localhost:2801'
        tracker2 = "http://badtracker.org/announce"
        infohash_bin = '\xee'*20
        infohash_hex = hexlify(infohash_bin)
        self.session.lm.popularity_community.queue_content = lambda _: None

        failure = Failure()
        failure.tracker_url = tracker2
        result = [
            (True, {tracker1: [{'leechers': 1, 'seeders': 2, 'infohash': infohash_hex}]}),
            (False, failure),
            (True, {'DHT': [{'leechers': 12, 'seeders': 13, 'infohash': infohash_hex}]})
        ]
        # Check that everything works fine even if the database contains no proper infohash
        self.torrent_checker.on_gui_request_completed(infohash_bin, result)
        self.assertDictEqual(self.torrent_checker.on_gui_request_completed(infohash_bin, result),
                         {'DHT': {'leechers': 12, 'seeders': 13, 'infohash': infohash_hex},
                          'http://badtracker.org/announce': {'error': ''}, 'udp://localhost:2801': {'leechers': 1, 'seeders': 2, 'infohash': infohash_hex}})

        with db_session:
            ts = self.session.lm.mds.TorrentState(infohash=infohash_bin)
            previous_check = ts.last_check
            self.torrent_checker.on_gui_request_completed(infohash_bin, result)
            self.assertEqual(result[2][1]['DHT'][0]['leechers'], ts.leechers)
            self.assertEqual(result[2][1]['DHT'][0]['seeders'], ts.seeders)
            self.assertLess(previous_check, ts.last_check)
