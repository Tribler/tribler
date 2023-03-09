import time
from dataclasses import dataclass, field
from typing import List, Tuple

import human_readable

from tribler.core.utilities.unicode import hexlify


MINUTE = 60
HOUR = MINUTE * 60
TOLERABLE_TIME_DRIFT = MINUTE  # When receiving health from another peer, how far the timestamp can be in the future?
TORRENT_CHECK_WINDOW = MINUTE  # When asking multiple trackers in parallel, we ignore this time difference in responses
HEALTH_FRESHNESS_SECONDS = 4 * HOUR  # Number of seconds before a torrent health is considered stale. Default: 4 hours


@dataclass
class HealthInfo:
    infohash: bytes = field(repr=False)
    seeders: int = 0
    leechers: int = 0
    last_check: int = field(default_factory=lambda: int(time.time()))

    def __repr__(self):
        infohash_repr = hexlify(self.infohash[:4])
        age = self._last_check_repr(self.last_check)
        return f"{self.__class__.__name__}('{infohash_repr}', {self.seeders}/{self.leechers}, {age})"

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
        return self.last_check < int(time.time()) + TOLERABLE_TIME_DRIFT

    @property
    def seeders_leechers_last_check(self) -> Tuple[int, int, int]:
        return self.seeders, self.leechers, self.last_check

    def should_update(self, torrent_state, self_checked=False) -> bool:
        # Self is a new health info, torrent_state is a previously saved health info for the same infohash
        if self.infohash != torrent_state.infohash:
            raise ValueError('An attempt to compare health for different infohashes')

        if not self.is_valid():
            return False  # Health info with future last_check time is ignored

        now = int(time.time())
        if self_checked:
            if not torrent_state.self_checked:
                return True  # Always prefer self-checked info

            if torrent_state.last_check < now - TORRENT_CHECK_WINDOW:
                # The previous torrent's health info is too old, replace it with the new health info,
                # even if the new health info has fewer seeders
                return True

            if self.seeders_leechers_last_check > torrent_state.seeders_leechers_last_check:
                # The new health info is received almost immediately after the previous health info from another tracker
                # and have a bigger number of seeders/leechers, or at least is a bit more fresh
                return True

            # The previous health info is also self-checked, not too old, and has more seeders/leechers
            return False

        # The new health info is received from another peer and not self-checked

        if torrent_state.self_checked and torrent_state.last_check >= now - HEALTH_FRESHNESS_SECONDS:
            # The previous self-checked health is fresh enough, do not replace it with remote health info
            return False

        if torrent_state.last_check + HEALTH_FRESHNESS_SECONDS < self.last_check:
            # The new health info appears to be significantly more recent; let's use it disregarding
            # the number of seeders (Note: it is possible that the newly received health info was actually
            # checked earlier, but with incorrect OS time. To mitigate this, we can switch to a relative
            # time when sending health info over the wire (like, "this remote health check was performed
            # 1000 seconds ago"), then the correctness of the OS time will not matter anymore)
            return True

        if torrent_state.last_check - TOLERABLE_TIME_DRIFT <= self.last_check \
                and self.seeders_leechers_last_check > torrent_state.seeders_leechers_last_check:
            # The new remote health info is not (too) older than the previous one, and have more seeders/leechers
            return True

        # The new remote health info is older than the previous health info, or not much fresher and has fewer seeders
        return False

@dataclass
class TrackerResponse:
    url: str
    torrent_health_list: List[HealthInfo]
