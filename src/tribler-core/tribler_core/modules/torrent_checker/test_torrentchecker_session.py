import socket
import struct
from asyncio import CancelledError, DatagramProtocol, Future, ensure_future, get_event_loop, start_server

from aiohttp.web_exceptions import HTTPBadRequest

from libtorrent import bencode

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.torrent_checker.torrentchecker_session import (
    FakeBep33DHTSession,
    FakeDHTSession,
    HttpTrackerSession,
    UdpTrackerSession,
)
from tribler_core.session import Session
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import succeed


class FakeUdpSocketManager(object):
    transport = 1

    def __init__(self):
        self.response = None
        self.tracker_sessions = {}

    def send_request(self, *args):
        return succeed(self.response)


class TestTorrentCheckerSession(TestAsServer):

    async def setUp(self):
        self.timeout = 15
        await super(TestTorrentCheckerSession, self).setUp()
        self.mock_transport = MockObject()
        self.mock_transport.write = lambda *_: None
        self.socket_mgr = FakeUdpSocketManager()

    async def test_httpsession_scrape_no_body(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._infohash_list = []
        self.assertRaises(ValueError, session._process_scrape_response, None)
        self.assertTrue(session.is_failed)
        await session.cleanup()

    async def test_httpsession_bdecode_fails(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._infohash_list = []
        self.assertRaises(ValueError, session._process_scrape_response, bencode({}))
        self.assertTrue(session.is_failed)
        await session.cleanup()

    async def test_httpsession_code_not_200(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)

        def fake_request(_):
            raise HTTPBadRequest()
        session._session.get = fake_request

        with self.assertRaises(Exception):
            await session.connect_to_tracker()
        await session.cleanup()

    async def test_httpsession_failure_reason_in_dict(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._infohash_list = []
        self.assertRaises(ValueError, session._process_scrape_response, bencode({'failure reason': 'test'}))
        self.assertTrue(session.is_failed)
        await session.cleanup()

    @timeout(5)
    async def test_httpsession_unicode_err(self):
        session = HttpTrackerSession("retracker.local", ("retracker.local", 80),
                                     u"/announce?comment=%26%23%3B%28%2C%29%5B%5D%E3%5B%D4%E8%EB%FC%EC%EE%E2", 5)

        with self.assertRaises(UnicodeEncodeError):
            await session.connect_to_tracker()
        await session.cleanup()

    @timeout(5)
    async def test_httpsession_timeout(self):
        sleep_task = Future()

        async def _client_connected(_, writer):
            await sleep_task
            writer.close()

        server = await start_server(_client_connected, host='localhost', port=0, family=socket.AF_INET)
        _, port = server.sockets[0].getsockname()
        session = HttpTrackerSession("localhost", ("localhost", port), "/announce", 1)
        with self.assertRaises(ValueError):
            await session.connect_to_tracker()
        sleep_task.set_result(None)
        await session.cleanup()
        server.close()

    @timeout(5)
    async def test_udpsession_timeout(self):
        sleep_future = Future()
        self.socket_mgr.send_request = lambda *_: sleep_future
        transport, _ = await get_event_loop().create_datagram_endpoint(lambda: DatagramProtocol(),
                                                                       local_addr=('127.0.0.1', 0),
                                                                       family=socket.AF_INET)
        _, port = transport.get_extra_info('sockname')
        session = UdpTrackerSession("localhost", ("127.0.0.1", port), "/announce", 1, self.socket_mgr)
        with self.assertRaises(ValueError):
            await session.connect_to_tracker()
        transport.close()

    @timeout(5)
    async def test_httpsession_cancel_operation(self):
        session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5)
        task = ensure_future(session.connect_to_tracker())
        with self.assertRaises(CancelledError):
            task.cancel()
            await task
        await session.cleanup()

    async def test_udpsession_cancel_operation(self):
        session = UdpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 0, self.socket_mgr)
        task = ensure_future(session.connect_to_tracker())
        with self.assertRaises(CancelledError):
            task.cancel()
            await task
        await session.cleanup()

    async def test_udpsession_handle_response_wrong_len(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        self.assertFalse(session.is_failed)
        self.socket_mgr.response = b"too short"
        with self.assertRaises(ValueError):
            await session.connect()
        self.assertTrue(session.is_failed)

        # After receiving a correct packet, it session should still be in a failed state
        session.action = 123
        session.transaction_id = 124
        self.socket_mgr.response = struct.pack("!iiq", 123, 124, 126)
        await session.connect()
        self.assertTrue(session.is_failed)

    async def test_udpsession_no_port(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        self.assertFalse(session.is_failed)
        self.socket_mgr.transport = None
        with self.assertRaises(ValueError):
            await session.connect()
        self.assertTrue(session.is_failed)

    async def test_udpsession_handle_connection_wrong_action_transaction(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        self.assertFalse(session.is_failed)
        self.socket_mgr.response = struct.pack("!qq4s", 123, 123, b"test")
        with self.assertRaises(ValueError):
            await session.scrape()
        self.assertTrue(session.is_failed)

    async def test_udpsession_handle_packet(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        session.action = 123
        session.transaction_id = 124
        self.assertFalse(session.is_failed)
        self.socket_mgr.response = struct.pack("!iiq", 123, 124, 126)
        await session.connect()
        self.assertFalse(session.is_failed)

    async def test_udpsession_handle_wrong_action_transaction(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        self.assertFalse(session.is_failed)
        self.socket_mgr.response = struct.pack("!qq4s", 123, 123, b"test")
        with self.assertRaises(ValueError):
            await session.connect()
        self.assertTrue(session.is_failed)

    async def test_udpsession_mismatch(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        session.action = 123
        session.transaction_id = 124
        session.infohash_list = [b'\x00' * 20]
        self.assertFalse(session.is_failed)
        self.socket_mgr.response = struct.pack("!ii", 123, 124)
        with self.assertRaises(ValueError):
            await session.scrape()
        self.assertTrue(session.is_failed)

    async def test_udpsession_response_too_short(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        self.assertFalse(session.is_failed)
        self.socket_mgr.response = struct.pack("!i", 123)
        with self.assertRaises(ValueError):
            await session.scrape()
        self.assertTrue(session.is_failed)

    async def test_udpsession_response_wrong_transaction_id(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        self.assertFalse(session.is_failed)
        self.socket_mgr.response = struct.pack("!ii", 0, 1337)
        with self.assertRaises(ValueError):
            await session.scrape()
        self.assertTrue(session.is_failed)

    async def test_udpsession_response_list_len_mismatch(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, self.socket_mgr)
        session.action = 123
        session.transaction_id = 123
        self.assertFalse(session.is_failed)
        session._infohash_list = [b"test", b"test2"]
        self.socket_mgr.response = struct.pack("!iiiii", 123, 123, 0, 1, 2)
        with self.assertRaises(ValueError):
            await session.scrape()
        self.assertTrue(session.is_failed)

    @timeout(5)
    async def test_udpsession_correct_handle(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5, self.socket_mgr)
        session.ip_address = "127.0.0.1"
        session.infohash_list.append(b'test')
        self.socket_mgr.response = struct.pack("!iiq", 0, session.transaction_id, 2)
        await session.connect()
        self.socket_mgr.response = struct.pack("!iiiii", 2, session.transaction_id, 0, 1, 2)
        await session.scrape()
        self.assertFalse(session.is_failed)
        await session.cleanup()

    @timeout(5)
    async def test_big_correct_run(self):
        session = UdpTrackerSession("localhost", ("192.168.1.1", 1234), "/announce", 0, self.socket_mgr)
        self.assertFalse(session.is_failed)
        self.socket_mgr.response = struct.pack("!iiq", session.action, session.transaction_id, 126)
        await session.connect()
        session.infohash_list = [b"test"]
        self.socket_mgr.response = struct.pack("!iiiii", session.action, session.transaction_id, 0, 1, 2)
        await session.scrape()
        self.assertTrue(session.is_finished)

    async def test_http_unprocessed_infohashes(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session.infohash_list.append(b"test")
        response = bencode({"files": {b"a" * 20: {"complete": 10, "incomplete": 10}}})
        session._process_scrape_response(response)
        self.assertTrue(session.is_finished)
        await session.cleanup()

    async def test_failed_unicode(self):
        session = HttpTrackerSession(u"localhost", ("localhost", 8475), "/announce", 5)
        self.assertRaises(ValueError, session._process_scrape_response, bencode({'failure reason': '\xe9'}))
        await session.cleanup()

    def test_failed_unicode_udp(self):
        session = UdpTrackerSession("localhost", ("localhost", 8475), "/announce", 0, self.socket_mgr)
        self.assertRaises(ValueError, session.failed, '\xd0')


class TestDHTSession(TriblerCoreTest):
    """
    Test the DHT session that we use to fetch the swarm status from the DHT.
    """

    async def setUp(self):
        await super(TestDHTSession, self).setUp()

        state_dir = self.getStateDir()
        config = TriblerConfig()
        config.get_default_state_dir = lambda _: state_dir

        self.session = Session(config)
        self.session.ltmgr = MockObject()
        self.session.ltmgr.dht_health_manager = MockObject()
        dht_health_dict = {
            "infohash": hexlify(b'a' * 20),
            "seeders": 1,
            "leechers": 2
        }
        self.session.ltmgr.dht_health_manager.get_health = lambda *_, **__: succeed({"DHT": [dht_health_dict]})

        self.dht_session = FakeDHTSession(self.session, b'a' * 20, 10)
        self.bep33_dht_session = FakeBep33DHTSession(self.session, b'a' * 20, 10)

    @timeout(10)
    async def test_cleanup(self):
        """
        Test the cleanup of a DHT session
        """
        await self.bep33_dht_session.cleanup()

    @timeout(10)
    async def test_connect_to_tracker(self):
        """
        Test the metainfo lookup of the DHT session
        """
        metainfo = {b'seeders': 42, b'leechers': 42}
        self.session.ltmgr.get_metainfo = lambda *_, **__: succeed(metainfo)

        metainfo = await self.dht_session.connect_to_tracker()

        self.assertTrue('DHT' in metainfo)
        self.assertEqual(metainfo['DHT'][0]['leechers'], 42)
        self.assertEqual(metainfo['DHT'][0]['seeders'], 42)

    @timeout(10)
    async def test_connect_to_tracker_fail(self):
        """
        Test the metainfo lookup of the DHT session when it fails
        """
        self.session.ltmgr.get_metainfo = lambda *_, **__: succeed(None)

        try:
            await self.dht_session.connect_to_tracker()
        except:
            pass

    @timeout(10)
    async def test_connect_to_tracker_bep33(self):
        """
        Test the metainfo lookup of the BEP33 DHT session
        """
        metainfo = await self.bep33_dht_session.connect_to_tracker()

        self.assertTrue('DHT' in metainfo)
        self.assertEqual(metainfo['DHT'][0]['leechers'], 2)
        self.assertEqual(metainfo['DHT'][0]['seeders'], 1)

    def test_methods(self):
        """
        Test various methods in the DHT session class
        """
        self.bep33_dht_session.add_infohash('b' * 20)
        self.assertEqual(self.bep33_dht_session.infohash, 'b' * 20)
