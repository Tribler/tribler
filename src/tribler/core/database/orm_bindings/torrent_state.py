from __future__ import annotations

from typing import TYPE_CHECKING

from pony import orm
from typing_extensions import Self

from tribler.core.torrent_checker.dataclasses import HealthInfo

if TYPE_CHECKING:
    from dataclasses import dataclass

    from pony.orm import Database

    from tribler.core.database.orm_bindings.torrent_metadata import TorrentMetadata
    from tribler.core.database.orm_bindings.tracker_state import TrackerState


    @dataclass
    class TorrentState:
        """
        Database type for the state of a torrent.
        """

        rowid: int
        infohash: bytes
        seeders: int | None
        leechers: int | None
        last_check: int | None
        self_checked: bool | None
        has_data: bool
        metadata: set[TorrentMetadata]
        trackers: set[TrackerState]


        def __init__(self, infohash: bytes) -> None: ...  # noqa: D107

        @staticmethod
        def get(infohash: bytes) -> TorrentState | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(infohash: bytes) -> TorrentState | None: ...  # noqa: D102


def define_binding(db: Database) -> type[TorrentState]:
    """
    Define the tracker state binding.
    """

    class TorrentState(db.Entity):
        """
        This ORM class represents torrent swarms. It is used by HealthChecker.
        """

        rowid = orm.PrimaryKey(int, auto=True)
        infohash = orm.Required(bytes, unique=True)
        seeders = orm.Optional(int, default=0)
        leechers = orm.Optional(int, default=0)
        last_check = orm.Optional(int, size=64, default=0)
        self_checked = orm.Optional(bool, default=False, sql_default='0')
        has_data = orm.Required(bool, default=False, sql_default='0', volatile=True)
        metadata = orm.Set('TorrentMetadata', reverse='health')
        trackers = orm.Set('TrackerState', reverse='torrents')

        @classmethod
        def from_health(cls: type[Self], health: HealthInfo) -> Self:
            return cls(infohash=health.infohash, seeders=health.seeders, leechers=health.leechers,
                       last_check=health.last_check, self_checked=health.self_checked)

        def to_health(self) -> HealthInfo:
            return HealthInfo(self.infohash, self.seeders, self.leechers, self.last_check, self.self_checked)

    return TorrentState
