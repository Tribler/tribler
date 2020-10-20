import os
import socket
import time

from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.torrent_checker.torrentchecker_session import HttpTrackerSession, UdpSocketManager
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
async def torrent_checker(session):
    torrent_checker = TorrentChecker(session)
    yield torrent_checker
    await torrent_checker.shutdown()


@pytest.mark.asyncio
async def test_initialize(torrent_checker):
    """
    Test the initialization of the torrent checker
    """
    await torrent_checker.initialize()
    assert torrent_checker.is_pending_task_active("tracker_check")
    assert torrent_checker.is_pending_task_active("torrent_check")


@pytest.mark.asyncio
async def test_create_socket_fail(torrent_checker):
    """
    Test creation of the UDP socket of the torrent checker when it fails
    """
    def mocked_listen_on_udp():
        raise socket.error("Something went wrong")

    torrent_checker.socket_mgr = UdpSocketManager()
    torrent_checker.listen_on_udp = mocked_listen_on_udp
    await torrent_checker.create_socket_or_schedule()

    assert torrent_checker.udp_transport is None
    assert torrent_checker.is_pending_task_active("listen_udp_port")


@pytest.mark.asyncio
async def test_health_check_blacklisted_trackers(enable_chant, torrent_checker, session):
    """
    Test whether only cached results of a torrent are returned with only blacklisted trackers
    """
    with db_session:
        tracker = session.mds.TrackerState(url="http://localhost/tracker")
        session.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                 last_check=int(time.time()))

    session.tracker_manager.blacklist.append("http://localhost/tracker")
    result = await torrent_checker.check_torrent_health(b'a' * 20)
    assert {'db'} == set(result.keys())
    assert result['db']['seeders'] == 5
    assert result['db']['leechers'] == 10


@pytest.mark.asyncio
async def test_health_check_cached(enable_chant, torrent_checker, session):
    """
    Test whether cached results of a torrent are returned when fetching the health of a torrent
    """
    with db_session:
        tracker = session.mds.TrackerState(url="http://localhost/tracker")
        session.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                 last_check=int(time.time()))

    result = await torrent_checker.check_torrent_health(b'a' * 20)
    assert 'db' in result
    assert result['db']['seeders'] == 5
    assert result['db']['leechers'] == 10


@pytest.mark.asyncio
async def test_task_select_no_tracker(enable_chant, torrent_checker):
    """
    Test whether we are not checking a random tracker if there are no trackers in the database.
    """
    result = await torrent_checker.check_random_tracker()
    assert not result


@pytest.mark.asyncio
async def test_check_random_tracker_shutdown(enable_chant, torrent_checker):
    """
    Test whether we are not performing a tracker check if we are shutting down.
    """
    await torrent_checker.shutdown()
    result = await torrent_checker.check_random_tracker()
    assert not result


@pytest.mark.asyncio
async def test_check_random_tracker_not_alive(enable_chant, torrent_checker, session):
    """
    Test whether we correctly update the tracker state when the number of failures is too large.
    """
    with db_session:
        session.mds.TrackerState(url="http://localhost/tracker", failures=1000, alive=True)

    result = await torrent_checker.check_random_tracker()
    assert not result

    with db_session:
        tracker = session.tracker_manager.tracker_store.get()
        assert not tracker.alive


@pytest.mark.asyncio
async def test_task_select_tracker(enable_chant, torrent_checker, session):
    with db_session:
        tracker = session.mds.TrackerState(url="http://localhost/tracker")
        session.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker})

    controlled_session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5, None)
    controlled_session.connect_to_tracker = lambda: succeed(None)

    torrent_checker._create_session_for_request = lambda *args, **kwargs: controlled_session
    result = await torrent_checker.check_random_tracker()
    assert not result

    assert len(controlled_session.infohash_list) == 1


@pytest.mark.asyncio
async def test_tracker_test_error_resolve(enable_chant, torrent_checker, session):
    """
    Test whether we capture the error when a tracker check fails
    """
    with db_session:
        tracker = session.mds.TrackerState(url="http://localhost/tracker")
        session.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                 last_check=int(time.time()))
    result = await torrent_checker.check_random_tracker()
    assert not result

    # Verify whether we successfully cleaned up the session after an error
    assert len(torrent_checker._session_list) == 1


@pytest.mark.asyncio
async def test_tracker_no_infohashes(enable_chant, torrent_checker, session):
    """
    Test the check of a tracker without associated torrents
    """
    session.tracker_manager.add_tracker('http://trackertest.com:80/announce')
    result = await torrent_checker.check_random_tracker()
    assert not result


def test_get_valid_next_tracker_for_auto_check(torrent_checker):
    """
    Test if only valid tracker url are used for auto check
    """
    mock_tracker_state_invalid = MockObject()
    mock_tracker_state_invalid.url = "http://anno nce.torrentsmd.com:8080/announce"
    mock_tracker_state_valid = MockObject()
    mock_tracker_state_valid.url = "http://announce.torrentsmd.com:8080/announce"
    tracker_states = [mock_tracker_state_invalid, mock_tracker_state_valid]

    def get_next_tracker_for_auto_check():
        return tracker_states[0] if tracker_states else None

    def remove_tracker(_):
        tracker_states.remove(mock_tracker_state_invalid)

    torrent_checker.get_next_tracker_for_auto_check = get_next_tracker_for_auto_check
    torrent_checker.remove_tracker = remove_tracker

    next_tracker = torrent_checker.get_valid_next_tracker_for_auto_check()
    assert len(tracker_states) == 1
    assert next_tracker.url == "http://announce.torrentsmd.com:8080/announce"


def test_on_health_check_completed(enable_chant, torrent_checker, session):
    tracker1 = 'udp://localhost:2801'
    tracker2 = "http://badtracker.org/announce"
    infohash_bin = b'\xee'*20
    infohash_hex = hexlify(infohash_bin)

    exception = Exception()
    exception.tracker_url = tracker2
    result = [
        {tracker1: [{'leechers': 1, 'seeders': 2, 'infohash': infohash_hex}]},
        exception,
        {'DHT': [{'leechers': 12, 'seeders': 13, 'infohash': infohash_hex}]}
    ]
    # Check that everything works fine even if the database contains no proper infohash
    res_dict = {
        'DHT': {
            'leechers': 12,
            'seeders': 13,
            'infohash': infohash_hex
        },
        'http://badtracker.org/announce': {
            'error': ''
        },
        'udp://localhost:2801': {
            'leechers': 1,
            'seeders': 2,
            'infohash': infohash_hex
        }
    }
    torrent_checker.on_torrent_health_check_completed(infohash_bin, result)
    assert torrent_checker.on_torrent_health_check_completed(infohash_bin, result) == res_dict
    assert not torrent_checker.on_torrent_health_check_completed(infohash_bin, None)

    with db_session:
        ts = session.mds.TorrentState(infohash=infohash_bin)
        previous_check = ts.last_check
        torrent_checker.on_torrent_health_check_completed(infohash_bin, result)
        assert 1 == len(torrent_checker.torrents_checked)
        assert result[2]['DHT'][0]['leechers'] == ts.leechers
        assert result[2]['DHT'][0]['seeders'] == ts.seeders
        assert previous_check < ts.last_check


def test_on_health_check_failed(enable_chant, torrent_checker):
    """
    Check whether there is no crash when the torrent health check failed and the response is None
    No torrent info is added to torrent_checked list.
    """
    infohash_bin = b'\xee' * 20
    torrent_checker.on_torrent_health_check_completed(infohash_bin, [None])
    assert 0 == len(torrent_checker.torrents_checked)


@db_session
def test_check_random_torrent(enable_chant, torrent_checker, session):
    """
    Test that the random torrent health checking mechanism picks the right torrents
    """
    for ind in range(1, 20):
        torrent = session.mds.TorrentMetadata(title='torrent1', infohash=os.urandom(20))
        torrent.health.last_check = ind

    torrent_checker.check_torrent_health = lambda _: succeed(None)

    random_infohashes = torrent_checker.check_random_torrent()
    assert random_infohashes

    # Now we should only check a single torrent
    torrent_checker.torrents_checked.add((b'a' * 20, 5, 5, int(time.time())))
    random_infohashes = torrent_checker.check_random_torrent()
    assert len(random_infohashes) == 1
