import logging
import threading
from asyncio import get_event_loop
from datetime import datetime, timedelta
from time import sleep

from ipv8.database import database_blob

import lz4.frame

from pony import orm
from pony.orm import CacheIndexError, TransactionIntegrityError, db_session

from tribler_common.simpledefs import NTFY

from tribler_core.exceptions import InvalidSignatureException
from tribler_core.modules.category_filter.l2_filter import is_forbidden
from tribler_core.modules.metadata_store.orm_bindings import (
    channel_metadata,
    channel_node,
    channel_peer,
    channel_vote,
    collection_node,
    metadata_node,
    misc,
    torrent_metadata,
    torrent_state,
    tracker_state,
    vsids,
)
from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import get_mdblob_sequence_number
from tribler_core.modules.metadata_store.orm_bindings.channel_node import LEGACY_ENTRY
from tribler_core.modules.metadata_store.serialization import (
    CHANNEL_TORRENT,
    COLLECTION_NODE,
    DELETED,
    NULL_KEY,
    REGULAR_TORRENT,
    read_payload_with_offset,
)
from tribler_core.utilities.path_util import str_path
from tribler_core.utilities.unicode import hexlify

BETA_DB_VERSIONS = [0, 1, 2, 3, 4, 5]
CURRENT_DB_VERSION = 11

NO_ACTION = 0
UNKNOWN_CHANNEL = 1
UPDATED_OUR_VERSION = 2
GOT_NEWER_VERSION = 4
UNKNOWN_TORRENT = 5
DELETED_METADATA = 6
UNKNOWN_COLLECTION = 7


MIN_BATCH_SIZE = 10
MAX_BATCH_SIZE = 1000


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


class MetadataStore:
    def __init__(
        self, db_filename, channels_dir, my_key, disable_sync=False, notifier=None, check_tables=True, db_version=None
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
        self.ChannelVote = channel_vote.define_binding(self._db)
        self.ChannelPeer = channel_peer.define_binding(self._db)
        self.Vsids = vsids.define_binding(self._db)

        self.ChannelMetadata._channels_dir = channels_dir

        self._db.bind(provider='sqlite', filename=str(db_filename), create_db=create_db, timeout=120.0)
        self._db.generate_mapping(
            create_tables=create_db, check_tables=check_tables
        )  # Must be run out of session scope
        if create_db:
            with db_session(ddl=True):
                self._db.execute(sql_create_fts_table)
                self.create_fts_triggers()

        if create_db:
            if db_version is None:
                db_version = CURRENT_DB_VERSION
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
            cursor.execute("drop index %s" % index_name)

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
            cursor.execute("drop trigger %s" % trigger_name)

    def create_fts_triggers(self):
        cursor = self._db.get_connection().cursor()
        cursor.execute(sql_add_fts_trigger_insert)
        cursor.execute(sql_add_fts_trigger_delete)
        cursor.execute(sql_add_fts_trigger_update)

    def fill_fts_index(self):
        cursor = self._db.get_connection().cursor()
        cursor.execute("insert into FtsIndex(rowid, title) select rowid, title from ChannelNode")

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
        # TODO: subclass ThreadPoolExecutor to handle this automatically
        if not isinstance(threading.current_thread(), threading._MainThread):
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
        # TODO: This procedure copy-pastes some stuff from process_channel_dir. Maybe DRY it somehow?
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
            return [(None, NO_ACTION)]

        if payload.metadata_type == DELETED:
            if payload.public_key == self.my_public_key_bin and skip_personal_metadata_payload:
                return [(None, NO_ACTION)]
            # We only allow people to delete their own entries, thus PKs must match
            node = self.ChannelNode.get_for_update(signature=payload.delete_signature, public_key=payload.public_key)
            if node:
                node.delete()
                return [(None, DELETED_METADATA)]

        if payload.metadata_type not in [CHANNEL_TORRENT, REGULAR_TORRENT, COLLECTION_NODE]:
            return []

        # Check for offending words stop-list
        if is_forbidden(payload.title + payload.tags):
            return [(None, NO_ACTION)]

        # FFA payloads get special treatment:
        if payload.public_key == NULL_KEY:
            if payload.metadata_type == REGULAR_TORRENT:
                node = self.TorrentMetadata.add_ffa_from_dict(payload.to_dict())
                if node:
                    return [(node, UNKNOWN_TORRENT)]
            return [(None, NO_ACTION)]

        if channel_public_key is None and payload.metadata_type in [COLLECTION_NODE, REGULAR_TORRENT]:
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
                    return [(None, NO_ACTION)]

        # Check for the older version of the added node
        node = self.ChannelNode.get_for_update(public_key=database_blob(payload.public_key), id_=payload.id_)
        if node:
            return self.update_channel_node(node, payload, skip_personal_metadata_payload)

        if payload.public_key == self.my_public_key_bin and skip_personal_metadata_payload:
            return [(None, NO_ACTION)]
        for orm_class, response in (
            (self.TorrentMetadata, UNKNOWN_TORRENT),
            (self.ChannelMetadata, UNKNOWN_CHANNEL),
            (self.CollectionNode, UNKNOWN_COLLECTION),
        ):
            if orm_class._discriminator_ == payload.metadata_type:
                return [(orm_class.from_payload(payload), response)]
        return []

    @db_session
    def update_channel_node(self, node, payload, skip_personal_metadata_payload=True):
        # The received metadata has newer version than the stuff we got, so we have to update our version.
        if node.timestamp < payload.timestamp:
            # If we received a metadata payload signed by ourselves we simply ignore it since we are the only
            # authoritative source of information about our own channel.
            if payload.public_key == self.my_public_key_bin and skip_personal_metadata_payload:
                return [(None, NO_ACTION)]

            # Update local metadata entry
            if node.metadata_type == payload.metadata_type:
                node.set(**payload.to_dict())
                return [(node, UPDATED_OUR_VERSION)]
            # Workaround for the corner case of remote change of md type.
            # We delete the original node and replace it with the updated one.
            for orm_class in (self.ChannelMetadata, self.CollectionNode):
                if orm_class._discriminator_ == payload.metadata_type:
                    node.delete()
                    return [(orm_class.from_payload(payload), UPDATED_OUR_VERSION)]
            self._logger.warning(
                f"Tried to update channel node to illegal type: "
                f" original type: {node.metadata_type}"
                f" updated type: {payload.metadata_type}"
                f" {hexlify(payload.public_key)}, {payload.id_} "
            )
            return [(None, NO_ACTION)]

        elif node.timestamp > payload.timestamp:
            return [(node, GOT_NEWER_VERSION)]
        # Otherwise, we got the same version locally and do nothing.
        # Nevertheless, it is important to indicate to upper levels that we recognised
        # the entry, for e.g. channel votes bumping
        return [(node, GOT_NEWER_VERSION)]

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
