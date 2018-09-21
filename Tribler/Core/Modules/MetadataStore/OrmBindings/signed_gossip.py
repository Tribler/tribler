from datetime import datetime

from pony import orm

from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes, serialize_metadata_gossip


def define_binding(db):
    class SignedGossip(db.Entity):
        rowid = orm.PrimaryKey(int, auto=True)
        type = orm.Discriminator(int)
        _discriminator_ = MetadataTypes.TYPELESS.value
        signature = orm.Optional(buffer)
        timestamp = orm.Optional(datetime, default=datetime.utcnow)
        tc_pointer = orm.Optional(int, size=64, default=0)
        public_key = orm.Optional(buffer)
        addition_timestamp = orm.Optional(datetime, default=datetime.utcnow)

        def serialized(self, check_signature=False):
            md = self.to_dict()
            return serialize_metadata_gossip(md, check_signature=check_signature)

        def to_file(self, filename):
            with open(filename, 'w') as f:
                f.write(self.serialized())

        def sign(self, key):
            md_dict = self.to_dict()
            serialize_metadata_gossip(md_dict, key)
            self.signature = md_dict["signature"]
            self.public_key = buffer(key.pub().key_to_bin())

        @classmethod
        def from_dict(cls, key, md_dict):
            md = cls(**md_dict)
            md.sign(key)
            return md

    return SignedGossip
