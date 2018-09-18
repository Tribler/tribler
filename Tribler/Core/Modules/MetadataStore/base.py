from datetime import datetime
from pony import orm
from pony.orm import db_session
from Tribler.Core.Modules.MetadataStore.serialization import serialize_metadata_gossip, MetadataTypes
from Tribler.Core.Modules.MetadataStore.torrents import define_torrent_md
from Tribler.Core.Modules.MetadataStore.channels import define_channel_md

METADATA_DB_RELATIVE_PATH = "chant.db"


def define_signed_gossip(db):
    class SignedGossip(db.Entity):
        rowid = orm.PrimaryKey(int, auto=True)
        type = orm.Discriminator(int)
        _discriminator_ = MetadataTypes.TYPELESS.value
        signature = orm.Optional(buffer)
        timestamp = orm.Optional(datetime, default=datetime.utcnow)
        tc_pointer = orm.Optional(int, size=64, default=0)
        public_key = orm.Optional(buffer)
        addition_timestamp = orm.Optional(datetime, default=datetime.utcnow)

        def serialized(self, check_signature = False):
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


def define_deleted_md(db):
    class DeletedMD(db.SignedGossip):
        _discriminator_ = MetadataTypes.DELETED.value
        delete_signature = orm.Required(buffer)


def start_orm(db_filename, create_db=False):
    # We have to dynamically define/init ORM-managed entities here to be able to support
    # multiple sessions in Tribler. Each session has its own db member object which
    # has it's own instances of ORM-managed classes.
    db = orm.Database()

    define_signed_gossip(db)
    define_deleted_md(db)
    define_torrent_md(db)
    define_channel_md(db)

    db.bind(provider='sqlite', filename=db_filename, create_db=create_db)
    if create_db:
        with db_session:
            db.execute(sql_create_fts_table)
    db.generate_mapping(create_tables=create_db)
    if create_db:
        with db_session:
            db.execute(sql_add_fts_trigger_insert)
            db.execute(sql_add_fts_trigger_delete)
            db.execute(sql_add_fts_trigger_update)
    return db


# This table should never be used from ORM directly.
# It is created as a VIRTUAL table by raw SQL and
# maintained by SQL triggers.
sql_create_fts_table = """
    CREATE VIRTUAL TABLE FtsIndex USING FTS5
        (title, tags, content='SignedGossip',
         tokenize='porter unicode61 remove_diacritics 1');"""

sql_add_fts_trigger_insert = """
    CREATE TRIGGER fts_ai AFTER INSERT ON SignedGossip
    BEGIN
        INSERT INTO FtsIndex(rowid, title, tags) VALUES
            (new.rowid, new.title, new.tags);
    END;"""

sql_add_fts_trigger_delete = """
    CREATE TRIGGER fts_ad AFTER DELETE ON SignedGossip
    BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
    END;"""

sql_add_fts_trigger_update = """
    CREATE TRIGGER fts_au AFTER UPDATE ON SignedGossip BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
        INSERT INTO FtsIndex(rowid, title, tags) VALUES (new.rowid, new.title,
      new.tags);
    END;"""
