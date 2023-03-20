import logging
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
    checker_service = CheckerService(download_manager=MagicMock(),
                                     proxy=MagicMock())
    yield checker_service
    await checker_service.shutdown()


async def test_create_socket_fail(checker_service):
    """
    Test creation of the UDP socket of the torrent checker when it fails
    """

    def mocked_listen_on_udp():
        raise OSError("Something went wrong")

    checker_service.socket_mgr = UdpSocketManager()
    checker_service.listen_on_udp = mocked_listen_on_udp
    await checker_service.create_socket_or_schedule()

    assert checker_service.udp_transport is None
    assert checker_service.is_pending_task_active("listen_udp_port")


async def test_get_tracker_response_cancelled_error(checker_service, caplog):
    """
    Tests that CancelledError from session.connect_to_tracker() is handled correctly
    """
    checker_service.clean_session = AsyncMock()

    tracker_url = '<tracker_url>'
    session = Mock(tracker_url=tracker_url)
    session.connect_to_tracker = AsyncMock(side_effect=CancelledError())

    with pytest.raises(CancelledError):
        await checker_service.get_tracker_response(session)

    checker_service.clean_session.assert_called_once()

    assert caplog.record_tuples == [
        ('CheckerService', logging.INFO, 'Tracker session is being cancelled: <tracker_url>')
    ]


async def test_get_tracker_response_other_error(checker_service, caplog):
    """
    Tests that arbitrary exception from session.connect_to_tracker() is handled correctly
    """
    checker_service.clean_session = AsyncMock()

    tracker_url = '<tracker_url>'
    session = Mock(tracker_url=tracker_url)
    session.connect_to_tracker = AsyncMock(side_effect=ValueError('error text'))

    with pytest.raises(ValueError, match='^error text$'):
        await checker_service.get_tracker_response(session)

    checker_service.clean_session.assert_called_once()

    assert caplog.record_tuples == [
        ('CheckerService', logging.WARNING, "Got session error for the tracker: <tracker_url>\nerror text")
    ]


async def test_get_tracker_response(checker_service: CheckerService, caplog):
    """
    Tests that the result from session.connect_to_tracker() is handled correctly and passed to update_torrent_health()
    """
    health = HealthInfo(unhexlify('abcd0123'))
    tracker_url = '<tracker_url>'
    tracker_response = TrackerResponse(url=tracker_url, torrent_health_list=[health])

    session = Mock(tracker_url=tracker_url)
    session.connect_to_tracker = AsyncMock(return_value=tracker_response)

    checker_service.clean_session = AsyncMock()
    results = await checker_service.get_tracker_response(session)
    assert results is tracker_response
    assert "Got response from Mock" in caplog.text
