import os
import random
import secrets
import time

from asynctest import Mock

from ipv8.util import succeed

from pony.orm import db_session

import pytest

import tribler_core.components.torrent_checker.torrent_checker.torrent_checker as torrent_checker_module
from tribler_core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.components.torrent_checker.torrent_checker.torrentchecker_session import HttpTrackerSession, \
    UdpSocketManager
from tribler_core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
def tracker_manager(tmp_path, metadata_store):
    return TrackerManager(state_dir=tmp_path, metadata_store=metadata_store)


@pytest.fixture(name="torrent_checker")
async def fixture_torrent_checker(tribler_config, tracker_manager, metadata_store):

    torrent_checker = TorrentChecker(config=tribler_config,
                                     download_manager=Mock(),
                                     notifier=Mock(),
                                     metadata_store=metadata_store,
                                     tracker_manager=tracker_manager
                                     )
    yield torrent_checker
    await torrent_checker.shutdown()


@pytest.mark.asyncio
async def test_initialize(torrent_checker):  # pylint: disable=unused-argument
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
        raise OSError("Something went wrong")

    torrent_checker.socket_mgr = UdpSocketManager()
    torrent_checker.listen_on_udp = mocked_listen_on_udp
    await torrent_checker.create_socket_or_schedule()

    assert torrent_checker.udp_transport is None
    assert torrent_checker.is_pending_task_active("listen_udp_port")


@pytest.mark.asyncio
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
    assert {'db'} == set(result.keys())
    assert result['db']['seeders'] == 5
    assert result['db']['leechers'] == 10


@pytest.mark.asyncio
async def test_health_check_cached(torrent_checker):
    """
    Test whether cached results of a torrent are returned when fetching the health of a torrent
    """
    with db_session:
        tracker = torrent_checker.mds.TrackerState(url="http://localhost/tracker")
        torrent_checker.mds.TorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                                         last_check=int(time.time()))

    result = await torrent_checker.check_torrent_health(b'a' * 20)
    assert 'db' in result
    assert result['db']['seeders'] == 5
    assert result['db']['leechers'] == 10


@pytest.mark.asyncio
async def test_load_torrents_check_from_db(torrent_checker):  # pylint: disable=unused-argument
    """
    Test if the torrents_checked set is properly initialized based on the last_check
    and self_checked values from the database.
    """
    @db_session
    def save_random_torrent_state(last_checked=0, self_checked=False, count=1):
        for _ in range(count):
            torrent_checker.mds.TorrentState(infohash=secrets.token_bytes(20),
                                             seeders=random.randint(1, 100),
                                             leechers=random.randint(1, 100),
                                             last_check=last_checked,
                                             self_checked=self_checked)

    now = int(time.time())
    freshness_threshold = now - torrent_checker_module.HEALTH_FRESHNESS_SECONDS
    before_threshold = freshness_threshold - 100  # considered not-fresh
    after_threshold = freshness_threshold + 100  # considered fresh

    # Case 1: Save random 10 non-self checked torrents
    # Expected: empty set, since only self checked torrents are considered.
    save_random_torrent_state(last_checked=now, self_checked=False, count=10)
    assert not torrent_checker.torrents_checked

    # Case 2: Save 10 self checked torrent but not within the freshness period
    # Expected: empty set, since only self checked fresh torrents are considered.
    save_random_torrent_state(last_checked=before_threshold, self_checked=True, count=10)
    assert not torrent_checker.torrents_checked

    # Case 3: Save 10 self checked fresh torrents
    # Expected: 10 torrents, since there are 10 self checked and fresh torrents
    save_random_torrent_state(last_checked=after_threshold, self_checked=True, count=10)
    assert len(torrent_checker.torrents_checked) == 10

    # Case 4: Save some more self checked fresh torrents
    # Expected: 10 torrents, since torrent_checked set should already be initialized above.
    save_random_torrent_state(last_checked=after_threshold, self_checked=True, count=10)
    assert len(torrent_checker.torrents_checked) == 10

    # Case 5: Clear the torrent_checked set (private variable),
    # and save freshly self checked torrents more than max return size (10 more).
    # Expected: max (return size) torrents, since limit is placed on how many to load.
    torrent_checker._torrents_checked = dict()  # pylint: disable=protected-access
    return_size = torrent_checker_module.TORRENTS_CHECKED_RETURN_SIZE
    save_random_torrent_state(last_checked=after_threshold, self_checked=True, count=return_size + 10)
    assert len(torrent_checker.torrents_checked) == return_size


@pytest.mark.asyncio
async def test_task_select_no_tracker(torrent_checker):
    """
    Test whether we are not checking a random tracker if there are no trackers in the database.
    """
    result = await torrent_checker.check_random_tracker()
    assert not result


@pytest.mark.asyncio
async def test_check_random_tracker_shutdown(torrent_checker):
    """
    Test whether we are not performing a tracker check if we are shutting down.
    """
    await torrent_checker.shutdown()
    result = await torrent_checker.check_random_tracker()
    assert not result


@pytest.mark.asyncio
async def test_check_random_tracker_not_alive(torrent_checker):
    """
    Test whether we correctly update the tracker state when the number of failures is too large.
    """
    with db_session:
        torrent_checker.mds.TrackerState(url="http://localhost/tracker", failures=1000, alive=True)

    result = await torrent_checker.check_random_tracker()
    assert not result

    with db_session:
        tracker = torrent_checker.tracker_manager.tracker_store.get()
        assert not tracker.alive


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_tracker_test_error_resolve(torrent_checker):
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
    assert len(torrent_checker._session_list) == 1


@pytest.mark.asyncio
async def test_tracker_no_infohashes(torrent_checker):
    """
    Test the check of a tracker without associated torrents
    """
    torrent_checker.tracker_manager.add_tracker('http://trackertest.com:80/announce')
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


def test_on_health_check_completed(torrent_checker):
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
        ts = torrent_checker.mds.TorrentState(infohash=infohash_bin)
        previous_check = ts.last_check
        torrent_checker.on_torrent_health_check_completed(infohash_bin, result)
        assert 1 == len(torrent_checker.torrents_checked)
        assert result[2]['DHT'][0]['leechers'] == ts.leechers
        assert result[2]['DHT'][0]['seeders'] == ts.seeders
        assert previous_check < ts.last_check


def test_on_health_check_failed(torrent_checker):
    """
    Check whether there is no crash when the torrent health check failed and the response is None
    No torrent info is added to torrent_checked list.
    """
    infohash_bin = b'\xee' * 20
    torrent_checker.on_torrent_health_check_completed(infohash_bin, [None])
    assert 0 == len(torrent_checker.torrents_checked)


@db_session
def test_check_local_torrents(torrent_checker):
    """
    Test that the random torrent health checking mechanism picks the right torrents
    """

    def random_infohash():
        return os.urandom(20)

    num_torrents = 20
    torrent_checker.check_torrent_health = lambda _: succeed(None)

    # No torrents yet, the selected torrents should be empty
    selected_torrents = torrent_checker.check_local_torrents()
    assert len(selected_torrents) == 0

    # Add some freshly checked torrents
    time_fresh = time.time()
    fresh_infohashes = []
    for index in range(0, num_torrents):
        infohash = random_infohash()
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
        torrent = torrent_checker.mds.TorrentMetadata(title=f'torrent{index}', infohash=infohash)
        torrent.health.seeders = max_seeder - index     # Note: decreasing trend
        torrent.health.last_check = int(time_stale) - index  # Note: decreasing trend
        stale_infohashes.append(infohash)

    # Now check that all torrents selected for check are stale torrents.
    selected_torrents = torrent_checker.check_local_torrents()
    assert len(selected_torrents) <= torrent_checker_module.TORRENT_SELECTION_POOL_SIZE

    # In the above setup, both seeder (popularity) count and last_check are decreasing so,
    # 1. Popular torrents are in the front, and
    # 2. Older torrents are towards the back
    # Therefore the selection range becomes:
    selection_range = stale_infohashes[0: torrent_checker_module.TORRENT_SELECTION_POOL_SIZE] \
        + stale_infohashes[- torrent_checker_module.TORRENT_SELECTION_POOL_SIZE:]

    for infohash in selected_torrents:
        assert infohash in selection_range


@db_session
def test_check_channel_torrents(torrent_checker):
    """
    Test that the channel torrents are checked based on last checked time.
    Only outdated torrents are selected for health checks.
    """

    def random_infohash():
        return os.urandom(20)

    def add_torrent_to_channel(infohash, last_check):
        torrent = torrent_checker.mds.TorrentMetadata(public_key=torrent_checker.mds.my_public_key_bin,
                                                      infohash=infohash)
        torrent.health.last_check = last_check
        return torrent

    check_torrent_health_mock = Mock(return_value=None)
    torrent_checker.check_torrent_health = lambda _: check_torrent_health_mock()

    # No torrents yet in channel, the selected channel torrents to check should be empty
    selected_torrents = torrent_checker.torrents_to_check_in_user_channel()
    assert len(selected_torrents) == 0

    # No health check call are done
    torrent_checker.check_torrents_in_user_channel()
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
        outdated_torrents.append(torrent)

    # Now check that only outdated torrents are selected for check
    selected_torrents = torrent_checker.torrents_to_check_in_user_channel()
    assert len(selected_torrents) <= torrent_checker_module.USER_CHANNEL_TORRENT_SELECTION_POOL_SIZE
    for torrent in selected_torrents:
        assert torrent in outdated_torrents

    # Health check requests are sent for all selected torrents
    torrent_checker.check_torrents_in_user_channel()
    assert check_torrent_health_mock.call_count == len(selected_torrents)
