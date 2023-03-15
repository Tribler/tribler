from __future__ import annotations

from pony import orm

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo


def define_binding(db):
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
        def from_health(cls, health: HealthInfo):
            return cls(infohash=health.infohash, seeders=health.seeders, leechers=health.leechers,
                       last_check=health.last_check, self_checked=health.self_checked)

        def to_health(self) -> HealthInfo:
            return HealthInfo(self.infohash, self.seeders, self.leechers, self.last_check, self.self_checked)

    return TorrentState
