from __future__ import absolute_import

import os
import socket
import time

from pony.orm import db_session

from six.moves import xrange

from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.python.failure import Failure

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY
from Tribler.Core.Modules.tracker_manager import TrackerManager
from Tribler.Core.TorrentChecker.session import HttpTrackerSession, UdpSocketManager
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.Utilities.unicode import hexlify
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

        self.torrent_checker = self.session.lm.torrent_checker
        self.torrent_checker.listen_on_udp = lambda: None

        def get_metainfo(_, callback, **__):
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
        self.assertTrue(self.torrent_checker.is_pending_task_active("tracker_check"))
        self.assertTrue(self.torrent_checker.is_pending_task_active("torrent_check"))

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

    def test_health_check_blacklisted_trackers(self):
        """
        Test whether only cached results of a torrent are returned with only blacklisted trackers
        """
        with db_session:
            tracker = self.session.lm.mds.TrackerState(url="http://localhost/tracker")
            self.session.lm.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                             last_check=int(time.time()))

        def verify_response(result):
            self.assertSetEqual({'db'}, set(result.keys()))
            self.assertEqual(result['db']['seeders'], 5)
            self.assertEqual(result['db']['leechers'], 10)

        self.session.lm.tracker_manager.blacklist.append("http://localhost/tracker")

        return self.torrent_checker.check_torrent_health(b'a' * 20).addCallback(verify_response)

    def test_health_check_cached(self):
        """
        Test whether cached results of a torrent are returned when fetching the health of a torrent
        """
        with db_session:
            tracker = self.session.lm.mds.TrackerState(url="http://localhost/tracker")
            self.session.lm.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                             last_check=int(time.time()))

        def verify_response(result):
            self.assertTrue('db' in result)
            self.assertEqual(result['db']['seeders'], 5)
            self.assertEqual(result['db']['leechers'], 10)

        return self.torrent_checker.check_torrent_health(b'a' * 20).addCallback(verify_response)

    @trial_timeout(10)
    def test_task_select_no_tracker(self):
        return self.torrent_checker.check_random_tracker()

    def test_task_select_tracker(self):
        with db_session:
            tracker = self.session.lm.mds.TrackerState(url="http://localhost/tracker")
            self.session.lm.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker})

        controlled_session = HttpTrackerSession(None, None, None, None)
        controlled_session.connect_to_tracker = lambda: Deferred()

        self.torrent_checker._create_session_for_request = lambda *args, **kwargs: controlled_session
        self.torrent_checker.check_random_tracker()

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
            self.session.lm.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                             last_check=int(time.time()))
        return self.torrent_checker.check_random_tracker().addCallback(verify_cleanup)

    @trial_timeout(10)
    def test_tracker_no_infohashes(self):
        """
        Test the check of a tracker without associated torrents
        """
        self.session.lm.tracker_manager.add_tracker('http://trackertest.com:80/announce')
        return self.torrent_checker.check_random_tracker()

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

    def test_on_health_check_completed(self):
        tracker1 = 'udp://localhost:2801'
        tracker2 = "http://badtracker.org/announce"
        infohash_bin = b'\xee'*20
        infohash_hex = hexlify(infohash_bin)

        failure = Failure()
        failure.tracker_url = tracker2
        result = [
            (True, {tracker1: [{'leechers': 1, 'seeders': 2, 'infohash': infohash_hex}]}),
            (False, failure),
            (True, {'DHT': [{'leechers': 12, 'seeders': 13, 'infohash': infohash_hex}]})
        ]
        # Check that everything works fine even if the database contains no proper infohash
        res_dict = {
            'DHT': {
                'leechers': 12,
                'seeders': 13,
                'infohash': infohash_hex
            },
            'http://badtracker.org/announce': {
                'error': ''
            },
            'udp://localhost:2801': {
                'leechers': 1,
                'seeders': 2,
                'infohash': infohash_hex
            }
        }
        self.torrent_checker.on_torrent_health_check_completed(infohash_bin, result)
        self.assertDictEqual(self.torrent_checker.on_torrent_health_check_completed(infohash_bin, result), res_dict)
        self.assertFalse(self.torrent_checker.on_torrent_health_check_completed(infohash_bin, None))

        with db_session:
            ts = self.session.lm.mds.TorrentState(infohash=infohash_bin)
            previous_check = ts.last_check
            self.torrent_checker.on_torrent_health_check_completed(infohash_bin, result)
            self.assertEqual(result[2][1]['DHT'][0]['leechers'], ts.leechers)
            self.assertEqual(result[2][1]['DHT'][0]['seeders'], ts.seeders)
            self.assertLess(previous_check, ts.last_check)

    def test_on_health_check_failed(self):
        """
        Check whether there is no crash when the torrent health check failed and the response is None
        """
        infohash_bin = '\xee' * 20
        self.torrent_checker.on_torrent_health_check_completed(infohash_bin, [(True, None)])
        self.assertEqual(1, len(self.torrent_checker.torrents_checked))
        self.assertEqual(0, list(self.torrent_checker.torrents_checked)[0][1])

    @db_session
    def test_check_random_torrent_legacy(self):
        """
        Test whether legacy torrents are not health checked
        """
        torrent1 = self.session.lm.mds.TorrentMetadata(title='torrent1', infohash=os.urandom(20))
        torrent1.status = LEGACY_ENTRY

        self.assertFalse(self.torrent_checker.check_random_torrent())

    @db_session
    def test_check_random_torrent(self):
        """
        Test that the random torrent health checking mechanism picks the right torrents
        """
        for ind in xrange(1, 20):
            torrent = self.session.lm.mds.TorrentMetadata(title='torrent1', infohash=os.urandom(20))
            torrent.health.last_check = ind

        self.torrent_checker.check_torrent_health = lambda _: None

        random_infohashes = self.torrent_checker.check_random_torrent()
        self.assertTrue(random_infohashes)

        # Now we should only check a single torrent
        self.torrent_checker.torrents_checked.add((b'a' * 20, 5, 5, int(time.time())))
        random_infohashes = self.torrent_checker.check_random_torrent()
        self.assertEqual(len(random_infohashes), 1)
