import socket
import struct
from asyncio import CancelledError, DatagramProtocol, Future, ensure_future, get_event_loop, sleep, start_server
from unittest.mock import Mock

import pytest
from aiohttp.web_exceptions import HTTPBadRequest
from ipv8.util import succeed
from libtorrent import bencode

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.components.torrent_checker.torrent_checker.torrentchecker_session import \
    FakeBep33DHTSession, FakeDHTSession, HttpTrackerSession, UdpSocketManager, UdpTrackerSession


# pylint: disable=redefined-outer-name

class FakeUdpSocketManager:
    transport = 1

    def __init__(self):
        self.response = None
        self.tracker_sessions = {}

    def send_request(self, *args):
        return succeed(self.response)


@pytest.fixture(name='fake_udp_socket_manager')
def fixture_fake_udp_socket_manager():
    return FakeUdpSocketManager()


@pytest.fixture
async def bep33_session(mock_dlmgr):
    bep33_dht_session = FakeBep33DHTSession(mock_dlmgr, 10)
    yield bep33_dht_session
    await bep33_dht_session.cleanup()


@pytest.fixture
async def fake_dht_session(mock_dlmgr):
    fake_dht_session = FakeDHTSession(mock_dlmgr, 10)
    yield fake_dht_session
    await fake_dht_session.shutdown_task_manager()


async def test_httpsession_scrape_no_body():
    session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)
    session._infohash_list = []
    with pytest.raises(ValueError):
        session._process_scrape_response(None)
    assert session.is_failed
    await session.cleanup()


async def test_httpsession_bdecode_fails():
    session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)
    session._infohash_list = []
    with pytest.raises(ValueError):
        session._process_scrape_response(bencode({}))
    assert session.is_failed
    await session.cleanup()


async def test_httpsession_code_not_200():
    session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)

    def fake_request(_):
        raise HTTPBadRequest()

    session._session.get = fake_request

    with pytest.raises(Exception):
        await session.connect_to_tracker()
    await session.cleanup()


async def test_httpsession_failure_reason_in_dict():
    session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)
    session._infohash_list = []
    with pytest.raises(ValueError):
        session._process_scrape_response(bencode({'failure reason': 'test'}))
    assert session.is_failed
    await session.cleanup()


async def test_httpsession_unicode_err():
    session = HttpTrackerSession("retracker.local", ("retracker.local", 80),
                                 "/announce?comment=%26%23%3B%28%2C%29%5B%5D%E3%5B%D4%E8%EB%FC%EC%EE%E2", 5, None)

    with pytest.raises(UnicodeEncodeError):
        await session.connect_to_tracker()
    await session.cleanup()


async def test_httpsession_timeout():
    sleep_task = Future()

    async def _client_connected(_, writer):
        await sleep_task
        writer.close()

    server = await start_server(_client_connected, host='localhost', port=0, family=socket.AF_INET)
    _, port = server.sockets[0].getsockname()
    session = HttpTrackerSession("localhost", ("localhost", port), "/announce", .1, None)
    with pytest.raises(ValueError):
        await session.connect_to_tracker()
    sleep_task.set_result(None)
    await session.cleanup()
    server.close()


async def test_udpsession_timeout(fake_udp_socket_manager):
    sleep_future = Future()
    fake_udp_socket_manager.send_request = lambda *_: sleep_future
    transport, _ = await get_event_loop().create_datagram_endpoint(lambda: DatagramProtocol(),
                                                                   local_addr=('127.0.0.1', 0),
                                                                   family=socket.AF_INET)
    _, port = transport.get_extra_info('sockname')
    session = UdpTrackerSession("localhost", ("127.0.0.1", port), "/announce", .1, None, fake_udp_socket_manager)
    with pytest.raises(ValueError):
        await session.connect_to_tracker()
    transport.close()


async def test_pop_finished_transaction():
    """
    Test that receiving a datagram for an already finished tracker session does not result in InvalidStateError
    """
    transaction_id = 123
    mgr = UdpSocketManager()
    mgr.connection_made(Mock())
    task = ensure_future(mgr.send_request(Mock(), Mock(proxy=None, transaction_id=transaction_id)))
    await sleep(0)
    assert mgr.tracker_sessions

    data = struct.pack("!iiq", 124, transaction_id, 126)
    mgr.datagram_received(data, None)
    assert not mgr.tracker_sessions
    await task
    assert task.done()


async def test_proxy_transport():
    """
    Test that the UdpSocketManager uses a proxy if specified
    """
    mgr = UdpSocketManager()
    mgr.connection_made(Mock())
    mgr.proxy_transports['proxy_url'] = Mock()
    ensure_future(mgr.send_request(b'', Mock(proxy='proxy_url', transaction_id=123)))
    await sleep(0)
    mgr.proxy_transports['proxy_url'].sendto.assert_called_once()
    mgr.transport.assert_not_called()
    mgr.tracker_sessions[123].cancel()

    ensure_future(mgr.send_request(b'', Mock(proxy=None, transaction_id=123)))
    await sleep(0)
    mgr.proxy_transports['proxy_url'].sendto.assert_called_once()
    mgr.transport.sendto.assert_called_once()
    mgr.tracker_sessions[123].cancel()


async def test_httpsession_cancel_operation():
    session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5, None)
    task = ensure_future(session.connect_to_tracker())
    with pytest.raises(CancelledError):
        task.cancel()
        await task
    await session.cleanup()


async def test_udpsession_cancel_operation(fake_udp_socket_manager):
    session = UdpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 0, None, fake_udp_socket_manager)
    task = ensure_future(session.connect_to_tracker())
    with pytest.raises(CancelledError):
        task.cancel()
        await task
    await session.cleanup()


async def test_udpsession_handle_response_wrong_len(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    assert not session.is_failed
    fake_udp_socket_manager.response = b"too short"
    with pytest.raises(ValueError):
        await session.connect()
    assert session.is_failed

    # After receiving a correct packet, it session should still be in a failed state
    session.action = 123
    session.transaction_id = 124
    fake_udp_socket_manager.response = struct.pack("!iiq", 123, 124, 126)
    await session.connect()
    assert session.is_failed


async def test_udpsession_no_port(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    assert not session.is_failed
    fake_udp_socket_manager.transport = None
    with pytest.raises(ValueError):
        await session.connect()
    assert session.is_failed


async def test_udpsession_handle_connection_wrong_action_transaction(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    assert not session.is_failed
    fake_udp_socket_manager.response = struct.pack("!qq4s", 123, 123, b"test")
    with pytest.raises(ValueError):
        await session.scrape()
    assert session.is_failed


async def test_udpsession_handle_packet(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    session.action = 123
    session.transaction_id = 124
    assert not session.is_failed
    fake_udp_socket_manager.response = struct.pack("!iiq", 123, 124, 126)
    await session.connect()
    assert not session.is_failed


async def test_udpsession_handle_wrong_action_transaction(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    assert not session.is_failed
    fake_udp_socket_manager.response = struct.pack("!qq4s", 123, 123, b"test")
    with pytest.raises(ValueError):
        await session.connect()
    assert session.is_failed


async def test_udpsession_mismatch(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    session.action = 123
    session.transaction_id = 124
    session.infohash_list = [b'\x00' * 20]
    assert not session.is_failed
    fake_udp_socket_manager.response = struct.pack("!ii", 123, 124)
    with pytest.raises(ValueError):
        await session.scrape()
    assert session.is_failed


async def test_udpsession_response_too_short(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    assert not session.is_failed
    fake_udp_socket_manager.response = struct.pack("!i", 123)
    with pytest.raises(ValueError):
        await session.scrape()
    assert session.is_failed


async def test_udpsession_response_wrong_transaction_id(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    assert not session.is_failed
    fake_udp_socket_manager.response = struct.pack("!ii", 0, 1337)
    with pytest.raises(ValueError):
        await session.scrape()
    assert session.is_failed


async def test_udpsession_response_list_len_mismatch(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 0, None, fake_udp_socket_manager)
    session.action = 123
    session.transaction_id = 123
    assert not session.is_failed
    session._infohash_list = [b"test", b"test2"]
    fake_udp_socket_manager.response = struct.pack("!iiiii", 123, 123, 0, 1, 2)
    with pytest.raises(ValueError):
        await session.scrape()
    assert session.is_failed
    await session.cleanup()


async def test_udpsession_correct_handle(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5, None, fake_udp_socket_manager)
    session.ip_address = "127.0.0.1"
    session.infohash_list.append(b'test')
    fake_udp_socket_manager.response = struct.pack("!iiq", 0, session.transaction_id, 2)
    await session.connect()
    fake_udp_socket_manager.response = struct.pack("!iiiii", 2, session.transaction_id, 0, 1, 2)
    await session.scrape()
    assert not session.is_failed
    await session.cleanup()


async def test_big_correct_run(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("192.168.1.1", 1234), "/announce", 0, None, fake_udp_socket_manager)
    assert not session.is_failed
    fake_udp_socket_manager.response = struct.pack("!iiq", session.action, session.transaction_id, 126)
    await session.connect()
    session.infohash_list = [b"test"]
    fake_udp_socket_manager.response = struct.pack("!iiiii", session.action, session.transaction_id, 0, 1, 2)
    await session.scrape()
    assert session.is_finished
    await session.cleanup()


async def test_http_unprocessed_infohashes():
    session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)
    session.infohash_list.append(b"test")
    response = bencode({"files": {b"a" * 20: {"complete": 10, "incomplete": 10}}})
    session._process_scrape_response(response)
    assert session.is_finished
    await session.cleanup()


async def test_failed_unicode():
    session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5, None)
    with pytest.raises(ValueError):
        session._process_scrape_response(bencode({'failure reason': '\xe9'}))
    await session.cleanup()


def test_failed_unicode_udp(fake_udp_socket_manager):
    session = UdpTrackerSession("localhost", ("localhost", 8475), "/announce", 0, None, fake_udp_socket_manager)
    with pytest.raises(ValueError):
        session.failed('\xd0')


async def test_cleanup(bep33_session):
    """
    Test the cleanup of a DHT session
    """
    await bep33_session.cleanup()


async def test_connect_to_tracker(mock_dlmgr, fake_dht_session):
    """
    Test the metainfo lookup of the DHT session
    """
    metainfo = {b'seeders': 42, b'leechers': 42}
    mock_dlmgr.get_metainfo = lambda *_, **__: succeed(metainfo)
    fake_dht_session.add_infohash(b'a' * 20)
    response = await fake_dht_session.connect_to_tracker()

    assert response.url == 'DHT'
    assert len(response.torrent_health_list) == 1

    health = response.torrent_health_list[0]
    assert health.leechers == 42
    assert health.seeders == 42


async def test_connect_to_tracker_fail(mock_dlmgr, fake_dht_session):
    """
    Test the metainfo lookup of the DHT session when it fails
    """
    mock_dlmgr.get_metainfo = Mock(side_effect=TimeoutError)
    fake_dht_session.add_infohash(b'a' * 20)
    with pytest.raises(TimeoutError):
        await fake_dht_session.connect_to_tracker()


async def test_connect_to_tracker_bep33(bep33_session, mock_dlmgr):
    """
    Test the metainfo lookup of the BEP33 DHT session
    """
    infohash = b'a' * 20
    infohash_health = HealthInfo(infohash, seeders=1, leechers=2)

    mock_dlmgr.dht_health_manager = Mock()
    mock_dlmgr.dht_health_manager.get_health = lambda *_, **__: succeed(infohash_health)
    bep33_session.add_infohash(infohash)
    response = await bep33_session.connect_to_tracker()
    assert response.url == 'DHT'
    assert len(response.torrent_health_list) == 1

    health = response.torrent_health_list[0]
    assert health.leechers == 2
    assert health.seeders == 1
