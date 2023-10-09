from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List

import human_readable

from tribler.core.utilities.unicode import hexlify

MINUTE = 60
HOUR = MINUTE * 60
TOLERABLE_TIME_DRIFT = MINUTE  # When receiving health from another peer, how far the timestamp can be in the future?
TORRENT_CHECK_WINDOW = MINUTE  # When asking multiple trackers in parallel, we ignore this time difference in responses
HEALTH_FRESHNESS_SECONDS = 4 * HOUR  # Number of seconds before a torrent health is considered stale. Default: 4 hours


class Source(IntEnum):
    """ Source of the Torrent Health information.
    """
    UNKNOWN = 0
    DHT = 1
    TRACKER = 2
    POPULARITY_COMMUNITY = 3


@dataclass(order=True)
class HealthInfo:
    infohash: bytes = field(repr=False)
    seeders: int = 0
    leechers: int = 0
    last_check: int = field(default_factory=lambda: int(time.time()))
    self_checked: bool = False
    source: Source = Source.UNKNOWN
    tracker: str = ''

    def __repr__(self):
        infohash_repr = hexlify(self.infohash[:4])
        status = self._last_check_repr(self.last_check)
        if status == 'just checked' and self.self_checked:
            status = 'just self-checked'
        elif self.self_checked:
            status += ', self-checked'
        return f"{self.__class__.__name__}('{infohash_repr}', {self.seeders}/{self.leechers}, {status})"

    @staticmethod
    def _last_check_repr(last_check: int) -> str:
        if last_check < 0:
            return 'invalid time'

        if last_check == 0:
            return 'never checked'

        now = int(time.time())
        diff = now - last_check
        if diff == 0:
            return 'just checked'

        age = human_readable.time_delta(diff, use_months=False)
        return age + (' ago' if diff > 0 else ' in the future')

    @property
    def infohash_hex(self):
        return hexlify(self.infohash)

    def is_valid(self) -> bool:
        return self.seeders >= 0 and self.leechers >= 0 and self.last_check < int(time.time()) + TOLERABLE_TIME_DRIFT

    def old(self) -> bool:
        now = int(time.time())
        return self.last_check < now - HEALTH_FRESHNESS_SECONDS

    def older_than(self, other: HealthInfo) -> bool:
        return self.last_check < other.last_check - TORRENT_CHECK_WINDOW

    def much_older_than(self, other: HealthInfo) -> bool:
        return self.last_check + HEALTH_FRESHNESS_SECONDS < other.last_check

    def should_replace(self, prev: HealthInfo) -> bool:
        if self.infohash != prev.infohash:
            raise ValueError('An attempt to compare health for different infohashes')

        if not self.is_valid():
            return False  # Health info with future last_check time is ignored

        if self.self_checked:
            return not prev.self_checked \
                or prev.older_than(self) \
                or (self.seeders, self.leechers) > (prev.seeders, prev.leechers)

        if self.older_than(prev):
            # Always ignore a new health info if it is older than the previous health info
            return False

        if prev.self_checked and not prev.old():
            # The previous self-checked health info is fresh enough, do not replace it with a remote health info
            return False

        if prev.much_older_than(self):
            # The previous health info (that can be self-checked ot not) is very old,
            # let's replace it with a more recent remote health info
            return True

        # self is a remote health info that isn't older than previous health info, but isn't much fresher as well
        return (self.seeders, self.leechers) > (prev.seeders, prev.leechers)


@dataclass
class TrackerResponse:
    url: str
    torrent_health_list: List[HealthInfo]
