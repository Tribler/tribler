import struct
from asyncio import CancelledError, Future, ensure_future, sleep
from unittest.mock import Mock, patch

from aiohttp.web_exceptions import HTTPBadRequest
from ipv8.test.base import TestBase
from ipv8.util import succeed
from libtorrent import bencode

from tribler.core.torrent_checker.dataclasses import HealthInfo
from tribler.core.torrent_checker.torrentchecker_session import (
    FakeBep33DHTSession,
    FakeDHTSession,
    HttpTrackerSession,
    UdpSocketManager,
    UdpTrackerSession,
)


class MockUdpSocketManager:
    """
    A mocked UDP socket manager.
    """

    transport = 1

    def __init__(self) -> None:
        """
        Create a new MockUdpSocketManager.
        """
        self.response = None
        self.tracker_sessions = {}

    def send_request(self, data: bytes, tracker_session: UdpTrackerSession) -> Future:
        """
        Fake sending a request and return the registered response.
        """
        return succeed(self.response)


class TestTrackerSession(TestBase):
    """
    Tests for the TrackerSession classes.
    """

    def setUp(self) -> None:
        """
        Create a fake udp socket manager.
        """
        self.fake_udp_socket_manager = MockUdpSocketManager()
        self.fake_dht_session = FakeDHTSession(Mock(), 10)
        self.session = None

    async def tearDown(self) -> None:
        """
        Clean the registered session and helpers.
        """
        if self.session is not None:
            await self.session.cleanup()
        await self.fake_dht_session.shutdown_task_manager()
        await super().tearDown()

    async def test_httpsession_scrape_no_body(self) -> None:
        """
        Test if processing a scrape response of None leads to a ValueError.
        """
        self.session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)

        with self.assertRaises(ValueError):
            self.session.process_scrape_response(None)

        self.assertTrue(self.session.is_failed)

    async def test_httpsession_bdecode_fails(self) -> None:
        """
        Test if processing a scrape response of an empty (bencoded) dictionary leads to a ValueError.
        """
        self.session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)

        with self.assertRaises(ValueError):
            self.session.process_scrape_response(bencode({}))

        self.assertTrue(self.session.is_failed)

    async def test_httpsession_code_not_200(self) -> None:
        """
        Test if getting a HTTP code 400 leads to a ValueError when connecting.
        """
        self.session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)

        def fake_request(_: str) -> None:
            raise HTTPBadRequest

        with self.assertRaises(ValueError), patch.object(self.session.session, "get", fake_request):
            await self.session.connect_to_tracker()

        self.assertTrue(self.session.is_failed)

    async def test_httpsession_failure_reason_in_dict(self) -> None:
        """
        Test if processing a scrape response of a failed (bencoded) dictionary leads to a ValueError.
        """
        self.session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)

        with self.assertRaises(ValueError):
            self. session.process_scrape_response(bencode({'failure reason': 'test'}))

        self.assertTrue(self.session.is_failed)

    async def test_httpsession_unicode_err(self) -> None:
        """
        Test if connecting to a tracker with a unicode error in the url raises a UnicodeEncodeError.
        """
        self.session = HttpTrackerSession("retracker.local", ("retracker.local", 80),
                                          "/announce?comment=%26%23%3B%28%2C%29%5B%5D%E3%5B%D4%E8%EB%FC%EC%EE%E2", 5,
                                          None)

        with self.assertRaises(UnicodeEncodeError):
            await self.session.connect_to_tracker()

        self.assertFalse(self.session.is_failed)

    async def test_pop_finished_transaction(self) -> None:
        """
        Test if receiving a datagram for an already finished tracker session does not result in InvalidStateError.
        """
        transaction_id = 123
        mgr = UdpSocketManager()
        mgr.connection_made(Mock())

        task = ensure_future(mgr.send_request(Mock(), Mock(proxy=None, transaction_id=transaction_id)))
        await sleep(0)
        self.assertNotEqual({}, mgr.tracker_sessions)

        data = struct.pack("!iiq", 124, transaction_id, 126)
        mgr.datagram_received(data, None)
        self.assertEqual({}, mgr.tracker_sessions)
        await task
        self.assertTrue(task.done())

    async def test_proxy_transport(self) -> None:
        """
        Test if the UdpSocketManager uses a proxy if specified.
        """
        mgr = UdpSocketManager()
        mgr.connection_made(Mock())
        mgr.proxy_transports['proxy_url'] = Mock()
        _ = ensure_future(mgr.send_request(b'', Mock(proxy='proxy_url', transaction_id=123)))
        await sleep(0)
        mgr.proxy_transports['proxy_url'].sendto.assert_called_once()
        mgr.transport.assert_not_called()
        mgr.tracker_sessions[123].cancel()

        _ = ensure_future(mgr.send_request(b'', Mock(proxy=None, transaction_id=123)))
        await sleep(0)
        mgr.proxy_transports['proxy_url'].sendto.assert_called_once()
        mgr.transport.sendto.assert_called_once()
        mgr.tracker_sessions[123].cancel()
        del _

    async def test_httpsession_cancel_operation(self) -> None:
        """
        Test if a canceled task is propagated through the HTTP session.
        """
        self.session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5, None)
        task = ensure_future(self.session.connect_to_tracker())

        with self.assertRaises(CancelledError):
            task.cancel()
            await task

    async def test_udpsession_cancel_operation(self) -> None:
        """
        Test if a canceled task is propagated through the UDP session.
        """
        self.session = UdpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 0, None,
                                         self.fake_udp_socket_manager)
        task = ensure_future(self.session.connect_to_tracker())

        with self.assertRaises(CancelledError):
            task.cancel()
            await task

    async def test_udpsession_handle_response_wrong_len(self) -> None:
        """
        Test if, after receiving a correct packet, a session should still be in a failed state.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, self.fake_udp_socket_manager)
        self.fake_udp_socket_manager.response = b"too short"

        with self.assertRaises(ValueError):
            await self.session.connect()

        self.session.action, self.session.transaction_id = 123, 124
        self.fake_udp_socket_manager.response = struct.pack("!iiq", 123, 124, 126)
        await self.session.connect()

        self.assertTrue(self.session.is_failed)

    async def test_udpsession_no_port(self) -> None:
        """
        Test if a UDP session without a port raises a ValueError when connecting.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None,
                                         self.fake_udp_socket_manager)
        self.fake_udp_socket_manager.transport = None

        with self.assertRaises(ValueError):
            await self.session.connect()

        self.assertTrue(self.session.is_failed)

    async def test_udpsession_handle_connection_wrong_action_transaction(self) -> None:
        """
        Test if a wrong action response leads to a ValueError when scraping.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None,
                                         self.fake_udp_socket_manager)
        self.fake_udp_socket_manager.response = struct.pack("!qq4s", 123, 123, b"test")

        with self.assertRaises(ValueError):
            await self.session.scrape()

        self.assertTrue(self.session.is_failed)

    async def test_udpsession_handle_packet(self) -> None:
        """
        Test if a normal UDP packet leads to a non-failed UDP session.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, self.fake_udp_socket_manager)
        self.session.action, self.session.transaction_id = 123, 124
        self.fake_udp_socket_manager.response = struct.pack("!iiq", 123, 124, 126)

        await self.session.connect()

        self.assertFalse(self.session.is_failed)

    async def test_udpsession_handle_wrong_action_transaction(self) -> None:
        """
        Test if a wrong action leads to ValueError when connecting.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None,
                                         self.fake_udp_socket_manager)
        self.fake_udp_socket_manager.response = struct.pack("!qq4s", 123, 123, b"test")

        with self.assertRaises(ValueError):
            await self.session.connect()

        self.assertTrue(self.session.is_failed)

    async def test_udpsession_mismatch(self) -> None:
        """
        Test if a UDP session mismatch leads to a ValueError when scraping.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, self.fake_udp_socket_manager)
        self.session.action, self.session.transaction_id, self.session.infohash_list = 123, 124, [b'\x00' * 20]
        self.fake_udp_socket_manager.response = struct.pack("!ii", 123, 124)

        with self.assertRaises(ValueError):
            await self.session.scrape()

        self.assertTrue(self.session.is_failed)

    async def test_udpsession_response_too_short(self) -> None:
        """
        Test if truncated response leads to a ValueError when scraping.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None,
                                         self.fake_udp_socket_manager)
        self.fake_udp_socket_manager.response = struct.pack("!i", 123)

        with self.assertRaises(ValueError):
            await self.session.scrape()

        self.assertTrue(self.session.is_failed)

    async def test_udpsession_response_wrong_transaction_id(self) -> None:
        """
        Test if a response with a wrong transaction id leads to a ValueError when scraping.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, self.fake_udp_socket_manager)
        self.fake_udp_socket_manager.response = struct.pack("!ii", 0, 1337)

        with self.assertRaises(ValueError):
            await self.session.scrape()

        self.assertTrue(self.session.is_failed)

    async def test_udpsession_response_list_len_mismatch(self) -> None:
        """
        Test if a response with a wrong size leads to a ValueError when scraping.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None,
                                         self.fake_udp_socket_manager)
        self.session.action, self.session.transaction_id, self.session.infohash_list = 123, 123, [b"test", b"test2"]
        self.fake_udp_socket_manager.response = struct.pack("!iiiii", 123, 123, 0, 1, 2)

        with self.assertRaises(ValueError):
            await self.session.scrape()

        self.assertTrue(self.session.is_failed)

    async def test_udpsession_correct_handle(self) -> None:
        """
        Test if correct connect and scrape responses do not lead to a failed session.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5, None, self.fake_udp_socket_manager)
        self.session.ip_address = "127.0.0.1"
        self.session.infohash_list.append(b'test')

        self.fake_udp_socket_manager.response = struct.pack("!iiq", 0, self.session.transaction_id, 2)
        await self.session.connect()

        self.fake_udp_socket_manager.response = struct.pack("!iiiii", 2, self.session.transaction_id, 0, 1, 2)
        await self.session.scrape()

        self.assertFalse(self.session.is_failed)

    async def test_big_correct_run(self) -> None:
        """
        Test if correct connect and scrape responses with infohashes do not lead to a failed session.
        """
        self.session = UdpTrackerSession("localhost", ("192.168.1.1", 1234), "/announce", 0, None,
                                         self.fake_udp_socket_manager)
        self.fake_udp_socket_manager.response = struct.pack("!iiq", self.session.action,
                                                            self.session.transaction_id, 126)

        await self.session.connect()

        self.session.infohash_list = [b"test"]
        self.fake_udp_socket_manager.response = struct.pack("!iiiii", self.session.action, self.session.transaction_id,
                                                            0, 1, 2)
        await self.session.scrape()

        self.assertTrue(self.session.is_finished)

    async def test_http_unprocessed_infohashes(self) -> None:
        """
        Test if a HTTP session that receives infohashes leads to a finished scrape.
        """
        self.session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)
        self.session.infohash_list.append(b"test")
        response = bencode({"files": {b"a" * 20: {"complete": 10, "incomplete": 10}}})

        self.session.process_scrape_response(response)

        self.assertTrue(self.session.is_finished)

    async def test_failed_unicode(self) -> None:
        """
        Test if response with non-unicode symbols leads to a ValueError when processing a scrape.
        """
        self.session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)

        with self.assertRaises(ValueError):
            self.session.process_scrape_response(bencode({'failure reason': '\xe9'}))

    def test_failed_unicode_udp(self) -> None:
        """
        Test if failing a session with non-unicode symbols leads to a ValueError.
        """
        self.session = UdpTrackerSession("localhost", ("localhost", 8475), "/announce", 0, None,
                                    self.fake_udp_socket_manager)

        with self.assertRaises(ValueError):
            self.session.failed('\xd0')

    async def test_connect_to_tracker(self) -> None:
        """
        Test if metainfo can be looked up for a DHT session.
        """
        metainfo = {b'seeders': 42, b'leechers': 42}
        self.fake_dht_session.download_manager.get_metainfo = Mock(return_value=succeed(metainfo))
        self.fake_dht_session.add_infohash(b'a' * 20)
        response = await self.fake_dht_session.connect_to_tracker()

        self.assertEqual("DHT", response.url)
        self.assertEqual(1, len(response.torrent_health_list))
        self.assertEqual(42, response.torrent_health_list[0].leechers)
        self.assertEqual(42, response.torrent_health_list[0].seeders)

    async def test_connect_to_tracker_fail(self) -> None:
        """
        Test if the DHT session raises a TimeoutError when the metainfo lookup fails.
        """
        self.fake_dht_session.download_manager.get_metainfo = Mock(side_effect=TimeoutError)
        self.fake_dht_session.add_infohash(b'a' * 20)

        with self.assertRaises(TimeoutError):
            await self.fake_dht_session.connect_to_tracker()

    async def test_connect_to_tracker_bep33(self) -> None:
        """
        Test the metainfo lookup of the BEP33 DHT session.
        """
        infohash_health = HealthInfo(b"a" * 20, seeders=1, leechers=2)
        mock_dlmgr = Mock(dht_health_manager=Mock(get_health=Mock(return_value=succeed([infohash_health]))))
        self.session = FakeBep33DHTSession(mock_dlmgr, 10)
        self.session.add_infohash(b"a" * 20)

        response = await self.session.connect_to_tracker()

        self.assertEqual("DHT", response.url)
        self.assertEqual(1, len(response.torrent_health_list))
        self.assertEqual(2, response.torrent_health_list[0].leechers)
        self.assertEqual(1, response.torrent_health_list[0].seeders)
