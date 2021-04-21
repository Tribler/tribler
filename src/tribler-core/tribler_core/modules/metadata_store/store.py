import enum
import logging
import threading
from asyncio import get_event_loop
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from time import sleep, time

from ipv8.database import database_blob

import lz4.frame

from pony import orm
from pony.orm import CacheIndexError, TransactionIntegrityError, db_session, desc, left_join, raw_sql, select

from tribler_common.simpledefs import NTFY

from tribler_core.exceptions import InvalidSignatureException
from tribler_core.modules.category_filter.l2_filter import is_forbidden
from tribler_core.modules.metadata_store.orm_bindings import (
    binary_node,
    channel_description,
    channel_metadata,
    channel_node,
    channel_peer,
    channel_thumbnail,
    channel_vote,
    collection_node,
    json_node,
    metadata_node,
    misc,
    torrent_metadata,
    torrent_state,
    tracker_state,
    vsids,
)
from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import get_mdblob_sequence_number
from tribler_core.modules.metadata_store.orm_bindings.channel_node import LEGACY_ENTRY, TODELETE
from tribler_core.modules.metadata_store.orm_bindings.torrent_metadata import NULL_KEY_SUBST
from tribler_core.modules.metadata_store.serialization import (
    BINARY_NODE,
    CHANNEL_DESCRIPTION,
    CHANNEL_NODE,
    CHANNEL_THUMBNAIL,
    CHANNEL_TORRENT,
    COLLECTION_NODE,
    DELETED,
    JSON_NODE,
    METADATA_NODE,
    NULL_KEY,
    REGULAR_TORRENT,
    read_payload_with_offset,
)
from tribler_core.utilities.path_util import str_path
from tribler_core.utilities.unicode import hexlify

BETA_DB_VERSIONS = [0, 1, 2, 3, 4, 5]
CURRENT_DB_VERSION = 13

MIN_BATCH_SIZE = 10
MAX_BATCH_SIZE = 1000

POPULAR_TORRENTS_FRESHNESS_PERIOD = 60 * 60 * 24  # Last day
POPULAR_TORRENTS_COUNT = 100


# This table should never be used from ORM directly.
# It is created as a VIRTUAL table by raw SQL and
# maintained by SQL triggers.
sql_create_fts_table = """
    CREATE VIRTUAL TABLE IF NOT EXISTS FtsIndex USING FTS5
        (title, content='ChannelNode', prefix = '2 3 4 5',
         tokenize='porter unicode61 remove_diacritics 1');"""

sql_add_fts_trigger_insert = """
    CREATE TRIGGER IF NOT EXISTS fts_ai AFTER INSERT ON ChannelNode
    BEGIN
        INSERT INTO FtsIndex(rowid, title) VALUES (new.rowid, new.title);
    END;"""

sql_add_fts_trigger_delete = """
    CREATE TRIGGER IF NOT EXISTS fts_ad AFTER DELETE ON ChannelNode
    BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
    END;"""

sql_add_fts_trigger_update = """
    CREATE TRIGGER IF NOT EXISTS fts_au AFTER UPDATE ON ChannelNode BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
        INSERT INTO FtsIndex(rowid, title) VALUES (new.rowid, new.title);
    END;"""

sql_add_torrentstate_trigger_after_insert = """
    CREATE TRIGGER IF NOT EXISTS torrentstate_ai AFTER INSERT ON TorrentState
    BEGIN
        UPDATE "TorrentState" SET has_data = (last_check > 0) WHERE rowid = new.rowid;
    END;
"""

sql_add_torrentstate_trigger_after_update = """
    CREATE TRIGGER IF NOT EXISTS torrentstate_au AFTER UPDATE ON TorrentState
    BEGIN
        UPDATE "TorrentState" SET has_data = (last_check > 0) WHERE rowid = new.rowid;
    END;
"""

sql_create_partial_index_channelnode_subscribed = """
    CREATE INDEX IF NOT EXISTS idx_channelnode__metadata_subscribed__partial ON "ChannelNode" (subscribed)
    WHERE subscribed = 1
"""

# ACHTUNG! When adding a new metadata_types which should be indexed you need to add
# it to this list and write a database upgrade which recreates the partial index
indexed_metadata_types = [
    CHANNEL_NODE,
    METADATA_NODE,
    COLLECTION_NODE,
    JSON_NODE,
    CHANNEL_DESCRIPTION,
    BINARY_NODE,
    CHANNEL_THUMBNAIL,
    CHANNEL_TORRENT,
]  # Does not include REGULAR_TORRENT! We dont want for regular torrents to be added to the partial index.

sql_create_partial_index_channelnode_metadata_type = """
    CREATE INDEX IF NOT EXISTS idx_channelnode__metadata_type__partial ON "ChannelNode" (metadata_type)
    WHERE %s;
""" % ' OR '.join(
    f'metadata_type = {discriminator_value}' for discriminator_value in indexed_metadata_types
)

sql_create_partial_index_torrentstate_last_check = """
    CREATE INDEX IF NOT EXISTS idx_torrentstate__last_check__partial
    ON TorrentState (last_check, seeders, leechers, self_checked)
    WHERE has_data = 1;
"""


class ObjState(enum.Enum):
    UPDATED_OUR_VERSION = enum.auto()  # We updated the local version of the ORM object with the received one
    GOT_NEWER_VERSION = enum.auto()  # Our local version of the ORM object is newer than the received one
    GOT_SAME_VERSION = enum.auto()  # Our local version of the ORM object is the same as the received one
    UNKNOWN_OBJECT = enum.auto()  # The received object is unknown to us and thus added to ORM


@dataclass
class ProcessingResult:
    # This class is used to return results of processing of a payload by process_payload.
    # It includes the ORM object created as a result of processing, the state of the object
    # as indicated by ObjState enum, and missing dependencies list that includes a list of query
    # arguments for get_entries to query the sender back through Remote Query Community
    md_obj: object = None
    obj_state: object = None
    missing_deps: list = field(default_factory=list)


class MetadataStore:
    def __init__(
        self,
        db_filename,
        channels_dir,
        my_key,
        disable_sync=False,
        notifier=None,
        check_tables=True,
        db_version: int = CURRENT_DB_VERSION,
    ):
        self.notifier = notifier  # Reference to app-level notification service
        self.db_filename = db_filename
        self.channels_dir = channels_dir
        self.my_key = my_key
        self.my_public_key_bin = bytes(database_blob(self.my_key.pub().key_to_bin()[10:]))
        self._logger = logging.getLogger(self.__class__.__name__)

        self._shutting_down = False
        self.batch_size = 10  # reasonable number, a little bit more than typically fits in a single UDP packet
        self.reference_timedelta = timedelta(milliseconds=100)
        self.sleep_on_external_thread = 0.05  # sleep this amount of seconds between batches executed on external thread

        create_db = str(db_filename) == ":memory:" or not self.db_filename.is_file()

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self._db = orm.Database()

        # This attribute is internally called by Pony on startup, though pylint cannot detect it
        # with the static analysis.
        # pylint: disable=unused-variable
        @self._db.on_connect(provider='sqlite')
        def sqlite_disable_sync(_, connection):
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA temp_store = MEMORY")
            cursor.execute("PRAGMA foreign_keys = ON")

            # Disable disk sync for special cases
            if disable_sync:
                # !!! ACHTUNG !!! This should be used only for special cases (e.g. DB upgrades), because
                # losing power during a write will corrupt the database.
                cursor.execute("PRAGMA journal_mode = 0")
                cursor.execute("PRAGMA synchronous = 0")
            # pylint: enable=unused-variable

        self.MiscData = misc.define_binding(self._db)

        self.TrackerState = tracker_state.define_binding(self._db)
        self.TorrentState = torrent_state.define_binding(self._db)

        self.ChannelNode = channel_node.define_binding(self._db, logger=self._logger, key=my_key)

        self.MetadataNode = metadata_node.define_binding(self._db)
        self.CollectionNode = collection_node.define_binding(self._db)
        self.TorrentMetadata = torrent_metadata.define_binding(self._db)
        self.ChannelMetadata = channel_metadata.define_binding(self._db)

        self.JsonNode = json_node.define_binding(self._db, db_version)
        self.ChannelDescription = channel_description.define_binding(self._db)

        self.BinaryNode = binary_node.define_binding(self._db, db_version)
        self.ChannelThumbnail = channel_thumbnail.define_binding(self._db)

        self.ChannelVote = channel_vote.define_binding(self._db)
        self.ChannelPeer = channel_peer.define_binding(self._db)
        self.Vsids = vsids.define_binding(self._db)

        self.ChannelMetadata._channels_dir = channels_dir  # pylint: disable=protected-access

        self._db.bind(provider='sqlite', filename=str(db_filename), create_db=create_db, timeout=120.0)
        self._db.generate_mapping(
            create_tables=create_db, check_tables=check_tables
        )  # Must be run out of session scope
        if create_db:
            with db_session(ddl=True):
                self._db.execute(sql_create_fts_table)
                self.create_fts_triggers()
                self.create_torrentstate_triggers()
                self.create_partial_indexes()

        if create_db:
            with db_session:
                self.MiscData(name="db_version", value=str(db_version))

        with db_session:
            default_vsids = self.Vsids.get(rowid=0)
            if not default_vsids:
                default_vsids = self.Vsids.create_default_vsids()
            self.ChannelMetadata.votes_scaling = default_vsids.max_val

    def drop_indexes(self):
        cursor = self._db.get_connection().cursor()
        cursor.execute("select name from sqlite_master where type='index' and name like 'idx_%'")
        for [index_name] in cursor.fetchall():
            cursor.execute(f"drop index {index_name}")

    def get_objects_to_create(self):
        connection = self._db.get_connection()
        schema = self._db.schema
        provider = schema.provider
        created_tables = set()
        result = []
        for table in schema.order_tables_to_create():
            for db_object in table.get_objects_to_create(created_tables):
                if not db_object.exists(provider, connection):
                    result.append(db_object)
        return result

    def drop_fts_triggers(self):
        cursor = self._db.get_connection().cursor()
        cursor.execute("select name from sqlite_master where type='trigger' and name like 'fts_%'")
        for [trigger_name] in cursor.fetchall():
            cursor.execute(f"drop trigger {trigger_name}")

    def create_fts_triggers(self):
        cursor = self._db.get_connection().cursor()
        cursor.execute(sql_add_fts_trigger_insert)
        cursor.execute(sql_add_fts_trigger_delete)
        cursor.execute(sql_add_fts_trigger_update)

    def fill_fts_index(self):
        cursor = self._db.get_connection().cursor()
        cursor.execute("insert into FtsIndex(rowid, title) select rowid, title from ChannelNode")

    def create_torrentstate_triggers(self):
        cursor = self._db.get_connection().cursor()
        cursor.execute(sql_add_torrentstate_trigger_after_insert)
        cursor.execute(sql_add_torrentstate_trigger_after_update)

    def create_partial_indexes(self):
        cursor = self._db.get_connection().cursor()
        cursor.execute(sql_create_partial_index_channelnode_subscribed)
        cursor.execute(sql_create_partial_index_channelnode_metadata_type)

    @db_session
    def upsert_vote(self, channel, peer_pk):
        voter = self.ChannelPeer.get(public_key=peer_pk)
        if not voter:
            voter = self.ChannelPeer(public_key=peer_pk)
        vote = self.ChannelVote.get(voter=voter, channel=channel)
        if not vote:
            vote = self.ChannelVote(voter=voter, channel=channel)
        else:
            vote.vote_date = datetime.utcnow()
        return vote

    @db_session
    def vote_bump(self, public_key, id_, voter_pk):
        channel = self.ChannelMetadata.get_for_update(public_key=public_key, id_=id_)
        if not channel:
            return
        vote = self.upsert_vote(channel, voter_pk)

        self.Vsids[0].bump_channel(channel, vote)

    def shutdown(self):
        self._shutting_down = True
        self._db.disconnect()

    def disconnect_thread(self):
        # Ugly workaround for closing threadpool connections
        # Remark: maybe subclass ThreadPoolExecutor to handle this automatically?
        if not isinstance(threading.current_thread(), threading._MainThread):  # pylint: disable=W0212
            self._db.disconnect()

    @staticmethod
    def get_list_of_channel_blobs_to_process(dirname, start_timestamp):
        blobs_to_process = []
        total_blobs_size = 0
        for full_filename in sorted(dirname.iterdir()):
            blob_sequence_number = get_mdblob_sequence_number(full_filename.name)

            if blob_sequence_number is None or blob_sequence_number <= start_timestamp:
                continue
            blob_size = full_filename.stat().st_size
            total_blobs_size += blob_size
            blobs_to_process.append((blob_sequence_number, full_filename, blob_size))
        return blobs_to_process, total_blobs_size

    @db_session
    def get_channel_dir_path(self, channel):
        return self.channels_dir / channel.dirname

    @db_session
    def compute_channel_update_progress(self, channel):
        blobs_to_process, total_blobs_size = self.get_list_of_channel_blobs_to_process(
            self.get_channel_dir_path(channel), channel.start_timestamp
        )
        processed_blobs_size = 0
        for blob_sequence_number, _, blob_size in blobs_to_process:
            if channel.local_version >= blob_sequence_number >= channel.start_timestamp:
                processed_blobs_size += blob_size
        return float(processed_blobs_size) / total_blobs_size

    def process_channel_dir(self, dirname, public_key, id_, **kwargs):
        """
        Load all metadata blobs in a given directory.
        :param dirname: The directory containing the metadata blobs.
        :param skip_personal_metadata_payload: if this is set to True, personal torrent metadata payload received
                through gossip will be ignored. The default value is True.
        :param external_thread: indicate to lower levels that this is running on a background thread
        :param public_key: public_key of the channel.
        :param id_: id_ of the channel.
        """
        # We use multiple separate db_sessions here to limit the memory and reactor time impact,
        # but we must check the existence of the channel every time to avoid race conditions
        with db_session:
            channel = self.ChannelMetadata.get(public_key=public_key, id_=id_)
            if not channel:
                return
            self._logger.debug(
                "Starting processing channel dir %s. Channel %s local/max version %i/%i",
                dirname,
                hexlify(channel.public_key),
                channel.local_version,
                channel.timestamp,
            )

        blobs_to_process, total_blobs_size = self.get_list_of_channel_blobs_to_process(dirname, channel.start_timestamp)

        # We count total size of all the processed blobs to estimate the progress of channel processing
        # Counting the blobs' sizes are the only reliable way to estimate the remaining processing time,
        # because it accounts for potential deletions, entry modifications, etc.
        processed_blobs_size = 0
        for blob_sequence_number, full_filename, blob_size in blobs_to_process:
            processed_blobs_size += blob_size
            # Skip blobs containing data we already have and those that are
            # ahead of the channel version known to us
            # ==================|          channel data       |===
            # ===start_timestamp|---local_version----timestamp|===
            # local_version is essentially a cursor pointing into the current state of update process
            with db_session:
                channel = self.ChannelMetadata.get(public_key=public_key, id_=id_)
                if not channel:
                    return
                if (
                    blob_sequence_number <= channel.start_timestamp
                    or blob_sequence_number <= channel.local_version
                    or blob_sequence_number > channel.timestamp
                ):
                    continue
            try:
                self.process_mdblob_file(str(full_filename), **kwargs, channel_public_key=public_key)
                # If we stopped mdblob processing due to shutdown flag, we should stop
                # processing immediately, so that the channel local version will not increase
                if self._shutting_down:
                    return
                # We track the local version of the channel while reading blobs
                with db_session:
                    channel = self.ChannelMetadata.get_for_update(public_key=public_key, id_=id_)
                    if not channel:
                        return
                    channel.local_version = blob_sequence_number
                    if self.notifier:
                        channel_update_dict = channel.to_simple_dict()
                        channel_update_dict["progress"] = float(processed_blobs_size) / total_blobs_size
                        self.notifier.notify(NTFY.CHANNEL_ENTITY_UPDATED, channel_update_dict)
            except InvalidSignatureException:
                self._logger.error("Not processing metadata located at %s: invalid signature", full_filename)

        with db_session:
            channel = self.ChannelMetadata.get(public_key=public_key, id_=id_)
            if not channel:
                return
            self._logger.debug(
                "Finished processing channel dir %s. Channel %s local/max version %i/%i",
                dirname,
                hexlify(bytes(channel.public_key)),
                channel.local_version,
                channel.timestamp,
            )

    def process_mdblob_file(self, filepath, **kwargs):
        """
        Process a file with metadata in a channel directory.
        :param filepath: The path to the file
        :param skip_personal_metadata_payload: if this is set to True, personal torrent metadata payload received
                through gossip will be ignored. The default value is True.
        :param external_thread: indicate to the lower lever that we're running in the backround thread,
            to possibly pace down the upload process
        :return: a list of tuples of (<metadata or payload>, <action type>)
        """
        with open(str_path(filepath), 'rb') as f:
            serialized_data = f.read()

        if str(filepath).endswith('.lz4'):
            return self.process_compressed_mdblob(serialized_data, **kwargs)
        return self.process_squashed_mdblob(serialized_data, **kwargs)

    async def process_compressed_mdblob_threaded(self, compressed_data, **kwargs):
        def _process_blob():
            result = None
            try:
                with db_session:
                    try:
                        result = self.process_compressed_mdblob(compressed_data, **kwargs)
                    except (TransactionIntegrityError, CacheIndexError) as err:
                        self._logger.error("DB transaction error when tried to process compressed mdblob: %s", str(err))
            # Unfortunately, we have to catch the exception twice, because Pony can raise them both on the exit from
            # db_session, and on calling the line of code
            except (TransactionIntegrityError, CacheIndexError) as err:
                self._logger.error("DB transaction error when tried to process compressed mdblob: %s", str(err))
            finally:
                self.disconnect_thread()
            return result

        return await get_event_loop().run_in_executor(None, _process_blob)

    def process_compressed_mdblob(self, compressed_data, **kwargs):
        try:
            decompressed_data = lz4.frame.decompress(compressed_data)
        except RuntimeError:
            self._logger.warning("Unable to decompress mdblob")
            return []
        return self.process_squashed_mdblob(decompressed_data, **kwargs)

    def process_squashed_mdblob(self, chunk_data, external_thread=False, **kwargs):
        """
        Process raw concatenated payloads blob. This routine breaks the database access into smaller batches.
        It uses a congestion-control like algorithm to determine the optimal batch size, targeting the
        batch processing time value of self.reference_timedelta.

        :param chunk_data: the blob itself, consists of one or more GigaChannel payloads concatenated together
        :param external_thread: if this is set to True, we add some sleep between batches to allow other threads
            to get the database lock. This is an ugly workaround for Python and asynchronous programming (locking)
            imperfections. It only makes sense to use it when this routine runs on a non-reactor thread.
        :return: a list of tuples of (<metadata or payload>, <action type>)
        """

        offset = 0
        payload_list = []
        while offset < len(chunk_data):
            payload, offset = read_payload_with_offset(chunk_data, offset)
            payload_list.append(payload)

        result = []
        total_size = len(payload_list)
        start = 0
        while start < total_size:
            end = start + self.batch_size
            batch = payload_list[start:end]
            batch_start_time = datetime.now()

            # We separate the sessions to minimize database locking.
            with db_session:
                for payload in batch:
                    result.extend(self.process_payload(payload, **kwargs))

            # Batch size adjustment
            batch_end_time = datetime.now() - batch_start_time
            target_coeff = batch_end_time.total_seconds() / self.reference_timedelta.total_seconds()
            if len(batch) == self.batch_size:
                # Adjust batch size only for full batches
                if target_coeff < 0.8:
                    self.batch_size += self.batch_size
                elif target_coeff > 1.0:
                    self.batch_size = int(float(self.batch_size) / target_coeff)
                # we want to guarantee that at least something
                # will go through, but not too much
                self.batch_size = min(max(self.batch_size, MIN_BATCH_SIZE), MAX_BATCH_SIZE)
            self._logger.debug(
                (
                    "Added payload batch to DB (entries, seconds): %i %f",
                    (self.batch_size, float(batch_end_time.total_seconds())),
                )
            )
            start = end
            if self._shutting_down:
                break

            if external_thread:
                sleep(self.sleep_on_external_thread)

        return result

    @db_session
    def process_payload(self, payload, skip_personal_metadata_payload=True, channel_public_key=None):
        """
        This routine decides what to do with a given payload and executes the necessary actions.
        To do so, it looks into the database, compares version numbers, etc.
        It returns a list of tuples each of which contain the corresponding new/old object and the actions
        that were performed on that object.
        :param payload: payload to work on
        :param skip_personal_metadata_payload: if this is set to True, personal torrent metadata payload received
                through gossip will be ignored. The default value is True.
        :param channel_public_key: rejects payloads that do not belong to this key.
               Enabling this allows to skip some costly checks during e.g. channel processing.

        :return: a list of tuples of (<metadata or payload>, <action type>)
        """

        # In case we're processing a channel, we allow only payloads with the channel's public_key
        if channel_public_key is not None and payload.public_key != channel_public_key:
            self._logger.warning(
                "Tried to push metadata entry with foreign public key.\
             Expected public key: %s, entry public key / id: %s / %i",
                hexlify(channel_public_key),
                payload.public_key,
                payload.id_,
            )
            return []

        if payload.metadata_type == DELETED:
            if payload.public_key == self.my_public_key_bin and skip_personal_metadata_payload:
                return []
            # We only allow people to delete their own entries, thus PKs must match
            node = self.ChannelNode.get_for_update(signature=payload.delete_signature, public_key=payload.public_key)
            if node:
                node.delete()
                return []

        if payload.metadata_type not in [
            CHANNEL_TORRENT,
            REGULAR_TORRENT,
            COLLECTION_NODE,
            CHANNEL_DESCRIPTION,
            CHANNEL_THUMBNAIL,
        ]:
            return []

        # Check for offending words stop-list
        if is_forbidden(
            " ".join([getattr(payload, attr) for attr in ("title", "tags", "text") if hasattr(payload, attr)])
        ):
            return []

        # FFA payloads get special treatment:
        if payload.public_key == NULL_KEY:
            if payload.metadata_type == REGULAR_TORRENT:
                node = self.TorrentMetadata.add_ffa_from_dict(payload.to_dict())
                if node:
                    return [ProcessingResult(md_obj=node, obj_state=ObjState.UNKNOWN_OBJECT)]
            return []

        if channel_public_key is None and payload.metadata_type in [
            COLLECTION_NODE,
            REGULAR_TORRENT,
            CHANNEL_DESCRIPTION,
            CHANNEL_THUMBNAIL,
        ]:
            # Check if the received payload is from a channel that we already have and send update if necessary

            # Get the toplevel parent
            parent = self.ChannelNode.get(public_key=payload.public_key, id_=payload.origin_id)
            if parent:
                parent_channel = None
                if parent.origin_id == 0:
                    parent_channel = parent
                else:
                    parents_ids = parent.get_parents_ids()
                    if 0 in parents_ids:
                        parent_channel = self.ChannelNode.get(public_key=payload.public_key, id_=parents_ids[1])
                if parent_channel and parent_channel.local_version > payload.timestamp:
                    # Remark: add check_for_missing_dependencies here when collections are allowed descriptions
                    return []

        # Check for the older version of the added node
        node = self.ChannelNode.get_for_update(public_key=database_blob(payload.public_key), id_=payload.id_)
        if node:
            node.to_simple_dict()  # Force loading of related objects (like TorrentMetadata.health) in db_session
            update_results = self.update_channel_node(node, payload, skip_personal_metadata_payload)
            for r in update_results:
                r.missing_deps = self.check_for_missing_dependencies(r.md_obj, include_newer=True)
            return update_results

        if payload.public_key == self.my_public_key_bin and skip_personal_metadata_payload:
            return []
        for orm_class in (
            self.TorrentMetadata,
            self.ChannelMetadata,
            self.CollectionNode,
            self.ChannelThumbnail,
            self.ChannelDescription,
        ):
            if orm_class._discriminator_ == payload.metadata_type:  # pylint: disable=W0212
                obj = orm_class.from_payload(payload)
                missing_deps = self.check_for_missing_dependencies(obj)
                return [ProcessingResult(md_obj=obj, obj_state=ObjState.UNKNOWN_OBJECT, missing_deps=missing_deps)]
        return []

    @db_session
    def check_for_missing_dependencies(self, node, include_newer=False):
        """
        This method checks the given ORM node (object) for missing dependencies, such as thumbnails and/or
        descriptions. To do so, it checks for existence of special dependency flags in the object's
        "reserved_flags" field and checks for existence of the corresponding dependencies in the local database.
        For each missing dependency it will generate a query in the "get_entry" format that should be addressed to the
        peer that sent the original payload/node/object.
        If include_newer argument is true, it will generate a query even if the dependencies exist in the local
        database. However, this query will limit the selection to dependencies with a higher timestamp than that
        of the local versions. Effectively, this query asks the remote peer for updates on dependencies. Thus,
        it should only be issued when it is known that the parent object was updated.
        """
        if node.metadata_type not in (CHANNEL_TORRENT, COLLECTION_NODE):
            return []

        result = []
        for flag, dep_type in ((node.description_flag, CHANNEL_DESCRIPTION), (node.thumbnail_flag, CHANNEL_THUMBNAIL)):
            if flag:
                dep_node = self.ChannelNode.select(
                    lambda g: g.origin_id == node.id_
                    and g.public_key == node.public_key
                    # pylint: disable=cell-var-from-loop
                    and g.metadata_type == dep_type
                ).first()
                request_dict = {
                    "metadata_type": [dep_type],
                    "channel_pk": hexlify(node.public_key),
                    "origin_id": node.id_,
                    "first": 0,
                    "last": 1,
                }
                if not dep_node:
                    result.append(request_dict)
                elif include_newer:
                    request_dict["attribute_ranges"] = (("timestamp", dep_node.timestamp + 1, None),)
                    result.append(request_dict)
        return result

    @db_session
    def update_channel_node(self, node, payload, skip_personal_metadata_payload=True):
        # The received metadata has newer version than the stuff we got, so we have to update our version.
        if node.timestamp < payload.timestamp:
            # If we received a metadata payload signed by ourselves we simply ignore it since we are the only
            # authoritative source of information about our own channel.
            if payload.public_key == self.my_public_key_bin and skip_personal_metadata_payload:
                return []

            # Update local metadata entry
            if node.metadata_type == payload.metadata_type:
                node.set(**payload.to_dict())
                return [ProcessingResult(md_obj=node, obj_state=ObjState.UPDATED_OUR_VERSION)]
            # Workaround for the corner case of remote change of md type.
            # We delete the original node and replace it with the updated one.
            for orm_class in (self.ChannelMetadata, self.CollectionNode):
                if orm_class._discriminator_ == payload.metadata_type:  # pylint: disable=W0212
                    node.delete()
                    obj = orm_class.from_payload(payload)
                    return [ProcessingResult(md_obj=obj, obj_state=ObjState.UPDATED_OUR_VERSION)]
            self._logger.warning(
                f"Tried to update channel node to illegal type: "
                f" original type: {node.metadata_type}"
                f" updated type: {payload.metadata_type}"
                f" {hexlify(payload.public_key)}, {payload.id_} "
            )
            return []

        if node.timestamp > payload.timestamp:
            return [ProcessingResult(md_obj=node, obj_state=ObjState.GOT_NEWER_VERSION)]
        # Otherwise, we got the same version locally and do nothing.
        # Nevertheless, it is important to indicate to upper levels that we recognised
        # the entry, for e.g. channel votes bumping
        return [ProcessingResult(md_obj=node, obj_state=ObjState.GOT_SAME_VERSION)]

    @db_session
    def get_num_channels(self):
        return orm.count(self.ChannelMetadata.select(lambda g: g.metadata_type == CHANNEL_TORRENT))

    @db_session
    def get_num_torrents(self):
        return orm.count(self.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT))

    @db_session
    def torrent_exists_in_personal_channel(self, infohash):
        """
        Return True if torrent with given infohash exists in any of user's channels
        :param infohash: The infohash of the torrent
        :return: True if torrent exists else False
        """
        return self.TorrentMetadata.exists(
            lambda g: g.public_key == self.my_public_key_bin
            and g.infohash == database_blob(infohash)
            and g.status != LEGACY_ENTRY
        )

    # pylint: disable=unused-argument
    def search_keyword(self, query, lim=100):
        # Requires FTS5 table "FtsIndex" to be generated and populated.
        # FTS table is maintained automatically by SQL triggers.
        # BM25 ranking is embedded in FTS5.

        # Sanitize FTS query
        if not query or query == "*":
            return []

        fts_ids = raw_sql(
            """SELECT rowid FROM ChannelNode WHERE rowid IN (SELECT rowid FROM FtsIndex WHERE FtsIndex MATCH $query
            ORDER BY bm25(FtsIndex) LIMIT $lim) GROUP BY coalesce(infohash, rowid)"""
        )
        return left_join(g for g in self.MetadataNode if g.rowid in fts_ids)  # pylint: disable=E1135

    @db_session
    def get_entries_query(
        self,
        metadata_type=None,
        channel_pk=None,
        exclude_deleted=False,
        hide_xxx=False,
        exclude_legacy=False,
        origin_id=None,
        sort_by=None,
        sort_desc=True,
        max_rowid=None,
        txt_filter=None,
        subscribed=None,
        category=None,
        attribute_ranges=None,
        infohash=None,
        id_=None,
        complete_channel=None,
        self_checked_torrent=None,
        cls=None,
        health_checked_after=None,
        popular=None,
    ):
        """
        This method implements REST-friendly way to get entries from the database.
        :return: PonyORM query object corresponding to the given params.
        """
        # Warning! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere!

        if cls is None:
            cls = self.ChannelNode
        pony_query = self.search_keyword(txt_filter, lim=1000) if txt_filter else left_join(g for g in cls)

        if popular:
            if metadata_type:
                raise TypeError('Specifying `metadata_type` with `popular` is not allowed')
            metadata_type = REGULAR_TORRENT

            t = time() - POPULAR_TORRENTS_FRESHNESS_PERIOD
            health_list = list(
                select(
                    health
                    for health in self.TorrentState
                    if health.last_check >= t and (health.seeders > 0 or health.leechers > 0)
                ).order_by(lambda health: (health.seeders, health.leechers, health.last_check))[:POPULAR_TORRENTS_COUNT]
            )
            pony_query = pony_query.where(lambda g: g.health in health_list)

        if max_rowid is not None:
            pony_query = pony_query.where(lambda g: g.rowid <= max_rowid)

        if metadata_type is not None:
            try:
                pony_query = pony_query.where(lambda g: g.metadata_type in metadata_type)
            except TypeError:
                pony_query = pony_query.where(lambda g: g.metadata_type == metadata_type)

        pony_query = (
            pony_query.where(public_key=(b"" if channel_pk == NULL_KEY_SUBST else channel_pk))
            if channel_pk is not None
            else pony_query
        )

        if attribute_ranges is not None:
            for attr, left, right in attribute_ranges:
                if (
                    self.ChannelNode._adict_.get(attr)  # pylint: disable=W0212
                    or self.ChannelNode._subclass_adict_.get(attr)  # pylint: disable=W0212
                ) is None:  # Check against code injection
                    raise AttributeError("Tried to query for non-existent attribute")
                if left is not None:
                    pony_query = pony_query.where(f"g.{attr} >= left")
                if right is not None:
                    pony_query = pony_query.where(f"g.{attr} < right")

        # origin_id can be zero, for e.g. root channel
        pony_query = pony_query.where(id_=id_) if id_ is not None else pony_query
        pony_query = pony_query.where(origin_id=origin_id) if origin_id is not None else pony_query
        pony_query = pony_query.where(lambda g: g.subscribed) if subscribed is not None else pony_query
        pony_query = pony_query.where(lambda g: g.tags == category) if category else pony_query
        pony_query = pony_query.where(lambda g: g.status != TODELETE) if exclude_deleted else pony_query
        pony_query = pony_query.where(lambda g: g.xxx == 0) if hide_xxx else pony_query
        pony_query = pony_query.where(lambda g: g.status != LEGACY_ENTRY) if exclude_legacy else pony_query
        pony_query = pony_query.where(lambda g: g.infohash == infohash) if infohash else pony_query
        pony_query = (
            pony_query.where(lambda g: g.health.self_checked == self_checked_torrent)
            if self_checked_torrent is not None
            else pony_query
        )
        # ACHTUNG! Setting complete_channel to True forces the metadata type to Channels only!
        pony_query = (
            pony_query.where(lambda g: g.metadata_type == CHANNEL_TORRENT and g.timestamp == g.local_version)
            if complete_channel
            else pony_query
        )

        if health_checked_after is not None:
            pony_query = pony_query.where(lambda g: g.health.last_check >= health_checked_after)

        # Sort the query
        pony_query = pony_query.sort_by("desc(g.rowid)" if sort_desc else "g.rowid")

        if sort_by == "HEALTH":
            pony_query = pony_query.sort_by(
                "(desc(g.health.seeders), desc(g.health.leechers))"
                if sort_desc
                else "(g.health.seeders, g.health.leechers)"
            )
        elif sort_by == "size" and not issubclass(cls, self.ChannelMetadata):
            # Remark: this can be optimized to skip cases where size field does not matter
            # When querying for mixed channels / torrents lists, channels should have priority over torrents
            sort_expression = "desc(g.num_entries), desc(g.size)" if sort_desc else "g.num_entries, g.size"
            pony_query = pony_query.sort_by(sort_expression)
        elif sort_by:
            sort_expression = "g." + sort_by
            sort_expression = desc(sort_expression) if sort_desc else sort_expression
            pony_query = pony_query.sort_by(sort_expression)

        if sort_by is None:
            if txt_filter:
                pony_query = pony_query.sort_by(
                    f"""
                    (1 if g.metadata_type == {CHANNEL_TORRENT} else 2 if g.metadata_type == {COLLECTION_NODE} else 3),
                    desc(g.health.seeders), desc(g.health.leechers)
                """
                )
            elif popular:
                pony_query = pony_query.sort_by('(desc(g.health.seeders), desc(g.health.leechers))')

        return pony_query

    async def get_entries_threaded(self, **kwargs):
        def _get_results():
            result = self.get_entries(**kwargs)
            if not isinstance(threading.current_thread(), threading._MainThread):  # pylint: disable=W0212
                self._db.disconnect()
            return result

        return await get_event_loop().run_in_executor(None, _get_results)

    @db_session
    def get_entries(self, first=1, last=None, **kwargs):
        """
        Get some torrents. Optionally sort the results by a specific field, or filter the channels based
        on a keyword/whether you are subscribed to it.
        :return: A list of class members
        """
        pony_query = self.get_entries_query(**kwargs)
        return pony_query[(first or 1) - 1 : last]

    @db_session
    def get_total_count(self, **kwargs):
        """
        Get total count of torrents that would be returned if there would be no pagination/limits/sort
        """
        for p in ["first", "last", "sort_by", "sort_desc"]:
            kwargs.pop(p, None)
        return self.get_entries_query(**kwargs).count()

    @db_session
    def get_entries_count(self, **kwargs):
        for p in ["first", "last"]:
            kwargs.pop(p, None)
        return self.get_entries_query(**kwargs).count()

    @db_session
    def get_max_rowid(self):
        return select(max(obj.rowid) for obj in self.ChannelNode).get() or 0

    def get_auto_complete_terms(self, keyword, max_terms, limit=10):
        if not keyword:
            return []

        with db_session:
            result = self.search_keyword("\"" + keyword + "\"*", lim=limit)[:]
        titles = [g.title.lower() for g in result]

        # Copy-pasted from the old DBHandler (almost) completely
        all_terms = set()
        for line in titles:
            if len(all_terms) >= max_terms:
                break
            i1 = line.find(keyword)
            i2 = line.find(' ', i1 + len(keyword))
            term = line[i1:i2] if i2 >= 0 else line[i1:]
            if term != keyword:
                all_terms.add(term)
        return list(all_terms)
