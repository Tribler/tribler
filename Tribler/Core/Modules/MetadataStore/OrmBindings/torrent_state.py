from datetime import datetime

from pony import orm

from Tribler.pyipv8.ipv8.database import database_blob


def define_binding(db):
    class TorrentState(db.Entity):
        infohash = orm.PrimaryKey(database_blob)
        seeders = orm.Optional(int, default=0)
        leechers = orm.Optional(int, default=0)
        last_check = orm.Optional(datetime, default=datetime.utcnow)
        metadata = orm.Set('TorrentMetadata')

    return TorrentState
