from pony import orm

from Tribler.pyipv8.ipv8.database import database_blob


def define_binding(db):
    class Author(db.Entity):
        public_key = orm.PrimaryKey(database_blob)
        authored = orm.Set('ChannelNode')

    return Author
