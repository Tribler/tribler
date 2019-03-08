from __future__ import absolute_import

import logging
import os
from binascii import hexlify
from datetime import datetime

import lz4.frame

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.OrmBindings import (
    channel_metadata, channel_node, misc, torrent_metadata, torrent_state, tracker_state)
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import BLOB_EXTENSION
from Tribler.Core.Modules.MetadataStore.serialization import (
    CHANNEL_NODE, CHANNEL_TORRENT, DELETED, REGULAR_TORRENT, read_payload_with_offset, time2int)
from Tribler.Core.exceptions import InvalidSignatureException
from Tribler.pyipv8.ipv8.database import database_blob

CLOCK_STATE_FILE = "clock.state"

NO_ACTION = 0
UNKNOWN_CHANNEL = 1
UPDATED_OUR_VERSION = 2
GOT_SAME_VERSION = 3
GOT_NEWER_VERSION = 4
UNKNOWN_TORRENT = 5
DELETED_METADATA = 6

# This table should never be used from ORM directly.
# It is created as a VIRTUAL table by raw SQL and
# maintained by SQL triggers.
sql_create_fts_table = """
    CREATE VIRTUAL TABLE IF NOT EXISTS FtsIndex USING FTS5
        (title, tags, content='ChannelNode', prefix = '2 3 4 5',
         tokenize='porter unicode61 remove_diacritics 1');"""

sql_add_fts_trigger_insert = """
    CREATE TRIGGER IF NOT EXISTS fts_ai AFTER INSERT ON ChannelNode
    BEGIN
        INSERT INTO FtsIndex(rowid, title, tags) VALUES
            (new.rowid, new.title, new.tags);
    END;"""

sql_add_fts_trigger_delete = """
    CREATE TRIGGER IF NOT EXISTS fts_ad AFTER DELETE ON ChannelNode
    BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
    END;"""

sql_add_fts_trigger_update = """
    CREATE TRIGGER IF NOT EXISTS fts_au AFTER UPDATE ON ChannelNode BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
        INSERT INTO FtsIndex(rowid, title, tags) VALUES (new.rowid, new.title,
      new.tags);
    END;"""

sql_add_signature_index = "CREATE INDEX SignatureIndex ON ChannelNode(signature);"
sql_add_public_key_index = "CREATE INDEX PublicKeyIndex ON ChannelNode(public_key);"
sql_add_infohash_index = "CREATE INDEX InfohashIndex ON ChannelNode(infohash);"


class BadChunkException(Exception):
    pass


class DiscreteClock(object):
    # Lamport-clock-like persistent counter
    # Horribly inefficient and stupid, but works
    store_value_name = "discrete_clock"

    def __init__(self, datastore=None):
        # This is a stupid workaround for people who reinstall Tribler
        # and lose their database. We don't know what was their channel
        # clock before, but at least we can assume that they were not
        # adding to it 1000 torrents per second constantly...
        self.clock = time2int(datetime.utcnow()) * 1000
        self.datastore = datastore

    def init_clock(self):
        if self.datastore:
            with db_session:
                store_object = self.datastore.get(name=self.store_value_name, )
                if not store_object:
                    self.datastore(name=self.store_value_name, value=str(self.clock))
                else:
                    self.clock = int(store_object.value)

    def tick(self):
        self.clock += 1
        if self.datastore:
            with db_session:
                self.datastore[self.store_value_name].value = str(self.clock)
        return self.clock


class MetadataStore(object):
    def __init__(self, db_filename, channels_dir, my_key):
        self.db_filename = db_filename
        self.channels_dir = channels_dir
        self.my_key = my_key
        self._logger = logging.getLogger(self.__class__.__name__)

        create_db = (db_filename == ":memory:" or not os.path.isfile(self.db_filename))

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self._db = orm.Database()

        self.MiscData = misc.define_binding(self._db)

        self.TrackerState = tracker_state.define_binding(self._db)
        self.TorrentState = torrent_state.define_binding(self._db)

        self.clock = DiscreteClock(None if db_filename == ":memory:" else self.MiscData)

        self.ChannelNode = channel_node.define_binding(self._db, logger=self._logger, key=my_key, clock=self.clock)
        self.TorrentMetadata = torrent_metadata.define_binding(self._db)
        self.ChannelMetadata = channel_metadata.define_binding(self._db)

        self.ChannelMetadata._channels_dir = channels_dir

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

        if create_db:
            with db_session:
                self.MiscData(name="db_version", value="0")

        self.clock.init_clock()

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
                               dirname, hexlify(str(channel.public_key)), channel.local_version,
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
                    # ==================|          channel data       |===
                    # ===start_timestamp|---local_version----timestamp|===
                    # local_version is essentially a cursor pointing into the current state of update process
                    if blob_sequence_number <= channel.start_timestamp or \
                            blob_sequence_number <= channel.local_version or \
                            blob_sequence_number > channel.timestamp:
                        continue
                    try:
                        self.process_mdblob_file(full_filename)
                        # We track the local version of the channel while reading blobs
                        channel.local_version = blob_sequence_number
                    except InvalidSignatureException:
                        self._logger.error("Not processing metadata located at %s: invalid signature", full_filename)

        self._logger.debug("Finished processing channel dir %s. Channel %s local/max version %i/%i",
                           dirname, hexlify(str(channel.public_key)), channel.local_version,
                           channel.timestamp)

    @db_session
    def process_mdblob_file(self, filepath):
        """
        Process a file with metadata in a channel directory.
        :param filepath: The path to the file
        :return ChannelNode objects list if we can correctly load the metadata
        """
        with open(filepath, 'rb') as f:
            serialized_data = f.read()

        return (self.process_compressed_mdblob(serialized_data) if filepath.endswith('.lz4') else
                self.process_squashed_mdblob(serialized_data))

    def process_compressed_mdblob(self, compressed_data):
        try:
            decompressed_data = lz4.frame.decompress(compressed_data)
        except RuntimeError:
            self._logger.warning("Unable to decompress mdblob")
            return []

        return self.process_squashed_mdblob(decompressed_data)

    @db_session
    def process_squashed_mdblob(self, chunk_data):
        results_list = []
        offset = 0
        while offset < len(chunk_data):
            payload, offset = read_payload_with_offset(chunk_data, offset)
            results_list.append(self.process_payload(payload))
        return results_list

    @db_session
    def process_payload(self, payload):
        if payload.metadata_type == DELETED:
            # We only allow people to delete their own entries, thus PKs must match
            existing_metadata = self.ChannelNode.get(signature=payload.delete_signature,
                                                     public_key=payload.public_key)
            if existing_metadata:
                existing_metadata.delete()
                return None, DELETED_METADATA
            return None, NO_ACTION

        # Check the payload timestamp<->id_ correctness
        if payload.timestamp < payload.id_:
            return None, NO_ACTION

        # Check if we already got an older version of the same node that we can update, and
        # check the uniqueness constraint on public_key+infohash tuple. If the received entry
        # has the same tuple as the entry we already have, update our entry if necessary.
        # This procedure is necessary to handle the case when the original author of the payload
        # had created another entry with the same infohash earlier, deleted it, and sent
        # the different versions to two different peers.
        # There is a corner case where there already exist 2 entries in our database that match both
        # update conditions:
        # A: (pk, id1, ih1)
        # B: (pk, id2, ih2)
        # Now, when we receive the payload C1:(pk, id1, ih2) or C2:(pk, id2, ih1), we have to
        # replace _both_ entries with a single one, to honor the DB uniqueness constraints.
        # Get 0-2 entries that match the update condition
        # TODO: optimize this with a single UPSERT-style query
        pk_lambda = lambda g: g.public_key == database_blob(payload.public_key)
        if payload.metadata_type == CHANNEL_NODE:
            local_entries = self.ChannelNode.select(pk_lambda)
        else:
            local_entries = self.TorrentMetadata.select(pk_lambda).where(
                lambda g: (g.infohash == database_blob(payload.infohash) or g.id_ == payload.id_)) \
                .sort_by(lambda g: g.timestamp)

        deleted_something = False
        for local_node in list(local_entries):
            if local_node.timestamp < payload.timestamp:
                local_node.delete()
                deleted_something = True
            elif local_node.timestamp > payload.timestamp:
                return local_node, GOT_NEWER_VERSION
            else:
                return local_node, GOT_SAME_VERSION

        # Get the corresponding channel from local database to see if we really need to update our
        # local contents of the channel by comparing the channel's local_version with the payload's timestamp.
        # This check is necessary to prevent other peers pushing deleted entries into the
        # channels we are subscribed to.
        # If local channel version is 0, we are still in preview mode and willing to collect everything.
        channel = self.ChannelMetadata.get(public_key=payload.public_key, id_=payload.origin_id)
        if channel and (channel.local_version != 0) and (payload.timestamp <= channel.local_version):
            return None, NO_ACTION

        if payload.metadata_type == REGULAR_TORRENT:
            return self.TorrentMetadata.from_payload(
                payload), UPDATED_OUR_VERSION if deleted_something else UNKNOWN_TORRENT
        if payload.metadata_type == CHANNEL_TORRENT:
            return self.ChannelMetadata.from_payload(
                payload), UPDATED_OUR_VERSION if deleted_something else UNKNOWN_CHANNEL

        return None, NO_ACTION

    @db_session
    def get_my_channel(self):
        return self.ChannelMetadata.get_channel_with_id(self.my_key.pub().key_to_bin()[10:])

    @db_session
    def get_num_channels(self):
        return orm.count(self.ChannelMetadata.select(lambda g: g.metadata_type == CHANNEL_TORRENT))

    @db_session
    def get_num_torrents(self):
        return orm.count(self.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT))
