import os
from asyncio import Future
from binascii import unhexlify
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

from pytest_asyncio import fixture

from tribler.core.components.torrent_checker.torrent_checker.trackers.udp import UdpTracker

SAMPLE_INFOHASH = unhexlify("2c6b6858d61da9543d4231a71db4b1c9264b0685")  # Ubuntu 20.04
SAMPLE_TRACKER_URL = "udp://tracker.example.com:1337"
SAMPLE_VALID_TRACKER_CONNECTION_RESPONSE = b'\x00\x00\x00\x00\x00\x00\x00\x00$v\x1e\x80\x90\xcc\x17\x84'
# Below response is encoded representation of Seeders = 42, Leechers = 0
SAMPLE_VALID_TRACKER_SCRAPE_RESPONSE = b'\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00*\x00\x00\x047\x00\x00\x00\x00'


@fixture(name='socket_server')
def socket_server_fixture():
    return MagicMock()


@fixture(name='udp_tracker')
async def udp_tracker_fixture(socket_server):
    return UdpTracker(socket_server)


async def test_get_tracker_response(socket_server, udp_tracker):

    async def mock_send(udp_request, response_callback=None):
        if udp_request.is_connection_request():
            await udp_tracker.process_connection_response(udp_request, SAMPLE_VALID_TRACKER_CONNECTION_RESPONSE)
        elif udp_request.is_scrape_request():
            await udp_tracker.process_scrape_response(udp_request, SAMPLE_VALID_TRACKER_SCRAPE_RESPONSE)

    socket_server.send = AsyncMock(side_effect=mock_send)
    udp_tracker.resolve_ip = AsyncMock(return_value='1.1.1.1')

    response = await udp_tracker.get_tracker_response(SAMPLE_TRACKER_URL, [SAMPLE_INFOHASH], timeout=0.01)
    health_list = response.torrent_health_list

    assert response.url == SAMPLE_TRACKER_URL
    assert len(health_list) == 1
    assert health_list[0].infohash == SAMPLE_INFOHASH
    assert health_list[0].seeders == 42
    assert health_list[0].leechers == 0


async def test_connect_to_tracker(socket_server, udp_tracker):
    ip = '1.1.1.1'
    port = 1337
    expected_connection_id = b'1011'
    mock_connection_request = SimpleNamespace(response=Future())

    async def mock_send(udp_request, response_callback=None):
        mock_connection_request.response.set_result(expected_connection_id)

    socket_server.send = AsyncMock(side_effect=mock_send)
    udp_tracker.compose_connect_request = lambda _ip, _port: mock_connection_request
    udp_tracker.await_process_connection_response = AsyncMock()

    connection_id = await udp_tracker.connect_to_tracker(ip, port)
    assert connection_id == expected_connection_id
