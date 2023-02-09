from dataclasses import dataclass, field
from typing import List

from tribler.core.utilities.unicode import hexlify


@dataclass
class InfohashHealth:
    infohash: bytes = field(repr=False)
    infohash_hex: str = field(init=False)
    seeders: int = 0
    leechers: int = 0
    last_check: int = 0

    def __post_init__(self):
        self.infohash_hex = hexlify(self.infohash)


@dataclass
class TrackerResponse:
    url: str
    torrent_health_list: List[InfohashHealth]
