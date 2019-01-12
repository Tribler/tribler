from __future__ import absolute_import

import logging
import os

import lz4.frame
from pony import orm
from pony.orm import db_session

from Tribler.Core.Category.Category import Category
from Tribler.Core.Modules.MetadataStore.OrmBindings import metadata, torrent_metadata, channel_metadata, channel_node, \
    torrent_state, tracker_state
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import BLOB_EXTENSION
from Tribler.Core.Modules.MetadataStore.serialization import read_payload_with_offset, REGULAR_TORRENT, \
    CHANNEL_TORRENT, DELETED, ChannelMetadataPayload, int2time
# This table should never be used from ORM directly.
# It is created as a VIRTUAL table by raw SQL and
# maintained by SQL triggers.
from Tribler.Core.exceptions import InvalidSignatureException

CLOCK_STATE_FILE = "clock.state"

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


class DiscreteClock(object):
    # Lamport-clock-like persistent counter
    # Horribly inefficient and stupid, but works
    def __init__(self, filename=None):
        self.filename = filename
        self.clock = 0
        # Read the clock from the disk if the filename is given
        if self.filename and os.path.isfile(self.filename):
            with open(self.filename, 'rb') as f:
                self.clock = int(f.read())

    def tick(self):
        self.clock += 1
        if self.filename:
            with open(self.filename, 'wb') as f:
                f.write(str(self.clock))
        return self.clock


class MetadataStore(object):
    def __init__(self, db_filename, channels_dir, my_key):
        self.db_filename = db_filename
        self.channels_dir = channels_dir
        self.my_key = my_key
        self._logger = logging.getLogger(self.__class__.__name__)
        self.clock = DiscreteClock(None if db_filename == ":memory:" else os.path.join(channels_dir, CLOCK_STATE_FILE))

        create_db = (db_filename == ":memory:" or not os.path.isfile(self.db_filename))

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self._db = orm.Database()

        # Accessors for ORM-managed classes
        # self.Author = author.define_binding(self._db)

        self.TrackerState = tracker_state.define_binding(self._db)
        self.TorrentState = torrent_state.define_binding(self._db)

        self.Metadata = metadata.define_binding(self._db)
        self.ChannelNode = channel_node.define_binding(self._db)
        self.TorrentMetadata = torrent_metadata.define_binding(self._db)
        self.ChannelMetadata = channel_metadata.define_binding(self._db)

        self.Metadata._logger = self._logger  # Use Store-level logger for every ORM-based class
        self.Metadata._my_key = my_key
        self.Metadata._clock = self.clock

        self.ChannelMetadata._channels_dir = channels_dir

        # TODO: move Category Filter into a module-level global stateless object (i.e. make it a singleton)
        self.ChannelMetadata._category_filter = Category()

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
                self._db.execute(sql_add_infohash_index)

    def shutdown(self):
        self._db.disconnect()

    def process_channel_dir(self, dirname, channel_id):
        """
        Load all metadata blobs in a given directory.
        :param dirname: The directory containing the metadata blobs.
        :param channel_id: public_key of the channel.
        """
        # We use multiple separate db_sessions here to limit memory usage when reading big channels

        with db_session:
            channel = self.ChannelMetadata.get(public_key=channel_id)
            self._logger.debug("Starting processing channel dir %s. Channel %s local/max version %i/%i",
                               dirname, str(channel.public_key).encode("hex"), channel.local_version,
                               channel.timestamp)

        for filename in sorted(os.listdir(dirname)):
            with db_session:
                channel = self.ChannelMetadata.get(public_key=channel_id)
                full_filename = os.path.join(dirname, filename)

                blob_sequence_number = None
                if filename.endswith(BLOB_EXTENSION):
                    blob_sequence_number = int(filename[:-len(BLOB_EXTENSION)])
                elif filename.endswith(BLOB_EXTENSION + '.lz4'):
                    blob_sequence_number = int(filename[:-len(BLOB_EXTENSION + '.lz4')])

                if blob_sequence_number is not None:
                    # Skip blobs containing data we already have and those that are
                    # ahead of the channel version known to us
                    if blob_sequence_number <= channel.local_version or blob_sequence_number > channel.timestamp:
                        continue
                    try:
                        self.process_mdblob_file(full_filename)
                        # We track the local version of the channel while reading blobs
                        channel.local_version = blob_sequence_number
                    except InvalidSignatureException:
                        self._logger.error("Not processing metadata located at %s: invalid signature", full_filename)

        self._logger.debug("Finished processing channel dir %s. Channel %s local/max version %i/%i",
                           dirname, str(channel.public_key).encode("hex"), channel.local_version,
                           channel.timestamp)

    @db_session
    def process_mdblob_file(self, filepath):
        """
        Process a file with metadata in a channel directory.
        :param filepath: The path to the file
        :return Metadata objects list if we can correctly load the metadata
        """
        with open(filepath, 'rb') as f:
            serialized_data = f.read()

        if filepath.endswith('.lz4'):
            return self.process_compressed_mdblob(serialized_data)
        else:
            return self.process_squashed_mdblob(serialized_data)

    @db_session
    def process_compressed_mdblob(self, compressed_data):
        return self.process_squashed_mdblob(lz4.frame.decompress(compressed_data))

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
                return self.update_channel_info(payload)

    @db_session
    def update_channel_info(self, payload):
        """
        We received some channel metadata, possibly over the network.
        Validate the signature, update the local metadata store and put in at the beginning of the download queue
        if necessary.
        :param payload: The channel metadata, in serialized form.
        """

        channel = self.ChannelMetadata.get_channel_with_id(payload.public_key)
        if channel:
            if payload.timestamp > channel.timestamp:
                # Update the channel that is already there.
                self._logger.info("Updating channel metadata %s ts %s->%s", str(channel.public_key).encode("hex"),
                                  str(channel.timestamp), str(int2time(payload.timestamp)))
                channel.set(**ChannelMetadataPayload.to_dict(payload))
        else:
            # Add new channel object to DB
            channel = self.ChannelMetadata.from_payload(payload)

        """
        if channel.version > channel.local_version:
        #TODO: handle the case where the local version is the same as the new one and is not seeded
        """
        return channel

    @db_session
    def get_my_channel(self):
        return self.ChannelMetadata.get_channel_with_id(self.my_key.pub().key_to_bin()[10:])

    @db_session
    def get_num_channels(self):
        return orm.count(self.ChannelMetadata.select(lambda g: g.metadata_type == CHANNEL_TORRENT))

    @db_session
    def get_num_torrents(self):
        return orm.count(self.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT))
