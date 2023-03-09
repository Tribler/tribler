import time
from unittest.mock import Mock

import pytest

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HEALTH_FRESHNESS_SECONDS, HealthInfo, \
    TOLERABLE_TIME_DRIFT, \
    TORRENT_CHECK_WINDOW

INFOHASH = b'infohash_1'


def now() -> int:
    return int(time.time())


def mock_torrent_state(self_checked=False, seeders=0, leechers=0, last_check=None) -> Mock:
    result = Mock(infohash=INFOHASH, self_checked=self_checked, seeders=seeders, leechers=leechers,
                  last_check=now() if last_check is None else last_check)
    result.to_health.return_value = HealthInfo(INFOHASH, seeders, leechers, last_check)
    return result


def test_different_infohashes():
    torrent_state = mock_torrent_state()
    health = HealthInfo(infohash=b'infohash_2')
    with pytest.raises(ValueError, match='^An attempt to compare health for different infohashes$'):
        health.should_update(torrent_state)


def test_invalid_health():
    torrent_state = mock_torrent_state()
    health = HealthInfo(INFOHASH, last_check=now() + TOLERABLE_TIME_DRIFT + 2)
    assert not health.is_valid()
    assert not health.should_update(torrent_state)


def test_self_checked_health_remote_torrent_state():
    torrent_state = mock_torrent_state(self_checked=False)
    health = HealthInfo(INFOHASH)
    assert health.should_update(torrent_state, self_checked=True)


def test_self_checked_health_torrent_state_outside_window():
    torrent_state = mock_torrent_state(self_checked=True, last_check=now() - TORRENT_CHECK_WINDOW - 1)
    health = HealthInfo(INFOHASH)
    assert health.should_update(torrent_state, self_checked=True)


def test_self_checked_health_inside_window_more_seeders():
    now_ = now()
    torrent_state = mock_torrent_state(self_checked=True, seeders=1, leechers=2,
                                       last_check=now_ - TORRENT_CHECK_WINDOW + 2)
    health = HealthInfo(INFOHASH, last_check=now_, seeders=2, leechers=1)
    assert health > torrent_state.to_health()
    assert health.should_update(torrent_state, self_checked=True)


def test_self_checked_health_inside_window_fewer_seeders():
    now_ = now()
    torrent_state = mock_torrent_state(self_checked=True, seeders=2, leechers=1,
                                       last_check=now_ - TORRENT_CHECK_WINDOW + 2)
    health = HealthInfo(INFOHASH, last_check=now_, seeders=1, leechers=2)
    assert health < torrent_state.to_health()
    assert not health.should_update(torrent_state, self_checked=True)


def test_self_checked_torrent_state_fresh_enough():
    now_ = now()
    torrent_state = mock_torrent_state(self_checked=True, last_check=now_ - HEALTH_FRESHNESS_SECONDS + 2)
    health = HealthInfo(INFOHASH, last_check=now_)
    assert not health.should_update(torrent_state)


def test_torrent_state_self_checked_long_ago():
    now_ = now()
    torrent_state = mock_torrent_state(self_checked=True, last_check=now_ - HEALTH_FRESHNESS_SECONDS - 2)
    health = HealthInfo(INFOHASH, last_check=now_)
    assert health.should_update(torrent_state)

    # should work the same way if time is not recent
    big_time_offset = 1000000
    torrent_state.last_check -= big_time_offset
    health.last_check -= big_time_offset
    assert health.should_update(torrent_state)


def test_more_recent_more_seeders():
    t = now() - 100
    torrent_state = mock_torrent_state(self_checked=False, seeders=1, leechers=2, last_check=t)

    health = HealthInfo(INFOHASH, last_check=t-1, seeders=2, leechers=1)
    assert abs(torrent_state.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert health.should_update(torrent_state)

    health.last_check = t+1
    assert abs(torrent_state.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert health.should_update(torrent_state)


def test_more_recent_fewer_seeders():
    t = now() - 100
    torrent_state = mock_torrent_state(self_checked=False, seeders=2, leechers=1, last_check=t)

    health = HealthInfo(INFOHASH, last_check=t-1, seeders=1, leechers=2)
    assert abs(torrent_state.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert not health.should_update(torrent_state)

    health.last_check = t+1
    assert abs(torrent_state.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert not health.should_update(torrent_state)


def test_less_recent_more_seeders():
    t = now() - 100
    torrent_state = mock_torrent_state(self_checked=False, last_check=t)
    health = HealthInfo(INFOHASH, last_check=t - TOLERABLE_TIME_DRIFT - 1, seeders=100)
    assert not health.should_update(torrent_state)
