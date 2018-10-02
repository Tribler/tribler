import os

from pony import orm
from pony.orm import db_session

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Modules.MetadataStore.OrmBindings import signed_gossip, deleted_md, torrent_md, channel_md
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_md import BLOB_EXTENSION
from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes, deserialize_metadata_gossip
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo

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



class UnknownBlobTypeException(Exception):
    pass


class MetadataStore(object):

    def __init__(self, db_filename, channels_dir):
        self.db_filename = db_filename
        self.channels_dir = channels_dir

        create_db = db_filename is ":memory:" or os.path.isfile(self.db_filename) is False

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self._db = orm.Database()

        # Accessors for ORM-managed classes
        self.SignedGossip = signed_gossip.define_binding(self._db)
        self.DeletedMD = deleted_md.define_binding(self._db)
        self.TorrentMD = torrent_md.define_binding(self._db)
        self.ChannelMD = channel_md.define_binding(self._db)

        self._db.bind(provider='sqlite', filename=db_filename, create_db=create_db)
        if create_db:
            with db_session:
                self._db.execute(sql_create_fts_table)
        self._db.generate_mapping(create_tables=create_db)  # Must be run out of session scope
        if create_db:
            with db_session:
                self._db.execute(sql_add_fts_trigger_insert)
                self._db.execute(sql_add_fts_trigger_delete)
                self._db.execute(sql_add_fts_trigger_update)

    def shutdown(self):
        self._db.disconnect()

    def process_channel_dir(self, dirname, start_num=0):
        for filename in sorted(os.listdir(dirname)):
            full_filename = os.path.join(dirname, filename)
            try:
                if filename.endswith(BLOB_EXTENSION):
                    num = int(filename[:-len(BLOB_EXTENSION)])
                    if num < 0:
                        raise NameError
                else:
                    raise NameError
            except (ValueError, NameError):
                raise NameError('Wrong blob filename in channel dir:', full_filename)
            if num >= start_num:
                self.load_blob(full_filename)

    def download_channel(self, session, infohash, title):
        dcfg = DownloadStartupConfig()
        dcfg.set_dest_dir(self.channels_dir)
        tdef = TorrentDefNoMetainfo(infohash=str(infohash), name=title)
        download = session.start_download_from_tdef(tdef, dcfg)

        download.deferred_finished.addCallback(
            lambda handle: self.process_channel_dir(handle.get_content_dest()))
        return download.deferred_finished

    @db_session
    def load_blob(self, filename):
        with open(filename, 'rb') as f:
            gsp = deserialize_metadata_gossip(f.read())
            if self.SignedGossip.exists(signature=gsp["signature"]):
                # We already have this gossip.
                return self.SignedGossip.get(signature=gsp["signature"])
            if gsp["type"] == MetadataTypes.DELETED.value:
                # We only allow people to delete their own entries, thus PKs must
                # match
                md = self.SignedGossip.get(
                    signature=gsp["delete_signature"],
                    public_key=gsp["public_key"])
                if md:
                    md.delete()
                return None
            elif gsp["type"] == MetadataTypes.REGULAR_TORRENT.value:
                return self.TorrentMD(**gsp)
            elif gsp["type"] == MetadataTypes.CHANNEL_TORRENT.value:
                return self.ChannelMD(**gsp)
            raise UnknownBlobTypeException
