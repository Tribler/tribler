import logging
import os

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.OrmBindings import metadata, torrent_metadata, channel_metadata
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import BLOB_EXTENSION
from Tribler.Core.Modules.MetadataStore.serialization import read_payload_with_offset, REGULAR_TORRENT, \
    CHANNEL_TORRENT, DELETED
# This table should never be used from ORM directly.
# It is created as a VIRTUAL table by raw SQL and
# maintained by SQL triggers.
from Tribler.Core.exceptions import InvalidSignatureException
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer

sql_create_fts_table = """
    CREATE VIRTUAL TABLE IF NOT EXISTS FtsIndex USING FTS5
        (title, tags, content='Metadata',
         tokenize='porter unicode61 remove_diacritics 1');"""

sql_add_fts_trigger_insert = """
    CREATE TRIGGER IF NOT EXISTS fts_ai AFTER INSERT ON Metadata
    BEGIN
        INSERT INTO FtsIndex(rowid, title, tags) VALUES
            (new.rowid, new.title, new.tags);
    END;"""

sql_add_fts_trigger_delete = """
    CREATE TRIGGER IF NOT EXISTS fts_ad AFTER DELETE ON Metadata
    BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
    END;"""

sql_add_fts_trigger_update = """
    CREATE TRIGGER IF NOT EXISTS fts_au AFTER UPDATE ON Metadata BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
        INSERT INTO FtsIndex(rowid, title, tags) VALUES (new.rowid, new.title,
      new.tags);
    END;"""

sql_add_signature_index = "CREATE INDEX SignatureIndex ON Metadata(signature);"
sql_add_public_key_index = "CREATE INDEX PublicKeyIndex ON Metadata(public_key);"
sql_add_infohash_index = "CREATE INDEX InfohashIndex ON Metadata(infohash);"


class BadChunkException(Exception):
    pass


class MetadataStore(object):
    def __init__(self, db_filename, channels_dir, my_key):
        self.db_filename = db_filename
        self.channels_dir = channels_dir
        self.serializer = Serializer()
        self.my_key = my_key
        self._logger = logging.getLogger(self.__class__.__name__)

        create_db = (db_filename == ":memory:" or not os.path.isfile(self.db_filename))

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self._db = orm.Database()

        # Accessors for ORM-managed classes
        self.Metadata = metadata.define_binding(self._db)
        self.TorrentMetadata = torrent_metadata.define_binding(self._db)
        self.ChannelMetadata = channel_metadata.define_binding(self._db)

        self.Metadata._my_key = my_key
        self.ChannelMetadata._channels_dir = channels_dir
        self.Metadata._logger = self._logger  # Use Store-level logger for every ORM-based class

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
                self._db.execute(sql_add_signature_index)
                self._db.execute(sql_add_public_key_index)

    def shutdown(self):
        self._db.disconnect()

    def process_channel_dir(self, dirname, channel_id):
        """
        Load all metadata blobs in a given directory.
        :param dirname: The directory containing the metadata blobs.
        :param channel_id: public_key of the channel.
        """

        with db_session:
            channel = self.ChannelMetadata.get(public_key=channel_id)
            self._logger.debug("Starting processing channel dir %s. Channel %s local/max version %i/%i",
                               dirname, str(channel.public_key).encode("hex"), channel.local_version, channel.version)
            for filename in sorted(os.listdir(dirname)):
                full_filename = os.path.join(dirname, filename)
                if filename.endswith(BLOB_EXTENSION):
                    blob_sequence_number = int(filename[:-len(BLOB_EXTENSION)])
                    # Skip blobs containing data we already have and those that are
                    # ahead of the channel version known to us
                    if blob_sequence_number <= channel.local_version or blob_sequence_number > channel.version:
                        continue
                    try:
                        self.process_mdblob_file(full_filename)
                        # We track the local version of the channel while reading blobs
                        channel.local_version = blob_sequence_number
                    except InvalidSignatureException:
                        self._logger.error("Not processing metadata located at %s: invalid signature", full_filename)
            self._logger.debug("Finished processing channel dir %s. Channel %s local/max version %i/%i",
                               dirname, str(channel.public_key).encode("hex"), channel.local_version, channel.version)

    @db_session
    def process_mdblob_file(self, filepath):
        """
        Process a file with metadata in a channel directory.
        :param filepath: The path to the file
        :return a Metadata object if we can correctly load the metadata
        """
        with open(filepath, 'rb') as f:
            serialized_data = f.read()
        return self.process_squashed_mdblob(serialized_data)

    @db_session
    def process_squashed_mdblob(self, chunk_data):
        metadata_list = []
        offset = 0
        while offset < len(chunk_data):
            payload, offset = read_payload_with_offset(chunk_data, offset)
            md = self.process_payload(payload)
            if md:
                metadata_list.append(md)
        return metadata_list

    # Can't use db_session wrapper here, performance drops 10 times! Pony bug!
    def process_payload(self, payload):
        with db_session:
            if self.Metadata.exists(signature=payload.signature):
                return self.Metadata.get(signature=payload.signature)

            if payload.metadata_type == DELETED:
                # We only allow people to delete their own entries, thus PKs must match
                existing_metadata = self.Metadata.get(signature=payload.delete_signature, public_key=payload.public_key)
                if existing_metadata:
                    existing_metadata.delete()
                return None
            elif payload.metadata_type == REGULAR_TORRENT:
                return self.TorrentMetadata.from_payload(payload)
            elif payload.metadata_type == CHANNEL_TORRENT:
                return self.ChannelMetadata.from_payload(payload)

    @db_session
    def get_my_channel(self):
        return self.ChannelMetadata.get_channel_with_id(self.my_key.pub().key_to_bin())
