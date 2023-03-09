import time
from unittest.mock import Mock

import pytest

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HEALTH_FRESHNESS_SECONDS, HealthInfo, \
    TOLERABLE_TIME_DRIFT, \
    TORRENT_CHECK_WINDOW

INFOHASH = b'infohash_1'


def now() -> int:
    return int(time.time())


@pytest.fixture(name='torrent_state')
def torrent_state_fixture():
    return Mock(infohash=INFOHASH)


def test_different_infohashes(torrent_state: Mock):
    health = HealthInfo(infohash=b'infohash_2')
    with pytest.raises(ValueError, match='^An attempt to compare health for different infohashes$'):
        health.should_update(torrent_state)


def test_invalid_health(torrent_state: Mock):
    health = HealthInfo(INFOHASH, last_check=now() + TOLERABLE_TIME_DRIFT + 2)
    assert not health.is_valid()
    assert not health.should_update(torrent_state)


def test_self_checked_health_remote_torrent_state(torrent_state: Mock):
    torrent_state.self_checked = False
    health = HealthInfo(INFOHASH)
    assert health.should_update(torrent_state, self_checked=True)


def test_self_checked_health_torrent_state_outside_window(torrent_state: Mock):
    torrent_state.self_checked = True
    torrent_state.last_check = now() - TORRENT_CHECK_WINDOW - 1
    health = HealthInfo(INFOHASH)
    assert health.should_update(torrent_state, self_checked=True)


def test_self_checked_health_inside_window_more_seeders(torrent_state: Mock):
    now_ = now()
    torrent_state.self_checked = True
    torrent_state.last_check = now_ - TORRENT_CHECK_WINDOW + 2
    torrent_state.seeders_leechers_last_check = (1, 2, torrent_state.last_check)
    health = HealthInfo(INFOHASH, last_check=now_, seeders=2, leechers=1)
    assert health.seeders_leechers_last_check == (2, 1, now_)
    assert health.seeders_leechers_last_check > torrent_state.seeders_leechers_last_check
    assert health.should_update(torrent_state, self_checked=True)


def test_self_checked_health_inside_window_fewer_seeders(torrent_state: Mock):
    now_ = now()
    torrent_state.self_checked = True
    torrent_state.last_check = now_ - TORRENT_CHECK_WINDOW + 2
    torrent_state.seeders_leechers_last_check = (2, 1, torrent_state.last_check)
    health = HealthInfo(INFOHASH, last_check=now_, seeders=1, leechers=2)
    assert health.seeders_leechers_last_check == (1, 2, now_)
    assert health.seeders_leechers_last_check < torrent_state.seeders_leechers_last_check
    assert not health.should_update(torrent_state, self_checked=True)


def test_self_checked_torrent_state_fresh_enough(torrent_state: Mock):
    now_ = now()
    torrent_state.self_checked = True
    torrent_state.last_check = now_ - HEALTH_FRESHNESS_SECONDS + 2  # self-checked, fresh enough
    health = HealthInfo(INFOHASH, last_check=now_)
    assert not health.should_update(torrent_state)


def test_torrent_state_self_checked_long_ago(torrent_state: Mock):
    now_ = now()
    torrent_state.self_checked = True
    torrent_state.last_check = now_ - HEALTH_FRESHNESS_SECONDS - 2
    health = HealthInfo(INFOHASH, last_check=now_)
    assert health.should_update(torrent_state)

    # should work the same way if time is not recent
    big_time_offset = 1000000
    torrent_state.last_check -= big_time_offset
    health.last_check -= big_time_offset
    assert health.should_update(torrent_state)


def test_more_recent_more_seeders(torrent_state: Mock):
    t = now() - 100
    torrent_state.self_checked = False
    torrent_state.last_check = t
    torrent_state.seeders_leechers_last_check = (1, 2, t)

    health = HealthInfo(INFOHASH, last_check=t-1, seeders=2, leechers=1)
    assert abs(torrent_state.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert health.should_update(torrent_state)

    health.last_check = t+1
    assert abs(torrent_state.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert health.should_update(torrent_state)


def test_more_recent_fewer_seeders(torrent_state: Mock):
    t = now() - 100
    torrent_state.self_checked = False
    torrent_state.last_check = t
    torrent_state.seeders_leechers_last_check = (2, 1, t)

    health = HealthInfo(INFOHASH, last_check=t-1, seeders=1, leechers=2)
    assert abs(torrent_state.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert not health.should_update(torrent_state)

    health.last_check = t+1
    assert abs(torrent_state.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert not health.should_update(torrent_state)


def test_less_recent_more_seeders(torrent_state: Mock):
    t = now() - 100
    torrent_state.self_checked = False
    torrent_state.last_check = t

    health = HealthInfo(INFOHASH, last_check=t - TOLERABLE_TIME_DRIFT - 1, seeders=100)
    assert not health.should_update(torrent_state)
