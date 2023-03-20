import logging
import random
import secrets
import time
from binascii import unhexlify
from unittest.mock import MagicMock, Mock

import pytest
from pony.orm import db_session

import tribler.core.components.torrent_checker.torrent_checker.torrent_checker as torrent_checker_module
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo, TOLERABLE_TIME_DRIFT, \
    TrackerResponse
from tribler.core.components.torrent_checker.torrent_checker.db_service import DbService
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager
from tribler.core.components.torrent_checker.torrent_checker.utils import aggregate_responses_for_infohash


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


@pytest.fixture(name="db_service")
async def db_service_fixture(tribler_config, tracker_manager, metadata_store):
    db_service = DbService(download_manager=MagicMock(),
                           notifier=MagicMock(),
                           metadata_store=metadata_store,
                           tracker_manager=tracker_manager)
    yield db_service


def test_load_torrents_check_from_db(db_service):  # pylint: disable=unused-argument
    """
    Test if the torrents_checked set is properly initialized based on the last_check
    and self_checked values from the database.
    """

    @db_session
    def save_random_torrent_state(last_checked=0, self_checked=False, count=1):
        for _ in range(count):
            db_service.mds.TorrentState(infohash=secrets.token_bytes(20),
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
    db_service._torrents_checked = None  # pylint: disable=protected-access
    assert not db_service.torrents_checked

    # Case 2: Save 10 self checked torrent but not within the freshness period
    # Expected: empty set, since only self checked fresh torrents are considered.
    save_random_torrent_state(last_checked=before_threshold, self_checked=True, count=10)
    db_service._torrents_checked = None  # pylint: disable=protected-access
    assert not db_service.torrents_checked

    # Case 3: Save 10 self checked fresh torrents
    # Expected: 10 torrents, since there are 10 self checked and fresh torrents
    save_random_torrent_state(last_checked=after_threshold, self_checked=True, count=10)
    db_service._torrents_checked = None  # pylint: disable=protected-access
    assert len(db_service.torrents_checked) == 10

    # Case 4: Save some more self checked fresh torrents
    # Expected: 10 torrents, since torrent_checked set should already be initialized above.
    save_random_torrent_state(last_checked=after_threshold, self_checked=True, count=10)
    assert len(db_service.torrents_checked) == 10

    # Case 5: Clear the torrent_checked set (private variable),
    # and save freshly self checked torrents more than max return size (10 more).
    # Expected: max (return size) torrents, since limit is placed on how many to load.
    db_service._torrents_checked = None  # pylint: disable=protected-access
    return_size = torrent_checker_module.TORRENTS_CHECKED_RETURN_SIZE
    save_random_torrent_state(last_checked=after_threshold, self_checked=True, count=return_size + 10)
    assert len(db_service.torrents_checked) == return_size


def test_get_valid_next_tracker_for_auto_check(db_service):
    """
    Test if only valid tracker url are used for auto check
    """
    mock_tracker_state_invalid = MagicMock(
        url="http://anno nce.torrentsmd.com:8080/announce",
        failures=0
    )
    mock_tracker_state_valid = MagicMock(
        url="http://announce.torrentsmd.com:8080/announce",
        failures=0
    )
    tracker_states = [mock_tracker_state_invalid, mock_tracker_state_valid]

    def get_next_tracker_for_auto_check():
        return tracker_states[0] if tracker_states else None

    def remove_tracker(_):
        tracker_states.remove(mock_tracker_state_invalid)

    db_service.tracker_manager.get_next_tracker = get_next_tracker_for_auto_check
    db_service.tracker_manager.remove_tracker = remove_tracker
    next_tracker = db_service.get_next_tracker()
    assert len(tracker_states) == 1
    assert next_tracker.url == "http://announce.torrentsmd.com:8080/announce"


def test_update_health(db_service: DbService):
    infohash = b'\xee' * 20

    now = int(time.time())
    responses = [
        TrackerResponse(
            url='udp://localhost:2801',
            torrent_health_list=[HealthInfo(infohash, last_check=now, leechers=1, seeders=2)]
        ),
        TrackerResponse(
            url='DHT',
            torrent_health_list=[HealthInfo(infohash, last_check=now, leechers=12, seeders=13)]
        ),
    ]

    health = aggregate_responses_for_infohash(infohash, responses)
    health.self_checked = True

    # Check that everything works fine even if the database contains no proper infohash
    updated = db_service.update_torrent_health(health)
    assert not updated

    with db_session:
        ts = db_service.mds.TorrentState(infohash=infohash)
        updated = db_service.update_torrent_health(health)
        assert updated
        assert len(db_service.torrents_checked) == 1
        assert ts.leechers == 12
        assert ts.seeders == 13
        assert ts.last_check == now


def test_update_torrent_health_invalid_health(db_service: DbService, caplog):
    """
    Tests that invalid health is ignored in TorrentChecker.update_torrent_health()
    """
    caplog.set_level(logging.WARNING)
    now = int(time.time())
    health = HealthInfo(unhexlify('abcd0123'), last_check=now + TOLERABLE_TIME_DRIFT + 2)
    assert not db_service.update_torrent_health(health)
    assert "Invalid health info ignored: " in caplog.text


def test_update_torrent_health_not_self_checked(db_service: DbService, caplog):
    """
    Tests that non-self-checked health is ignored in TorrentChecker.update_torrent_health()
    """
    caplog.set_level(logging.ERROR)
    health = HealthInfo(unhexlify('abcd0123'))
    assert not db_service.update_torrent_health(health)
    assert "Self-checked torrent health expected" in caplog.text


def test_update_torrent_health_unknown_torrent(db_service: DbService, caplog):
    """
    Tests that unknown torrent's health is ignored in TorrentChecker.update_torrent_health()
    """
    caplog.set_level(logging.WARNING)
    health = HealthInfo(unhexlify('abcd0123'), 1, 2, self_checked=True)
    assert not db_service.update_torrent_health(health)
    assert "Unknown torrent: abcd0123" in caplog.text


async def test_update_torrent_health_no_replace(db_service: DbService, caplog):
    """
    Tests that the TorrentChecker.notify() method is called even if the new health does not replace the old health
    """
    now = int(time.time())
    db_service.notify = Mock()

    with db_session:
        torrent_state = db_service.mds.TorrentState(infohash=unhexlify('abcd0123'), seeders=2, leechers=1,
                                                         last_check=now, self_checked=True)
        prev_health = torrent_state.to_health()

    health = HealthInfo(unhexlify('abcd0123'), 1, 2, self_checked=True, last_check=now)
    assert not db_service.update_torrent_health(health)
    assert "Skip health update, the health in the database is fresher or have more seeders" in caplog.text
    db_service.notify.assert_called_with(prev_health)
