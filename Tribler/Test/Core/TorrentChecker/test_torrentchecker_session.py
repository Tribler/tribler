import struct

from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.task import Clock
from twisted.python.failure import Failure

from libtorrent import bencode
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentChecker.session import FakeDHTSession, DHT_TRACKER_MAX_RETRIES, DHT_TRACKER_RECHECK_INTERVAL, \
    UdpTrackerSession, UDPScraper, HttpTrackerSession
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class ClockedUDPCrawler(UDPScraper):
    _reactor = Clock()


class FakeScraper(object):
    def write_data(self, _):
        pass

    def stop(self):
        pass


class TestTorrentCheckerSession(TriblerCoreTest):

    def setUp(self, annotate=True):
        super(TestTorrentCheckerSession, self).setUp(annotate=annotate)
        self.mock_transport = MockObject()
        self.mock_transport.write = lambda *_: None

    def test_httpsession_scrape_no_body(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._process_scrape_response(None)
        session._infohash_list = []
        self.assertTrue(session.is_failed)

    def test_httpsession_bdecode_fails(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._infohash_list = []
        session._process_scrape_response("test")
        self.assertTrue(session.is_failed)

    def test_httpsession_code_not_200(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)

        class FakeResponse(object):
            code = 201
            phrase = "unit testing!"

        session.on_response(FakeResponse())
        self.assertTrue(session.is_failed)

    def test_httpsession_failure_reason_in_dict(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._infohash_list = []
        session._process_scrape_response(bencode({'failure reason': 'test'}))
        self.assertTrue(session.is_failed)

    @deferred(timeout=5)
    def test_httpsession_unicode_err(self):
        session = HttpTrackerSession("retracker.local", ("retracker.local", 80),
                                     u"/announce?comment=%26%23%3B%28%2C%29%5B%5D%E3%5B%D4%E8%EB%FC%EC%EE%E2", 5)

        test_deferred = Deferred()

        def on_error(failure):
            failure.trap(UnicodeEncodeError)
            self.assertTrue(isinstance(failure.value, UnicodeEncodeError))
            test_deferred.callback(None)

        session.connect_to_tracker().addErrback(on_error)
        return test_deferred

    @deferred(timeout=5)
    def test_httpsession_cancel_operation(self):
        test_deferred = Deferred()
        session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5)
        session.result_deferred = Deferred(session._on_cancel)
        session.result_deferred.addErrback(lambda _: test_deferred.callback(None))
        session.result_deferred.cancel()
        return test_deferred

    @deferred(timeout=5)
    def test_udpsession_cancel_operation(self):
        session = UdpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5)
        d = Deferred(session._on_cancel)
        d.addErrback(lambda _: None)
        session.result_deferred = d
        return session.cleanup()

    def test_udpsession_udp_tracker_timeout(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = ClockedUDPCrawler(session, "127.0.0.1", 4782, 5)
        # Advance 16 seconds so the timeout triggered
        session.scraper._reactor.advance(session.scraper.timeout + 1)
        self.assertFalse(session.scraper.timeout_call.active(), "timeout was active while should've canceled")

    @deferred(timeout=5)
    def test_udp_scraper_stop_no_connection(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        scraper = UDPScraper(session, "127.0.0.1", 4782, 5)
        # Stop it manually, so the transport becomes inactive
        stop_deferred = scraper.stop()

        return DeferredList([stop_deferred, session.cleanup()])

    @deferred(timeout=5)
    def test_udpsession_udp_tracker_connection_refused(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = UDPScraper(session, "127.0.0.1", 4782, 5)
        session.scraper.connectionRefused()
        self.assertTrue(session.is_failed, "Session did not fail while it should")
        return session.scraper.stop()

    def test_udpsession_handle_response_wrong_len(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.on_ip_address_resolved("127.0.0.1", start_scraper=False)
        self.assertFalse(session.is_failed)
        session.handle_connection_response("too short")
        self.assertTrue(session.is_failed)

    def test_udpsession_handle_connection_wrong_action_transaction(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.on_ip_address_resolved("127.0.0.1", start_scraper=None)
        self.assertFalse(session.is_failed)
        packet = struct.pack("!qq4s", 123, 123, "test")
        session.handle_connection_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_handle_packet(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        session._action = 123
        session._transaction_id = 124
        self.assertFalse(session.is_failed)
        packet = struct.pack("!iiq", 123, 124, 126)
        session.handle_connection_response(packet)
        self.assertFalse(session.is_failed)

    def test_udpsession_handle_wrong_action_transaction(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.on_ip_address_resolved("127.0.0.1", start_scraper=None)
        self.assertFalse(session.is_failed)
        packet = struct.pack("!qq4s", 123, 123, "test")
        session.handle_connection_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_mismatch(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        session._action = 123
        session._transaction_id = 124
        session._infohash_list = [1337]
        self.assertFalse(session.is_failed)
        packet = struct.pack("!ii", 123, 124)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_response_too_short(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!i", 123)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_response_wrong_transaction_id(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!ii", 0, 1337)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_response_list_len_mismatch(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        session.result_deferred = Deferred()

        def on_error(_):
            pass

        session.result_deferred.addErrback(on_error)
        session._action = 123
        session._transaction_id = 123
        self.assertFalse(session.is_failed)
        session._infohash_list = ["test", "test2"]
        packet = struct.pack("!iiiii", 123, 123, 0, 1, 2)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    @deferred(timeout=5)
    def test_udpsession_correct_handle(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.on_ip_address_resolved("127.0.0.1", start_scraper=False)
        session.result_deferred = Deferred()
        self.assertFalse(session.is_failed)
        session._infohash_list = ["test"]
        packet = struct.pack("!iiiii", session._action, session._transaction_id, 0, 1, 2)
        session.handle_response(packet)

        return session.result_deferred.addCallback(lambda *_: session.cleanup())

    @deferred(timeout=5)
    def test_udpsession_on_error(self):
        test_deferred = Deferred()
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.result_deferred = Deferred().addErrback(
            lambda failure: test_deferred.callback(failure.getErrorMessage()))
        session.scraper = FakeScraper()
        session.on_error(Failure(RuntimeError("test")))
        return test_deferred

    @deferred(timeout=5)
    def test_big_correct_run(self):
        session = UdpTrackerSession("localhost", ("192.168.1.1", 1234), "/announce", 1)
        session.on_ip_address_resolved("192.168.1.1", start_scraper=False)
        session.scraper.transport = self.mock_transport
        session.result_deferred = Deferred()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!iiq", session._action, session._transaction_id, 126)
        session.scraper.datagramReceived(packet, (None, None))
        session._infohash_list = ["test"]
        packet = struct.pack("!iiiii", session._action, session._transaction_id, 0, 1, 2)
        session.scraper.datagramReceived(packet, (None, None))
        self.assertTrue(session.is_finished)

        return session.result_deferred

    def test_http_unprocessed_infohashes(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        result_deffered = Deferred()
        session.result_deferred = result_deffered
        session._infohash_list.append("test")
        response = bencode(dict())
        session._process_scrape_response(response)
        self.assertTrue(session.is_finished)

    @deferred(timeout=5)
    def test_failed_unicode(self):
        test_deferred = Deferred()

        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)

        def on_error(failure):
            print failure
            test_deferred.callback(None)

        session.result_deferred = Deferred().addErrback(on_error)
        session._process_scrape_response(bencode({'failure reason': '\xe9'}))

        return test_deferred

class TestDHTSession(TriblerCoreTest):
    """
    Test the DHT session that we use to fetch the swarm status from the DHT.
    """

    def setUp(self, annotate=True):
        super(TestDHTSession, self).setUp(annotate=annotate)

        config = SessionStartupConfig()
        config.set_state_dir(self.getStateDir())

        self.session = Session(config, ignore_singleton=True)

        self.dht_session = FakeDHTSession(self.session, 'a' * 20, 10)

    @deferred(timeout=10)
    def test_cleanup(self):
        """
        Test the cleanup of a DHT session
        """
        return self.dht_session.cleanup()

    @deferred(timeout=10)
    def test_connect_to_tracker(self):
        """
        Test the metainfo lookup of the DHT session
        """
        def get_metainfo(infohash, callback, **_):
            callback({"seeders": 1, "leechers": 2})

        def verify_metainfo(metainfo):
            self.assertTrue('DHT' in metainfo)
            self.assertEqual(metainfo['DHT'][0]['leechers'], 2)
            self.assertEqual(metainfo['DHT'][0]['seeders'], 1)

        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo
        return self.dht_session.connect_to_tracker().addCallback(verify_metainfo)

    @deferred(timeout=10)
    def test_metainfo_timeout(self):
        """
        Test the metainfo timeout of the DHT session
        """
        test_deferred = Deferred()

        def get_metainfo_timeout(*args, **kwargs):
            timeout_cb = kwargs.get('timeout_callback')
            timeout_cb('a' * 20)

        def on_timeout(failure):
            test_deferred.callback(None)

        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo_timeout
        self.dht_session.connect_to_tracker().addErrback(on_timeout)
        return test_deferred

    def test_methods(self):
        """
        Test various methods in the DHT session class
        """
        self.assertTrue(self.dht_session.can_add_request())
        self.dht_session.add_infohash('b' * 20)
        self.assertEqual(self.dht_session.infohash, 'b' * 20)
        self.assertEqual(self.dht_session.max_retries, DHT_TRACKER_MAX_RETRIES)
        self.assertEqual(self.dht_session.retry_interval, DHT_TRACKER_RECHECK_INTERVAL)
        self.assertGreater(self.dht_session.last_contact, 0)
