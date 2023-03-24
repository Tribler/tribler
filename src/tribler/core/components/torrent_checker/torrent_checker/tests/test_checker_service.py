from asyncio import CancelledError
from binascii import unhexlify
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from tribler.core.components.torrent_checker.torrent_checker.checker_service import CheckerService
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo, TrackerResponse
from tribler.core.components.torrent_checker.torrent_checker.torrentchecker_session import \
    UdpSocketManager


@pytest.fixture(name="checker_service")
async def checker_service_fixture():
    checker_service = CheckerService(proxy=MagicMock())
    yield checker_service
    await checker_service.shutdown()


async def test_create_socket_fail(checker_service):
    """
    Test creation of the UDP socket of the torrent checker service when it fails.
    """

    def mocked_listen_on_udp():
        raise OSError("Something went wrong")

    checker_service.socket_mgr = UdpSocketManager()
    checker_service.listen_on_udp = mocked_listen_on_udp
    await checker_service.create_socket_or_schedule()

    assert checker_service.udp_transport is None
    assert checker_service.is_pending_task_active("listen_udp_port")


async def test_get_tracker_response_cancelled_error(checker_service):
    """
    Tests that CancelledError from get_tracker_response() is handled correctly.
    """
    tracker_url = 'udp://example.com:1337/announce'

    checker_service.udp_tracker = Mock()
    checker_service.udp_tracker.get_tracker_response = AsyncMock(side_effect=CancelledError())

    with pytest.raises(CancelledError):
        await checker_service.get_tracker_response(tracker_url)


async def test_get_tracker_response_other_error(checker_service):
    """
    Tests that arbitrary exception from get_tracker_response() is handled correctly.
    """
    tracker_url = 'udp://example.com:1337/announce'

    checker_service.udp_tracker = Mock()
    checker_service.udp_tracker.get_tracker_response = AsyncMock(side_effect=ValueError('error text'))

    with pytest.raises(ValueError, match='^error text$'):
        await checker_service.get_tracker_response(tracker_url)


async def test_get_tracker_response(checker_service: CheckerService):
    """
    Tests that the result from get_tracker_response() is handled correctly.
    """
    health = HealthInfo(unhexlify('abcd0123'))
    tracker_url = 'udp://example.com:1337/announce'
    tracker_response = TrackerResponse(url=tracker_url, torrent_health_list=[health])

    checker_service.udp_tracker = Mock()
    checker_service.udp_tracker.get_tracker_response = AsyncMock(side_effect=[tracker_response])

    results = await checker_service.get_tracker_response(tracker_url, [None])
    assert results is tracker_response
