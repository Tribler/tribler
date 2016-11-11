import time

from Tribler.Core.Modules.tracker_manager import TrackerManager
from Tribler.Core.TorrentChecker.session import UdpTrackerSession, HttpTrackerSession
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.test_as_server import TestAsServer


class TestTorrentChecker(TestAsServer):
    """
       This class contains tests which test the torrentchecker class.
     """

    @deferred(timeout=20)
    def test_torrent_checker_session_timout_retry(self):
        session = UdpTrackerSession("http://localhost/test", ("localhost", 4782), "/test", None)
        session2 = HttpTrackerSession("http://localhost/test", ("localhost", 8475), "/test", None)
        session._last_contact = int(time.time()) - (session.retry_interval() + 1)
        session.create_connection()
        session2.create_connection()
        session._is_initiated = True
        session2._is_initiated = True
        self.session.lm.tracker_manager = TrackerManager(self.session)
        self.session.lm.tracker_manager.initialize()
        self.session.lm.tracker_manager.add_tracker('http://localhost/test')
        torrent_checker = TorrentChecker(self.session)
        torrent_checker._session_list.append(session)
        torrent_checker._session_list.append(session2)
        torrent_checker.check_sessions()
        self.assertEqual(session._retries, 1, "Retries was %s while it should've been 1" % session._retries)
        self.assertEqual(session2._retries, 0, "Retries was not 0")
        return torrent_checker.shutdown()

    @deferred(timeout=20)
    def test_torrent_checker_udp_retry(self):
        session = UdpTrackerSession("http://localhost/test", ("localhost", 4782), "/test", None)
        session._last_contact = int(time.time()) - (session.retry_interval() + 1)
        session.infohash_list.append("test")
        session.create_connection()
        self.session.lm.tracker_manager = TrackerManager(self.session)
        self.session.lm.tracker_manager.initialize()
        self.session.lm.tracker_manager.add_tracker('http://localhost/test')
        torrent_checker = TorrentChecker(self.session)
        torrent_checker._session_list.append(session)
        torrent_checker._pending_response_dict["test"] = dict()
        torrent_checker.check_timed_out_udp_session([session])
        self.assertEqual(session._retries, 1, "Retries was %s while it should've been 1" % session._retries)
        return torrent_checker.shutdown()
