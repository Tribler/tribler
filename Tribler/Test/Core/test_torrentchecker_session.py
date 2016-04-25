import struct
from libtorrent import bencode

from twisted.internet.task import Clock

from twisted.internet.defer import Deferred, DeferredList


from Tribler.Core.TorrentChecker.session import HttpTrackerSession, UDPScraper, UdpTrackerSession
from Tribler.Core.Utilities.twisted_thread import deferred, reactor
from Tribler.Test.Core.base_test import TriblerCoreTest


class ClockedUDPCrawler(UDPScraper):
    _reactor = Clock()


class FakeScraper:
    def write_data(self, _):
        pass

class TestTorrentCheckerSession(TriblerCoreTest):
    def test_httpsession_scrape_no_body(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", None)
        session._process_scrape_response(None)
        session._infohash_list = []
        self.assertTrue(session.is_failed)

    def test_httpsession_bdecode_fails(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", None)
        session._infohash_list = []
        session._process_scrape_response("test")
        self.assertTrue(session.is_failed)

    def test_httpsession_code_not_200(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", None)

        class FakeResponse:
            code = 201
            phrase = "unit testing!"

        session.on_response(FakeResponse())
        self.assertTrue(session.is_failed)

    def test_httpsession_failure_reason_in_dict(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", None)
        session._infohash_list = []
        session._process_scrape_response(bencode({'failure reason': 'test'}))
        self.assertTrue(session.is_failed)

    @deferred(timeout=5)
    def test_httpsession_cancel_operation(self):
        session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", None)
        d = Deferred(session._on_cancel)
        d.addErrback(lambda _ : None)
        session.result_deferred = d
        return session.cleanup()

    @deferred(timeout=5)
    def test_udpsession_cancel_operation(self):
        session = UdpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", None)
        d = Deferred(session._on_cancel)
        d.addErrback(lambda _ : None)
        session.result_deferred = d
        return session.cleanup()

    def test_udpsession_udp_tracker_timeout(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        scraper = ClockedUDPCrawler(session, "127.0.0.1", 4782)
        # Advance 16 seconds so the timeout triggered
        scraper._reactor.advance(scraper.timeout_seconds + 1)
        self.assertFalse(scraper.timeout.active(), "timeout was active while should've canceled")

    @deferred(timeout=5)
    def test_udp_scraper_stop_no_connection(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        scraper = UDPScraper(session, "127.0.0.1", 4782)
        # Stop it manually, so the transport becomes inactive
        stop_deferred = scraper.stop()

        return DeferredList([stop_deferred, session.cleanup()])

    @deferred(timeout=5)
    def test_udpsession_udp_tracker_connection_refused(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        scraper = UDPScraper(session, "127.0.0.1", 4782)
        scraper.connectionRefused()
        self.assertTrue(session.is_failed, "Session did not fail while it should")
        return scraper.stop()

    @deferred(timeout=5)
    def test_udpsession_udp_tracker_stop(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        session.create_connection()
        scraper = UDPScraper(session, "127.0.0.1", 4782)
        session.scraper = scraper
        reactor.listenUDP(0, scraper)
        stop_deferred = scraper.stop()

        def verify_timeout_stop(_):
            self.assertFalse(scraper.timeout.active(), "timeout was active while should've fired.")

        stop_deferred.addCallback(verify_timeout_stop)
        return stop_deferred

    def test_udpsession_handle_response_wrong_len(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        self.assertFalse(session.is_failed)
        session.handle_connection_response("too short")
        self.assertTrue(session.is_failed)

    def test_udpsession_handle_connection_wrong_action_transaction(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        self.assertFalse(session.is_failed)
        packet = struct.pack("!qq4s", 123, 123, "test")
        session.handle_connection_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_handle_packet(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        session.scraper = FakeScraper()
        session._action = 123
        session._transaction_id = 124
        self.assertFalse(session.is_failed)
        packet = struct.pack("!iiq", 123, 124, 126)
        session.handle_connection_response(packet)
        self.assertFalse(session.is_failed)

    def test_udpsession_handle_wrong_action_transaction(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        self.assertFalse(session.is_failed)
        packet = struct.pack("!qq4s", 123, 123, "test")
        session.handle_connection_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_mismatch(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        session.scraper = FakeScraper()
        session._action = 123
        session._transaction_id = 124
        session._infohash_list = [1337]
        self.assertFalse(session.is_failed)
        packet = struct.pack("!ii", 123, 124)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_response_too_short(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        session.scraper = FakeScraper()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!i", 123)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_response_wrong_transaction_id(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        session.scraper = FakeScraper()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!ii", 0, 1337)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    @deferred(timeout=5)
    def test_udpsession_invalid_url(self):
        session = UdpTrackerSession("udp://localhost/triblertest", ("blablafakeshizzle.kr", 4782), "/announce", None)
        result_deferred = session.connect_to_tracker()

        def on_error(_):
            self.assertTrue(session.is_failed)

        result_deferred.addErrback(on_error)

        return result_deferred

    @deferred(timeout=5)
    def test_udpsession_cancel_old_deferreds(self):
        session = UdpTrackerSession("udp://localhost/announce", ("localhost", 13468), "/announce", None)
        session.create_connection()
        session.ip_address = "127.0.0.1"
        fake_func = lambda _: 1 + 1
        fake_result_deferred = Deferred(fake_func)
        fake_ip_reoslve_deferred = Deferred(fake_func)
        session.result_deferred = fake_result_deferred
        session.result_deferred.addErrback(fake_func)
        session.ip_resolve_deferred = fake_ip_reoslve_deferred
        session.ip_resolve_deferred.addErrback(fake_func)
        result_deferred = session.connect_to_tracker()

        def on_error(_):
            pass

        result_deferred.addErrback(on_error)

        cleanup_deferred = session.cleanup()
        return cleanup_deferred

    def test_udpsession_response_list_len_mismatch(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
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
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        session.create_connection()
        session.on_ip_address_resolved("127.0.0.1")
        session.result_deferred = Deferred()
        self.assertFalse(session.is_failed)
        session._infohash_list = ["test"]
        packet = struct.pack("!iiiii", session._action, session._transaction_id, 0, 1, 2)
        session.handle_response(packet)

        return session.result_deferred

    @deferred(timeout=5)
    def test_big_correct_run(self):
        session = UdpTrackerSession("localhost", ("192.168.1.1", 1234), "/announce", None)
        session.create_connection()
        session.on_ip_address_resolved("192.168.1.1")
        session.result_deferred = Deferred()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!iiq", session._action, session._transaction_id, 126)
        session.scraper.datagramReceived(packet, (None, None))
        session._infohash_list = ["test"]
        packet = struct.pack("!iiiii", session._action, session._transaction_id, 0, 1, 2)
        session.scraper.datagramReceived(packet, (None, None))

        return session.result_deferred

    def test_http_unprocessed_infohashes(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", None)
        result_deffered = Deferred()
        session.result_deferred = result_deffered
        session._infohash_list.append("test")
        response = bencode(dict())
        session._process_scrape_response(response)
        self.assertTrue(session.is_finished)

    @deferred(timeout=5)
    def test_scraper_stop_old(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", None)
        session.create_connection()
        scraper = UDPScraper(session, "127.0.0.1", 4782)
        session.scraper = scraper
        session.on_ip_address_resolved("127.0.0.1")
        self.assertNotEquals(session.scraper, scraper, "Scrapers are identical while they should not be")
        return session.cleanup()
