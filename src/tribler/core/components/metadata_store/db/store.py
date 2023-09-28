import logging
import re
from datetime import datetime, timedelta
from time import sleep, time
from typing import Optional, Union

from lz4.frame import LZ4FrameDecompressor
from pony import orm
from pony.orm import db_session, desc, left_join, raw_sql, select
from pony.orm.dbproviders.sqlite import keep_exception

from tribler.core import notifications
from tribler.core.components.metadata_store.db.orm_bindings import (
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
    torrent_state as torrent_state_,
    tracker_state,
    vsids,
)
from tribler.core.components.metadata_store.db.orm_bindings.channel_metadata import get_mdblob_sequence_number
from tribler.core.components.metadata_store.db.orm_bindings.channel_node import LEGACY_ENTRY, TODELETE
from tribler.core.components.metadata_store.db.orm_bindings.torrent_metadata import NULL_KEY_SUBST
from tribler.core.components.metadata_store.db.serialization import (
    BINARY_NODE,
    CHANNEL_DESCRIPTION,
    CHANNEL_NODE,
    CHANNEL_THUMBNAIL,
    CHANNEL_TORRENT,
    COLLECTION_NODE,
    HealthItemsPayload,
    JSON_NODE,
    METADATA_NODE,
    REGULAR_TORRENT,
    read_payload_with_offset,
)
from tribler.core.components.metadata_store.remote_query_community.payload_checker import process_payload
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.exceptions import InvalidSignatureException
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.pony_utils import TrackedDatabase, get_max, get_or_create, run_threaded
from tribler.core.utilities.search_utils import torrent_rank
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import MEMORY_DB

BETA_DB_VERSIONS = [0, 1, 2, 3, 4, 5]
CURRENT_DB_VERSION = 15

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


class MetadataStore:
    def __init__(
            self,
            db_filename: Union[Path, type(MEMORY_DB)],
            channels_dir,
            my_key,
            disable_sync=False,
            notifier: Notifier = None,
            check_tables=True,
            db_version: int = CURRENT_DB_VERSION,
            tag_processor_version: int = 0
    ):
        self.notifier = notifier  # Reference to app-level notification service
        self.db_path = db_filename
        self.channels_dir = channels_dir
        self.my_key = my_key
        self.my_public_key_bin = self.my_key.pub().key_to_bin()[10:]
        self._logger = logging.getLogger(self.__class__.__name__)

        self._shutting_down = False
        self.batch_size = 10  # reasonable number, a little bit more than typically fits in a single UDP packet
        self.reference_timedelta = timedelta(milliseconds=100)
        self.sleep_on_external_thread = 0.05  # sleep this amount of seconds between batches executed on external thread

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self.db = TrackedDatabase()

        # This attribute is internally called by Pony on startup, though pylint cannot detect it
        # with the static analysis.
        # pylint: disable=unused-variable
        @self.db.on_connect(provider='sqlite')
        def on_connect(_, connection):
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

            sqlite_rank = keep_exception(torrent_rank)
            connection.create_function('search_rank', 5, sqlite_rank)

            # pylint: enable=unused-variable

        self.MiscData = misc.define_binding(self.db)

        self.TrackerState = tracker_state.define_binding(self.db)
        self.TorrentState = torrent_state_.define_binding(self.db)

        self.ChannelNode = channel_node.define_binding(self.db, logger=self._logger, key=my_key)

        self.MetadataNode = metadata_node.define_binding(self.db)
        self.CollectionNode = collection_node.define_binding(self.db)
        self.TorrentMetadata = torrent_metadata.define_binding(
            self.db,
            notifier=notifier,
            tag_processor_version=tag_processor_version
        )
        self.ChannelMetadata = channel_metadata.define_binding(self.db)

        self.JsonNode = json_node.define_binding(self.db, db_version)
        self.ChannelDescription = channel_description.define_binding(self.db)

        self.BinaryNode = binary_node.define_binding(self.db, db_version)
        self.ChannelThumbnail = channel_thumbnail.define_binding(self.db)

        self.ChannelVote = channel_vote.define_binding(self.db)
        self.ChannelPeer = channel_peer.define_binding(self.db)
        self.Vsids = vsids.define_binding(self.db)

        self.ChannelMetadata._channels_dir = channels_dir  # pylint: disable=protected-access

        if db_filename is MEMORY_DB:
            create_db = True
            db_path_string = ":memory:"
        else:
            create_db = not db_filename.is_file()
            db_path_string = str(db_filename)

        self.db.bind(provider='sqlite', filename=db_path_string, create_db=create_db, timeout=120.0)
        self.db.generate_mapping(
            create_tables=create_db, check_tables=check_tables
        )  # Must be run out of session scope
        if create_db:
            with db_session(ddl=True):
                self.db.execute(sql_create_fts_table)
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

    def set_value(self, key: str, value: str):
        key_value = get_or_create(self.MiscData, name=key)
        key_value.value = value

    def get_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        data = self.MiscData.get(name=key)
        return data.value if data else default

    def drop_indexes(self):
        cursor = self.db.get_connection().cursor()
        cursor.execute("select name from sqlite_master where type='index' and name like 'idx_%'")
        for [index_name] in cursor.fetchall():
            cursor.execute(f"drop index {index_name}")

    def get_objects_to_create(self):
        connection = self.db.get_connection()
        schema = self.db.schema
        provider = schema.provider
        created_tables = set()
        result = []
        for table in schema.order_tables_to_create():
            for db_object in table.get_objects_to_create(created_tables):
                if not db_object.exists(provider, connection):
                    result.append(db_object)
        return result

    def get_db_file_size(self):
        return 0 if self.db_path is MEMORY_DB else Path(self.db_path).size()

    def drop_fts_triggers(self):
        cursor = self.db.get_connection().cursor()
        cursor.execute("select name from sqlite_master where type='trigger' and name like 'fts_%'")
        for [trigger_name] in cursor.fetchall():
            cursor.execute(f"drop trigger {trigger_name}")

    def create_fts_triggers(self):
        cursor = self.db.get_connection().cursor()
        cursor.execute(sql_add_fts_trigger_insert)
        cursor.execute(sql_add_fts_trigger_delete)
        cursor.execute(sql_add_fts_trigger_update)

    def fill_fts_index(self):
        cursor = self.db.get_connection().cursor()
        cursor.execute("insert into FtsIndex(rowid, title) select rowid, title from ChannelNode")

    def create_torrentstate_triggers(self):
        cursor = self.db.get_connection().cursor()
        cursor.execute(sql_add_torrentstate_trigger_after_insert)
        cursor.execute(sql_add_torrentstate_trigger_after_update)

    def create_partial_indexes(self):
        cursor = self.db.get_connection().cursor()
        cursor.execute(sql_create_partial_index_channelnode_subscribed)
        cursor.execute(sql_create_partial_index_channelnode_metadata_type)

    @db_session
    def upsert_vote(self, channel, peer_pk):
        voter = self.ChannelPeer.get_for_update(public_key=peer_pk)
        if not voter:
            voter = self.ChannelPeer(public_key=peer_pk)
        vote = self.ChannelVote.get_for_update(voter=voter, channel=channel)
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
        self.db.disconnect()

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
                        self.notifier[notifications.channel_entity_updated](channel_update_dict)
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
        path = Path.fix_win_long_file(filepath)
        with open(path, 'rb') as f:
            serialized_data = f.read()

        if path.endswith('.lz4'):
            return self.process_compressed_mdblob(serialized_data, **kwargs)
        return self.process_squashed_mdblob(serialized_data, **kwargs)

    async def process_compressed_mdblob_threaded(self, compressed_data, **kwargs):
        try:
            return await run_threaded(self.db, self.process_compressed_mdblob, compressed_data, **kwargs)
        except Exception as e:  # pylint: disable=broad-except  # pragma: no cover
            self._logger.warning("DB transaction error when tried to process compressed mdblob: %s", str(e))
            return None

    def process_compressed_mdblob(self, compressed_data, **kwargs):
        try:
            with LZ4FrameDecompressor() as decompressor:
                decompressed_data = decompressor.decompress(compressed_data)
                unused_data = decompressor.unused_data
        except RuntimeError as e:
            self._logger.warning(f"Unable to decompress mdblob: {str(e)}")
            return []

        health_info = None
        if unused_data:
            try:
                health_info = HealthItemsPayload.unpack(unused_data)
            except Exception as e:  # pylint: disable=broad-except  # pragma: no cover
                self._logger.warning(f"Unable to parse health information: {type(e).__name__}: {str(e)}")

        return self.process_squashed_mdblob(decompressed_data, health_info=health_info, **kwargs)

    def process_torrent_health(self, health: HealthInfo) -> bool:
        """
        Adds or updates information about a torrent health for the torrent with the specified infohash value
        :param health: a health info of a torrent
        :return: True if a new TorrentState object was added
        """
        if not health.is_valid():
            self._logger.warning(f'Invalid health info ignored: {health}')
            return False

        torrent_state = self.TorrentState.get_for_update(infohash=health.infohash)

        if torrent_state and health.should_replace(torrent_state.to_health()):
            self._logger.debug(f"Update health info {health}")
            torrent_state.set(seeders=health.seeders, leechers=health.leechers, last_check=health.last_check,
                              self_checked=False)
            return False

        if not torrent_state:
            self._logger.debug(f"Add health info {health}")
            self.TorrentState.from_health(health)
            return True

        return False

    def process_squashed_mdblob(self, chunk_data, external_thread=False, health_info=None, **kwargs):
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

        if health_info and len(health_info) == len(payload_list):
            with db_session:
                for payload, (seeders, leechers, last_check) in zip(payload_list, health_info):
                    if hasattr(payload, 'infohash'):
                        health = HealthInfo(payload.infohash, last_check=last_check,
                                            seeders=seeders, leechers=leechers)
                        self.process_torrent_health(health)

        result = []
        total_size = len(payload_list)
        start = 0
        while start < total_size:
            end = start + self.batch_size
            batch = payload_list[start:end]
            batch_start_time = datetime.now()

            # We separate the sessions to minimize database locking.
            with db_session(immediate=True):
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
    def process_payload(self, payload, **kwargs):
        return process_payload(self, payload, **kwargs)

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
            lambda g: g.public_key == self.my_public_key_bin and g.infohash == infohash and g.status != LEGACY_ENTRY
        )

    # pylint: disable=unused-argument
    def search_keyword(self, query, origin_id=None):
        # Requires FTS5 table "FtsIndex" to be generated and populated.
        # FTS table is maintained automatically by SQL triggers.
        # BM25 ranking is embedded in FTS5.

        # Sanitize FTS query
        if not query or query == "*":
            return []

        if origin_id is not None:
            # When filtering a specific channel folder, we want to return all matching results
            fts_ids = raw_sql("""
                SELECT rowid FROM ChannelNode
                WHERE origin_id = $origin_id
                  AND rowid IN (SELECT rowid FROM FtsIndex WHERE FtsIndex MATCH $query)
            """)
        else:
            # When searching through an entire database for some text queries, the database can contain hundreds
            # of thousands of matching torrents. The ranking of this number of torrents may be very expensive: we need
            # to retrieve each matching torrent info and the torrent state from the database for proper ordering.
            # They are scattered randomly through the entire database file, so fetching all these torrents is slow.
            # Also, the torrent_rank function used inside the final ORDER BY section is written in Python. It is about
            # 30 times slower than a possible similar function written in C due to SQLite-Python communication cost.
            #
            # To speed up the query, we limit and filter search results in several iterations, and each time apply
            # a more expensive ranking algorithm:
            #   * First, we quickly fetch at most 10000 of the most recent torrents that match the search criteria
            #     and ignore older torrents. This way, we avoid sorting all hundreds of thousands of matching torrents
            #     in degenerative cases. In typical cases, when the text query is specific enough, the number of
            #     matching torrents is not that big.
            #   * Then, we sort these 10000 torrents to prioritize torrents with seeders and restrict the number
            #     of torrents to just 1000.
            #   * Finally, in the main query, we apply a slow ranking function to these 1000 torrents to show the most
            #     relevant torrents at the top of the search result list.
            #
            # This multistep sort+limit sequence allows speedup queries up to two orders of magnitude. To further
            # speed up full-text search queries, we can rewrite the torrent_rank function to C one day.
            fts_ids = raw_sql("""
                SELECT fts.rowid
                FROM (
                    SELECT rowid FROM FtsIndex WHERE FtsIndex MATCH $query ORDER BY rowid DESC LIMIT 10000
                ) fts
                LEFT JOIN ChannelNode cn on fts.rowid = cn.rowid
                LEFT JOIN main.TorrentState ts on cn.health = ts.rowid
                ORDER BY coalesce(ts.seeders, 0) DESC, fts.rowid DESC  
                LIMIT 1000
            """)
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
            infohash_set=None,
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

        if txt_filter:
            pony_query = self.search_keyword(txt_filter, origin_id=origin_id)
        else:
            pony_query = left_join(g for g in cls)

        infohash_set = infohash_set or ({infohash} if infohash else None)
        if popular:
            if metadata_type != REGULAR_TORRENT:
                raise TypeError('With `popular=True`, only `metadata_type=REGULAR_TORRENT` is allowed')

            t = time() - POPULAR_TORRENTS_FRESHNESS_PERIOD
            health_list = list(
                select(
                    health
                    for health in self.TorrentState
                    if health.last_check >= t and (health.seeders > 0 or health.leechers > 0)
                ).order_by(
                    lambda health: (desc(health.seeders), desc(health.leechers), desc(health.last_check))
                )[:POPULAR_TORRENTS_COUNT]
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
        pony_query = pony_query.where(lambda g: g.infohash in infohash_set) if infohash_set else pony_query
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
            sort_expression = raw_sql(f"g.{sort_by} COLLATE NOCASE" + (" DESC" if sort_desc else ""))
            pony_query = pony_query.sort_by(sort_expression)

        if sort_by is None:
            if txt_filter:
                # pylint: disable=W0105
                """
                The following call of `sort_by` produces an ORDER BY expression that looks like this:

                ORDER BY
                    case when "g"."metadata_type" = $CHANNEL_TORRENT then 1
                         when "g"."metadata_type" = $COLLECTION_NODE then 2
                         else 3 end,

                    search_rank(
                        $QUERY_STRING,
                        g.title,
                        torrentstate.seeders,
                        torrentstate.leechers,
                        $CURRENT_TIME - strftime('%s', g.torrent_date)
                    ) DESC,

                    "torrentstate"."last_check" DESC,

                So, the channel torrents and channel folders are always on top if they are not filtered out.
                Then regular torrents are selected in order of their relevance according to a search_rank() result.
                If two torrents have the same search rank, they are ordered by the last time they were checked.

                The search_rank() function is called directly from the SQLite query, but is implemented in Python,
                it is actually the torrent_rank() function from core/utilities/search_utils.py, wrapped with
                keep_exception() to return possible exception from SQLite to Python.

                The search_rank() function receives the following arguments:
                  - the current query string (like "Big Buck Bunny");
                  - the title of the current torrent;
                  - the number of seeders;
                  - the number of leechers;
                  - the number of seconds since the torrent's creation time.
                """

                pony_query = pony_query.sort_by(
                    f"""
                    (1 if g.metadata_type == {CHANNEL_TORRENT} else 2 if g.metadata_type == {COLLECTION_NODE} else 3),
                    raw_sql('''search_rank(
                        $txt_filter, g.title, torrentstate.seeders, torrentstate.leechers,
                        $int(time()) - strftime('%s', g.torrent_date)
                    ) DESC'''),
                    desc(g.health.last_check)  # just to trigger the TorrentState table inclusion into the left join
                """
                )
            elif popular:
                pony_query = pony_query.sort_by('(desc(g.health.seeders), desc(g.health.leechers))')

        return pony_query

    async def get_entries_threaded(self, **kwargs):
        return await run_threaded(self.db, self.get_entries, **kwargs)

    @db_session
    def get_entries(self, first=1, last=None, **kwargs):
        """
        Get some torrents. Optionally sort the results by a specific field, or filter the channels based
        on a keyword/whether you are subscribed to it.
        :return: A list of class members
        """
        pony_query = self.get_entries_query(**kwargs)
        result = pony_query[(first or 1) - 1: last]
        for entry in result:
            # ACHTUNG! This is necessary in order to load entry.health inside db_session,
            # to be able to perform successfully `entry.to_simple_dict()` later
            entry.to_simple_dict()
        return result

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
    def get_max_rowid(self) -> int:
        return get_max(self.ChannelNode)

    fts_keyword_search_re = re.compile(r'\w+', re.UNICODE)

    def get_auto_complete_terms(self, text, max_terms, limit=200):
        if not text:
            return []

        words = self.fts_keyword_search_re.findall(text)
        if not words:
            return ""

        fts_query = '"%s"*' % ' '.join(f'{word}' for word in words)  # pylint: disable=unused-variable
        suggestion_pattern = r'\W+'.join(word for word in words) + r'(\W*)((?:[.-]?\w)*)'
        suggestion_re = re.compile(suggestion_pattern, re.UNICODE)

        with db_session:
            titles = self.db.select("""
                cn.title
                FROM ChannelNode cn
                LEFT JOIN TorrentState ts ON cn.health = ts.rowid
                WHERE cn.rowid in (
                    SELECT rowid FROM FtsIndex WHERE FtsIndex MATCH $fts_query ORDER BY rowid DESC LIMIT $limit
                )
                ORDER BY coalesce(ts.seeders, 0) DESC
            """)

        result = []
        for title in titles:
            title = title.lower()
            match = suggestion_re.search(title)
            if match:
                # group(2) is the ending of the last word (if the word is not finished) or the next word
                continuation = match.group(2)
                if re.match(r'^.*\w$', text) and match.group(1):  # group(1) is non-word symbols (spaces, commas, etc.)
                    continuation = match.group(1) + continuation
                suggestion = text + continuation
                if suggestion not in result:
                    result.append(suggestion)
                    if len(result) >= max_terms:
                        break

        return result
