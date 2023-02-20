import time
from dataclasses import dataclass, field
from typing import List

import human_readable

from tribler.core.utilities.unicode import hexlify


TOLERABLE_TIME_DRIFT = 60  # one minute
HOUR = 60 * 60


@dataclass
class HealthInfo:
    infohash: bytes = field(repr=False)
    last_check: int
    seeders: int = 0
    leechers: int = 0

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

    def should_update(self, torrent_state, self_checked=False):
        if self.last_check <= torrent_state.last_check:
            # The torrent state in the DB is already fresher than this health
            return False

        now = int(time.time())
        hour_ago = now - HOUR
        if not self_checked and torrent_state.self_checked and hour_ago <= torrent_state.last_check <= now:
            # The torrent state in the DB was locally checked just recently,
            # and we trust this recent local check more than the new health info received remotely
            return False

        return True

@dataclass
class TrackerResponse:
    url: str
    torrent_health_list: List[HealthInfo]
