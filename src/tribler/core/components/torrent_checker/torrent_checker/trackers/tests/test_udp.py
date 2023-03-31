import asyncio
import socket
from asyncio import Future, get_event_loop
from binascii import unhexlify
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

import pytest
from pytest_asyncio import fixture

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import UdpRequest
from tribler.core.components.torrent_checker.torrent_checker.trackers import TrackerException
from tribler.core.components.torrent_checker.torrent_checker.trackers.udp import UdpTracker, TRACKER_ACTION_CONNECT
from tribler.core.tests.tools.tracker.udp_tracker import TRACKER_ACTION_SCRAPE

SAMPLE_INFOHASH = unhexlify("2c6b6858d61da9543d4231a71db4b1c9264b0685")  # Ubuntu 20.04
SAMPLE_TRACKER_URL = "udp://tracker.example.com:1337"
SAMPLE_INVALID_TRACKER_URL = "udp://no-port-tracker.com"
SAMPLE_VALID_TRACKER_CONNECTION_RESPONSE = b'\x00\x00\x00\x00\x00\x00\x00\x00$v\x1e\x80\x90\xcc\x17\x84'
# Below response is encoded representation of Seeders = 42, Leechers = 0
SAMPLE_VALID_TRACKER_SCRAPE_RESPONSE = b'\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00*\x00\x00\x047\x00\x00\x00\x00'
SAMPLE_PROXY = ('127.0.0.1', 2000)

# Tracker host/port
SAMPLE_HOST = '127.0.0.1'
SAMPLE_PORT = 1234

# Connection Request/Response
SAMPLE_CONNECTION_ID = 2627320970151204740
SAMPLE_CONNECTION_TRANSACTION_ID = 0
SAMPLE_CONNECTION_RESPONSE = b'\x00\x00\x00\x00\x00\x00\x00\x00$v\x1e\x80\x90\xcc\x17\x84'

# Scrape Request/Response
SAMPLE_SCRAPE_TRANSACTION_ID = 1
SAMPLE_SCRAPE_RESPONSE = b'\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00*\x00\x00\x047\x00\x00\x00\x00'
SAMPLE_SCRAPE_RESPONSE_HEALTH = [(0, 0, 0)]
SAMPLE_INVALID_SCRAPE_RESPONSE = b'\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00*\x00\x00\x047\x00\x00\x00\x00\x00\x00'

INVALID_TRACKER_ACTION = -1


@fixture(name='socket_manager')
def socket_manager_fixture():
    return MagicMock()


@fixture(name='udp_tracker')
async def udp_tracker_fixture(socket_manager):
    return UdpTracker(socket_manager)


@fixture(name='event_loop')
async def event_loop_fixture():
    event_loop = get_event_loop()
    event_loop.getaddrinfo = AsyncMock()
    yield event_loop


@fixture(name='connection_request')
async def sample_connection_request(udp_tracker):
    ip = SAMPLE_HOST
    port = SAMPLE_PORT
    transaction_id = SAMPLE_CONNECTION_TRANSACTION_ID
    return udp_tracker.compose_connect_request(ip, port, transaction_id)


@fixture(name='scrape_request')
async def sample_scrape_request(udp_tracker):
    ip = SAMPLE_HOST
    port = SAMPLE_PORT
    transaction_id = SAMPLE_SCRAPE_TRANSACTION_ID
    connection_id = SAMPLE_CONNECTION_ID
    infohash_list = [SAMPLE_INFOHASH]
    return udp_tracker.compose_scrape_request(ip, port, transaction_id, connection_id, infohash_list)


async def test_get_tracker_response(socket_manager, udp_tracker):

    async def mock_send(udp_request, response_callback=None):
        if udp_request.is_connection_request():
            await udp_tracker.process_connection_response(udp_request, SAMPLE_VALID_TRACKER_CONNECTION_RESPONSE)
        elif udp_request.is_scrape_request():
            await udp_tracker.process_scrape_response(udp_request, SAMPLE_VALID_TRACKER_SCRAPE_RESPONSE)

    socket_manager.send = AsyncMock(side_effect=mock_send)
    udp_tracker.resolve_ip = AsyncMock(return_value='1.1.1.1')

    response = await udp_tracker.get_tracker_response(SAMPLE_TRACKER_URL, [SAMPLE_INFOHASH], timeout=0.01)
    health_list = response.torrent_health_list

    assert response.url == SAMPLE_TRACKER_URL
    assert len(health_list) == 1
    assert health_list[0].infohash == SAMPLE_INFOHASH
    assert health_list[0].seeders == 42
    assert health_list[0].leechers == 0


async def test_get_tracker_response_with_no_socket_mgr(udp_tracker):
    udp_tracker.socket_manager = None

    with pytest.raises(TrackerException) as te:
        _ = await udp_tracker.get_tracker_response(SAMPLE_TRACKER_URL, [SAMPLE_INFOHASH], timeout=0.01)
    assert te.match("UDP socket transport is not ready yet")

    udp_tracker.socket_manager = MagicMock()
    udp_tracker.socket_manager.transport = None

    with pytest.raises(TrackerException) as te:
        _ = await udp_tracker.get_tracker_response(SAMPLE_TRACKER_URL, [SAMPLE_INFOHASH], timeout=0.01)
    assert te.match("UDP socket transport is not ready yet")


async def test_get_tracker_response_timeout(udp_tracker):
    timeout = 0.01

    async def mock_resolve_ip_with_timeout(_):
        await asyncio.sleep(timeout)
        return None

    udp_tracker.resolve_ip = AsyncMock(side_effect=mock_resolve_ip_with_timeout)

    with pytest.raises(TrackerException) as te:
        _ = await udp_tracker.get_tracker_response(SAMPLE_TRACKER_URL, [SAMPLE_INFOHASH], timeout=timeout)
    assert te.match("Request timeout returning tracker response for")


async def test_get_tracker_response_with_invalid_tracker(udp_tracker):
    timeout = 0.01

    with pytest.raises(TrackerException) as te:
        _ = await udp_tracker.get_tracker_response(SAMPLE_INVALID_TRACKER_URL, [SAMPLE_INFOHASH], timeout=timeout)
    assert te.match("Invalid tracker URL")


@pytest.mark.asyncio
async def test_resolve_ip_without_proxy(event_loop, udp_tracker):
    tracker_address = ('tracker.example.com', 1234)
    ip_address = '192.168.1.1'
    event_loop.getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP, '', (ip_address, 0))]

    result = await udp_tracker.resolve_ip(tracker_address)

    assert result == ip_address
    event_loop.getaddrinfo.assert_called_once_with(tracker_address[0], 0, family=socket.AF_INET)


@pytest.mark.asyncio
async def test_resolve_ip_with_proxy(udp_tracker):
    tracker_address = ('tracker.example.com', 1234)
    udp_tracker.proxy = SAMPLE_PROXY

    ip = await udp_tracker.resolve_ip(tracker_address)
    assert ip == tracker_address[0]


async def test_connect_to_tracker(socket_manager, udp_tracker, connection_request):
    ip = '127.0.0.1'
    port = 1337
    expected_connection_id = b'1011'
    mock_connection_request = SimpleNamespace(response=Future())

    async def mock_send(udp_request, response_callback=None):
        mock_connection_request.response.set_result(expected_connection_id)

    socket_manager.send = AsyncMock(side_effect=mock_send)
    udp_tracker.compose_connect_request = lambda _ip, _port, _: mock_connection_request
    udp_tracker.await_process_connection_response = AsyncMock()

    connection_id = await udp_tracker.connect_to_tracker(ip, port)

    assert connection_id == expected_connection_id


async def test_process_connection_response(udp_tracker: UdpTracker, connection_request: UdpRequest):
    connection_id = SAMPLE_CONNECTION_ID

    # Fail for invalid action
    invalid_action = INVALID_TRACKER_ACTION
    transaction_id = connection_request.transaction_id

    udp_tracker.unpack_connection_response = lambda _: (invalid_action, transaction_id, connection_id)
    with pytest.raises(TrackerException):
        await udp_tracker.process_connection_response(connection_request, SAMPLE_CONNECTION_RESPONSE)

    # Fail for invalid transaction id
    action = TRACKER_ACTION_CONNECT
    invalid_transaction_id = connection_request.transaction_id + 1

    udp_tracker.unpack_connection_response = lambda _: (action, invalid_transaction_id, connection_id)
    with pytest.raises(TrackerException):
        await udp_tracker.process_connection_response(connection_request, SAMPLE_CONNECTION_RESPONSE)

    # Pass for valid action and valid transaction id
    action = TRACKER_ACTION_CONNECT
    transaction_id = connection_request.transaction_id

    udp_tracker.unpack_connection_response = lambda _: (action, transaction_id, connection_id)
    await udp_tracker.process_connection_response(connection_request, SAMPLE_CONNECTION_RESPONSE)

    obtained_connection_id = connection_request.response.result()
    assert obtained_connection_id == connection_id


async def test_process_scrape_response(udp_tracker: UdpTracker, scrape_request: UdpRequest):
    # Fail for invalid action
    invalid_action = INVALID_TRACKER_ACTION
    transaction_id = scrape_request.transaction_id
    health_info = SAMPLE_SCRAPE_RESPONSE_HEALTH

    udp_tracker.unpack_scrape_response = lambda _: (invalid_action, transaction_id, health_info)
    with pytest.raises(TrackerException) as te:
        await udp_tracker.process_scrape_response(scrape_request, SAMPLE_SCRAPE_RESPONSE)
    te.match("Invalid UDP scrape response")

    # Fail for invalid transaction id
    action = TRACKER_ACTION_SCRAPE
    invalid_transaction_id = scrape_request.transaction_id + 1

    udp_tracker.unpack_scrape_response = lambda _: (action, invalid_transaction_id, health_info)
    with pytest.raises(TrackerException):
        await udp_tracker.process_scrape_response(scrape_request, SAMPLE_SCRAPE_RESPONSE)
    te.match("Invalid UDP scrape response")

    # Pass for valid response
    action = TRACKER_ACTION_SCRAPE
    transaction_id = scrape_request.transaction_id

    udp_tracker.unpack_scrape_response = lambda _: (action, transaction_id, health_info)
    await udp_tracker.process_scrape_response(scrape_request, SAMPLE_SCRAPE_RESPONSE)

    health_infos = scrape_request.response.result()
    assert len(health_infos) == 1