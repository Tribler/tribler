from __future__ import absolute_import

from ipv8.database import database_blob

from pony import orm


def define_binding(db):
    class TorrentState(db.Entity):
        rowid = orm.PrimaryKey(int, auto=True)
        infohash = orm.Required(database_blob, unique=True)
        seeders = orm.Optional(int, default=0)
        leechers = orm.Optional(int, default=0)
        last_check = orm.Optional(int, size=64, default=0)
        metadata = orm.Set('TorrentMetadata', reverse='health')
        trackers = orm.Set('TrackerState', reverse='torrents')

    return TorrentState
