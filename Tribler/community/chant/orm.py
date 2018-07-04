from datetime import datetime
from pony import orm
from pony.orm import db_session
from Tribler.community.chant.MDPackXDR import serialize_metadata_gossip
import sqlite3

db = orm.Database()

sql_create_fts_table = """
    CREATE VIRTUAL TABLE FtsIndex USING FTS4
        (title, tags, content='metadatagossip', 
         tokenize='porter' 'unicode61');"""

sql_add_fts_insert_trigger="""
    CREATE TRIGGER fts_ai AFTER INSERT ON metadatagossip
    BEGIN
        INSERT INTO FtsIndex(rowid, title, tags) VALUES
            (new.rowid, new.title, new.tags);
    END;"""

sql_add_fts_delete_trigger="""
    CREATE TRIGGER fts_ad AFTER DELETE ON metadatagossip 
    BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
    END;"""

sql_add_fts_update_trigger="""
    CREATE TRIGGER fts_au AFTER UPDATE ON metadatagossip BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
        INSERT INTO FtsIndex(rowid, title, tags) VALUES (nem.rowid, new.title,
      new.tags);
    END;"""


class FtsIndex(db.Entity):
    rowid = orm.PrimaryKey(int, auto=True)
    title = orm.Optional(str)
    tags = orm.Optional(str)

class PeerORM(db.Entity):
    rowid = orm.PrimaryKey(int, auto=True)
    public_key = orm.Required(buffer)
    trusted = orm.Optional(bool)
    votes = orm.Optional(int)
    update_timestamp = orm.Required(datetime)


class MetadataGossip(db.Entity):
    rowid = orm.PrimaryKey(int, auto=True)
    type = orm.Required(int)
    signature = orm.Optional(buffer)
    infohash = orm.Optional(buffer)
    title = orm.Optional(str)
    size = orm.Optional(int)
    timestamp = orm.Optional(datetime)
    torrent_date = orm.Optional(datetime)
    tc_pointer = orm.Optional(int)
    public_key = orm.Optional(buffer)
    tags = orm.Optional(str)
    addition_timestamp = orm.Optional(datetime)
    version = orm.Optional(int)

    # visible            = orm.Optional(bool, default_sql=True)
    # delete_signature   = orm.Optional(buffer)
    # tags_parsed ????
    # terms ???

    def serialized(self):
        md = self.to_dict()
        return serialize_metadata_gossip(md)

    def sign(self, key):
        md = self.to_dict()
        serialize_metadata_gossip(md, key)
        self.signature = md["signature"]


def known_pk(pk):
    return PeerORM.get(public_key=pk)


def trusted_pk(pk):
    return PeerORM.get(public_key=pk).trusted


def known_signature(signature):
    return MetadataGossip.get(signature=signature)


def start_orm(db_filename, create_db=False):
    db.bind(provider='sqlite', filename=db_filename, create_db=create_db)

    if create_db:
        with db_session:
            db.execute(sql_create_fts_table)
    db.generate_mapping(create_tables=create_db)
    if create_db:
        with db_session:
            db.execute(sql_add_fts_insert_trigger)
            db.execute(sql_add_fts_update_trigger)
            db.execute(sql_add_fts_delete_trigger)

