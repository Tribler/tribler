from __future__ import absolute_import

from pony import orm

from Tribler.pyipv8.ipv8.database import database_blob


# This binding stores public keys of IPv8 peers that sent us some GigaChannel data
def define_binding(db):
    class ChannelPeer(db.Entity):
        rowid = orm.PrimaryKey(int, size=64, auto=True)
        public_key = orm.Required(database_blob, unique=True)
        votes = orm.Set('ChannelMetadata', reverse='votes')

    return ChannelPeer
