
from pony import orm
from datetime import datetime
from MDPackXDR import serialize_metadata_gossip

db = orm.Database()

class Peer(db.Entity):
    id               = orm.PrimaryKey(int, auto=True)
    public_key       = orm.Required(buffer)
    trusted          = orm.Optional(bool)
    votes            = orm.Optional(int)
    update_timestamp = orm.Required(datetime)

class MetadataGossip(db.Entity):
    id                 = orm.PrimaryKey(int, auto=True)
    sig                = orm.Required(buffer)
    type               = orm.Optional(int)
    infohash           = orm.Optional(buffer)
    title              = orm.Optional(str)
    size               = orm.Optional(int)
    timestamp          = orm.Optional(datetime)
    torrent_date       = orm.Optional(datetime)
    tc_pointer         = orm.Optional(int)
    public_key         = orm.Optional(buffer)
    tags               = orm.Optional(str)
    addition_timestamp = orm.Optional(datetime)
    # tags_parsed ????
    # terms ???
    
    def serialized(self):
        return serialize_metadata_gossip(self.to_dict())

def known_pk(pk):
    return Peer.get(public_key=pk)

def trusted_pk(pk):
    return Peer.get(public_key=pk).trusted

def known_sig(sig):
    return MetadataGossip.get(sig=sig)

db.bind(provider='sqlite', filename=':memory:')
db.generate_mapping(create_tables=True)
