import time

import pytest

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HEALTH_FRESHNESS_SECONDS, HealthInfo, \
    TOLERABLE_TIME_DRIFT, \
    TORRENT_CHECK_WINDOW

INFOHASH = b'infohash_1'


def now() -> int:
    return int(time.time())


def test_different_infohashes():
    prev_health = HealthInfo(INFOHASH)
    health = HealthInfo(infohash=b'infohash_2')
    with pytest.raises(ValueError, match='^An attempt to compare health for different infohashes$'):
        health.should_replace(prev_health)


def test_invalid_health():
    prev_health = HealthInfo(INFOHASH)
    health = HealthInfo(INFOHASH, last_check=now() + TOLERABLE_TIME_DRIFT + 2)
    assert not health.is_valid()
    assert not health.should_replace(prev_health)


def test_health_negative_seeders_or_leechers():
    """ Test that health with negative seeders or leechers is considered invalid"""
    assert not HealthInfo(INFOHASH, seeders=-1).is_valid()
    assert not HealthInfo(INFOHASH, leechers=-1).is_valid()


def test_self_checked_health_update_remote_health():
    prev_health = HealthInfo(INFOHASH)
    health = HealthInfo(INFOHASH, self_checked=True)
    assert health.should_replace(prev_health)


def test_self_checked_health_torrent_state_outside_window():
    prev_health = HealthInfo(INFOHASH, last_check=now() - TORRENT_CHECK_WINDOW - 1, self_checked=True)
    health = HealthInfo(INFOHASH, self_checked=True)
    assert health.should_replace(prev_health)


def test_self_checked_health_inside_window_more_seeders():
    prev_health = HealthInfo(INFOHASH, 1, 2, last_check=now() - TORRENT_CHECK_WINDOW + 2, self_checked=True)
    health = HealthInfo(INFOHASH, 2, 1, self_checked=True)
    assert health > prev_health
    assert health.should_replace(prev_health)


def test_self_checked_health_inside_window_fewer_seeders():
    prev_health = HealthInfo(INFOHASH, 2, 1, last_check=now() - TORRENT_CHECK_WINDOW + 2, self_checked=True)
    health = HealthInfo(INFOHASH, 1, 2, self_checked=True)
    assert health < prev_health
    assert not health.should_replace(prev_health)


def test_self_checked_torrent_state_fresh_enough():
    prev_health = HealthInfo(INFOHASH, last_check=now() - HEALTH_FRESHNESS_SECONDS + 2, self_checked=True)
    health = HealthInfo(INFOHASH)
    assert not health.should_replace(prev_health)


def test_torrent_state_self_checked_long_ago():
    prev_health = HealthInfo(INFOHASH, last_check=now() - HEALTH_FRESHNESS_SECONDS - 2, self_checked=True)
    health = HealthInfo(INFOHASH)
    assert health.should_replace(prev_health)

    # should work the same way if time is not recent
    big_time_offset = 1000000
    prev_health.last_check -= big_time_offset
    health.last_check -= big_time_offset
    assert health.should_replace(prev_health)


def test_more_recent_more_seeders():
    t = now() - 100
    prev_health = HealthInfo(INFOHASH, 1, 2, last_check=t)

    health = HealthInfo(INFOHASH, 2, 1, last_check=t - 1)
    assert abs(prev_health.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert health.should_replace(prev_health)

    health.last_check = t + 1
    assert abs(prev_health.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert health.should_replace(prev_health)


def test_more_recent_fewer_seeders():
    t = now() - 100
    prev_health = HealthInfo(INFOHASH, 2, 1, last_check=t)

    health = HealthInfo(INFOHASH, last_check=t - 1, seeders=1, leechers=2)
    assert abs(prev_health.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert not health.should_replace(prev_health)

    health.last_check = t + 1
    assert abs(prev_health.last_check - health.last_check) <= TOLERABLE_TIME_DRIFT
    assert not health.should_replace(prev_health)


def test_less_recent_more_seeders():
    t = now() - 100
    prev_health = HealthInfo(INFOHASH, last_check=t)
    health = HealthInfo(INFOHASH, 100, last_check=t - TOLERABLE_TIME_DRIFT - 1)
    assert not health.should_replace(prev_health)
