import logging
import os
import time
from asyncio import CancelledError
from binascii import unhexlify
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from ipv8.util import succeed
from pony.orm import db_session

import tribler.core.components.torrent_checker.torrent_checker.torrent_checker as torrent_checker_module
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo, TrackerResponse
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.components.torrent_checker.torrent_checker.torrentchecker_session import \
    HttpTrackerSession, UdpSocketManager
from tribler.core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager
from tribler.core.components.torrent_checker.torrent_checker.utils import filter_non_exceptions


# pylint: disable=protected-access

@pytest.fixture(name="tracker_manager")
def tracker_manager_fixture(tmp_path, metadata_store):
    return TrackerManager(state_dir=tmp_path, metadata_store=metadata_store)


@pytest.fixture(name="torrent_checker")
async def torrent_checker_fixture(tribler_config, tracker_manager, metadata_store):
    torrent_checker = TorrentChecker(config=tribler_config,
                                     download_manager=MagicMock(),
                                     notifier=MagicMock(),
                                     metadata_store=metadata_store,
                                     tracker_manager=tracker_manager
                                     )
    yield torrent_checker
    await torrent_checker.shutdown()


async def test_create_socket_fail(torrent_checker):
    """
    Test creation of the UDP socket of the torrent checker when it fails
    """

    def mocked_listen_on_udp():
        raise OSError("Something went wrong")

    torrent_checker.socket_mgr = UdpSocketManager()
    torrent_checker.listen_on_udp = mocked_listen_on_udp
    await torrent_checker.create_socket_or_schedule()

    assert torrent_checker.udp_transport is None
    assert torrent_checker.is_pending_task_active("listen_udp_port")


async def test_health_check_blacklisted_trackers(torrent_checker):
    """
    Test whether only cached results of a torrent are returned with only blacklisted trackers
    """
    with db_session:
        tracker = torrent_checker.mds.TrackerState(url="http://localhost/tracker")
        torrent_checker.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                         last_check=int(time.time()))

    torrent_checker.tracker_manager.blacklist.append("http://localhost/tracker")
    result = await torrent_checker.check_torrent_health(b'a' * 20)
    assert result.seeders == 5
    assert result.leechers == 10


async def test_health_check_cached(torrent_checker):
    """
    Test whether cached results of a torrent are returned when fetching the health of a torrent
    """
    with db_session:
        tracker = torrent_checker.mds.TrackerState(url="http://localhost/tracker")
        torrent_checker.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                         last_check=int(time.time()))

    result = await torrent_checker.check_torrent_health(b'a' * 20)
    assert result.seeders == 5
    assert result.leechers == 10


async def test_task_select_no_tracker(torrent_checker):
    """
    Test whether we are not checking a random tracker if there are no trackers in the database.
    """
    result = await torrent_checker.check_random_tracker()
    assert not result


async def test_check_random_tracker_shutdown(torrent_checker):
    """
    Test whether we are not performing a tracker check if we are shutting down.
    """
    await torrent_checker.shutdown()
    result = await torrent_checker.check_random_tracker()
    assert not result


async def test_check_random_tracker_not_alive(torrent_checker):
    """
    Test whether we correctly update the tracker state when the number of failures is too large.
    """
    with db_session:
        torrent_checker.mds.TrackerState(url="http://localhost/tracker", failures=1000, alive=True)

    result = await torrent_checker.check_random_tracker()
    assert not result

    with db_session:
        tracker = torrent_checker.tracker_manager.TrackerState.get()
        assert not tracker.alive


async def test_task_select_tracker(torrent_checker):
    with db_session:
        tracker = torrent_checker.mds.TrackerState(url="http://localhost/tracker")
        torrent_checker.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker})

    controlled_session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5, None)
    controlled_session.connect_to_tracker = lambda: succeed(None)

    torrent_checker._create_session_for_request = lambda *args, **kwargs: controlled_session

    result = await torrent_checker.check_random_tracker()

    assert not result
    assert len(controlled_session.infohash_list) == 1

    await controlled_session.cleanup()


async def test_tracker_test_error_resolve(torrent_checker: TorrentChecker):
    """
    Test whether we capture the error when a tracker check fails
    """
    with db_session:
        tracker = torrent_checker.mds.TrackerState(url="http://localhost/tracker")
        torrent_checker.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                         last_check=int(time.time()))
    result = await torrent_checker.check_random_tracker()
    assert not result

    # Verify whether we successfully cleaned up the session after an error
    assert not torrent_checker._sessions


async def test_tracker_no_infohashes(torrent_checker):
    """
    Test the check of a tracker without associated torrents
    """
    torrent_checker.tracker_manager.add_tracker('http://trackertest.com:80/announce')
    result = await torrent_checker.check_random_tracker()
    assert not result


def test_filter_non_exceptions():
    response = TrackerResponse(url='url', torrent_health_list=[])
    responses = [response, Exception()]

    assert filter_non_exceptions(responses) == [response]


async def test_check_local_torrents(torrent_checker):
    """
    Test that the random torrent health checking mechanism picks the right torrents
    """

    def random_infohash():
        return os.urandom(20)

    num_torrents = 20
    torrent_checker.check_torrent_health = lambda _: succeed(None)

    # No torrents yet, the selected torrents should be empty
    selected_torrents, _ = await torrent_checker.check_local_torrents()
    assert len(selected_torrents) == 0

    # Add some freshly checked torrents
    time_fresh = time.time()
    fresh_infohashes = []
    for index in range(0, num_torrents):
        infohash = random_infohash()
        with db_session:
            torrent = torrent_checker.mds.TorrentMetadata(title=f'torrent{index}', infohash=infohash)
            torrent.health.seeders = index
            torrent.health.last_check = int(time_fresh) + index
            fresh_infohashes.append(infohash)

    # Add some stale (old) checked torrents
    time_stale = time_fresh - torrent_checker_module.HEALTH_FRESHNESS_SECONDS
    stale_infohashes = []
    max_seeder = 10000  # some random value
    for index in range(0, num_torrents):
        infohash = random_infohash()
        with db_session:
            torrent = torrent_checker.mds.TorrentMetadata(title=f'torrent{index}', infohash=infohash)
            torrent.health.seeders = max_seeder - index  # Note: decreasing trend
            torrent.health.last_check = int(time_stale) - index  # Note: decreasing trend
        stale_infohashes.append(infohash)

    # Now check that all torrents selected for check are stale torrents.
    selected_torrents, _ = await torrent_checker.check_local_torrents()
    assert len(selected_torrents) <= torrent_checker_module.TORRENT_SELECTION_POOL_SIZE

    # In the above setup, both seeder (popularity) count and last_check are decreasing so,
    # 1. Popular torrents are in the front, and
    # 2. Older torrents are towards the back
    # Therefore the selection range becomes:
    selection_range = stale_infohashes[0: torrent_checker_module.TORRENT_SELECTION_POOL_SIZE] \
                      + stale_infohashes[- torrent_checker_module.TORRENT_SELECTION_POOL_SIZE:]

    for t in selected_torrents:
        assert t.infohash in selection_range


async def test_check_channel_torrents(torrent_checker: TorrentChecker):
    """
    Test that the channel torrents are checked based on last checked time.
    Only outdated torrents are selected for health checks.
    """

    def random_infohash():
        return os.urandom(20)

    @db_session
    def add_torrent_to_channel(infohash, last_check):
        torrent = torrent_checker.mds.TorrentMetadata(public_key=torrent_checker.mds.my_public_key_bin,
                                                      infohash=infohash)
        torrent.health.last_check = last_check
        return torrent

    check_torrent_health_mock = AsyncMock(return_value=None)
    torrent_checker.check_torrent_health = lambda _: check_torrent_health_mock()

    # No torrents yet in channel, the selected channel torrents to check should be empty
    selected_torrents = torrent_checker.db_service.torrents_to_check_in_user_channel()
    assert len(selected_torrents) == 0

    # No health check call are done
    await torrent_checker.check_torrents_in_user_channel()
    assert check_torrent_health_mock.call_count == len(selected_torrents)

    num_torrents = 20
    timestamp_now = int(time.time())
    timestamp_outdated = timestamp_now - torrent_checker_module.HEALTH_FRESHNESS_SECONDS

    # Add some recently checked and outdated torrents to the channel
    fresh_torrents = []
    for _ in range(num_torrents):
        torrent = add_torrent_to_channel(random_infohash(), last_check=timestamp_now)
        fresh_torrents.append(torrent)

    outdated_torrents = []
    for _ in range(num_torrents):
        torrent = add_torrent_to_channel(random_infohash(), last_check=timestamp_outdated)
        outdated_torrents.append(torrent.infohash)

    # Now check that only outdated torrents are selected for check
    selected_torrents = torrent_checker.db_service.torrents_to_check_in_user_channel()
    assert len(selected_torrents) <= torrent_checker_module.USER_CHANNEL_TORRENT_SELECTION_POOL_SIZE
    for torrent in selected_torrents:
        assert torrent.infohash in outdated_torrents

    # Health check requests are sent for all selected torrents
    result = await torrent_checker.check_torrents_in_user_channel()
    assert len(result) == len(selected_torrents)


async def test_get_tracker_response_cancelled_error(torrent_checker: TorrentChecker, caplog):
    """
    Tests that CancelledError from session.connect_to_tracker() is handled correctly
    """
    torrent_checker.clean_session = AsyncMock()
    torrent_checker.update_torrent_health = Mock()
    torrent_checker.tracker_manager.update_tracker_info = Mock()

    tracker_url = '<tracker_url>'
    session = Mock(tracker_url=tracker_url)
    session.connect_to_tracker = AsyncMock(side_effect=CancelledError())

    with pytest.raises(CancelledError):
        await torrent_checker.get_tracker_response(session)

    torrent_checker.clean_session.assert_called_once()
    torrent_checker.update_torrent_health.assert_not_called()
    torrent_checker.tracker_manager.update_tracker_info.assert_not_called()

    assert caplog.record_tuples == [
        ('TorrentChecker', logging.INFO, 'Tracker session is being cancelled: <tracker_url>')
    ]


async def test_get_tracker_response_other_error(torrent_checker: TorrentChecker, caplog):
    """
    Tests that arbitrary exception from session.connect_to_tracker() is handled correctly
    """
    torrent_checker.clean_session = AsyncMock()
    torrent_checker.update_torrent_health = Mock()
    torrent_checker.tracker_manager.update_tracker_info = Mock()

    tracker_url = '<tracker_url>'
    session = Mock(tracker_url=tracker_url)
    session.connect_to_tracker = AsyncMock(side_effect=ValueError('error text'))

    with pytest.raises(ValueError, match='^error text$'):
        await torrent_checker.get_tracker_response(session)

    torrent_checker.clean_session.assert_called_once()
    torrent_checker.update_torrent_health.assert_not_called()
    torrent_checker.tracker_manager.update_tracker_info.assert_called_once_with(tracker_url, False)

    assert caplog.record_tuples == [
        ('TorrentChecker', logging.WARNING, "Got session error for the tracker: <tracker_url>\nerror text")
    ]


async def test_get_tracker_response(torrent_checker: TorrentChecker, caplog):
    """
    Tests that the result from session.connect_to_tracker() is handled correctly and passed to update_torrent_health()
    """
    health = HealthInfo(unhexlify('abcd0123'))
    tracker_url = '<tracker_url>'
    tracker_response = TrackerResponse(url=tracker_url, torrent_health_list=[health])

    session = Mock(tracker_url=tracker_url)
    session.connect_to_tracker = AsyncMock(return_value=tracker_response)

    torrent_checker.clean_session = AsyncMock()
    # torrent_checker.db_service = Mock()
    torrent_checker.db_service.update_torrent_health = Mock()
    results = await torrent_checker.get_tracker_response(session)

    assert results is tracker_response
    torrent_checker.db_service.update_torrent_health.assert_called_once_with(health)

    assert "Got response from Mock" in caplog.text
