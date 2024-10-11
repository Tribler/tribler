from __future__ import annotations

import enum
import logging
import re
import threading
from asyncio import get_running_loop
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from os.path import getsize
from pathlib import Path
from time import sleep, time
from typing import TYPE_CHECKING, Any, Callable

from lz4.frame import LZ4FrameDecompressor
from pony import orm
from pony.orm import Database, db_session, desc, left_join, raw_sql, select
from pony.orm.dbproviders.sqlite import keep_exception

from tribler.core.database.orm_bindings import misc, torrent_metadata, tracker_state
from tribler.core.database.orm_bindings import torrent_state as torrent_state_
from tribler.core.database.orm_bindings.torrent_metadata import NULL_KEY_SUBST
from tribler.core.database.ranks import torrent_rank
from tribler.core.database.serialization import (
    CHANNEL_TORRENT,
    COLLECTION_NODE,
    NULL_KEY,
    REGULAR_TORRENT,
    HealthItemsPayload,
    TorrentMetadataPayload,
    read_payload_with_offset,
)
from tribler.core.torrent_checker.dataclasses import HealthInfo

if TYPE_CHECKING:
    from sqlite3 import Connection

    from ipv8.types import PrivateKey
    from pony.orm.core import Entity, Query

    from tribler.core.database.layers.layer import EntityImpl
    from tribler.core.database.orm_bindings.torrent_metadata import TorrentMetadata
    from tribler.core.notifier import Notifier


class ObjState(enum.Enum):
    """
    Different states of information in the store.
    """

    UPDATED_LOCAL_VERSION = enum.auto()  # We updated the local version of the ORM object with the received one
    LOCAL_VERSION_NEWER = enum.auto()  # The local version of the ORM object is newer than the received one
    LOCAL_VERSION_SAME = enum.auto()  # The local version of the ORM object is the same as the received one
    NEW_OBJECT = enum.auto()  # The received object is unknown to us and thus added to ORM
    DUPLICATE_OBJECT = enum.auto()  # We already know about the received object


@dataclass
class ProcessingResult:
    """
    This class is used to return results of processing of a payload by process_payload.
    It includes the ORM object created as a result of processing, the state of the object
    as indicated by ObjState enum, and missing dependencies list that includes a list of query
    arguments for get_entries to query the sender back through Remote Query Community.
    """

    md_obj: EntityImpl
    obj_state: object
    missing_deps: list = field(default_factory=list)


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

sql_create_partial_index_torrentstate_last_check = """
    CREATE INDEX IF NOT EXISTS idx_torrentstate__last_check__partial
    ON TorrentState (last_check, seeders, leechers, self_checked)
    WHERE has_data = 1;
"""


class MetadataStore:
    """
    Storage of metadata for channels and torrents.
    """

    def __init__(
            self,
            db_filename: str,
            private_key: PrivateKey,
            disable_sync: bool = False,
            notifier: Notifier | None = None,
            check_tables: bool = True,
            db_version: int = CURRENT_DB_VERSION
    ) -> None:
        """
        Create a new metadata store.
        """
        self.notifier = notifier  # Reference to app-level notification service
        self.db_path = db_filename
        self.my_key = private_key
        self.my_public_key_bin = self.my_key.pub().key_to_bin()[10:]
        self._logger = logging.getLogger(self.__class__.__name__)

        self._shutting_down = False
        self.batch_size = 10  # reasonable number, a little bit more than typically fits in a single UDP packet
        self.reference_timedelta = timedelta(milliseconds=100)
        self.sleep_on_external_thread = 0.05  # sleep this amount of seconds between batches executed on external thread

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self.db = Database()

        # This attribute is internally called by Pony on startup, though pylint cannot detect it
        # with the static analysis.
        @self.db.on_connect
        def on_connect(_: Database, connection: Connection) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode = DELETE")
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

        self.MiscData = misc.define_binding(self.db)

        self.TrackerState = tracker_state.define_binding(self.db)
        self.TorrentState = torrent_state_.define_binding(self.db)
        self.TorrentMetadata = torrent_metadata.define_binding(
            self.db,
            notifier=notifier,
            tag_processor_version=0
        )

        if db_filename == ":memory:":
            create_db = True
            db_path_string = ":memory:"
        else:
            create_db = not Path(db_filename).exists()
            db_path_string = str(db_filename)

        self.db.bind(provider="sqlite", filename=db_path_string, create_db=create_db, timeout=120.0)
        self.db.generate_mapping(
            create_tables=create_db, check_tables=check_tables
        )  # Must be run out of session scope
        if create_db:
            with db_session(ddl=True):
                self.db.execute(sql_create_fts_table)
                self.create_fts_triggers()
                self.create_torrentstate_triggers()

        if create_db:
            with db_session:
                self.MiscData(name="db_version", value=str(db_version))

    def set_value(self, key: str, value: str) -> None:
        """
        Set a generic key to a value.
        """
        obj = self.MiscData.get_for_update(name=key) or self.MiscData(name=key)
        obj.value = value

    def get_value(self, key: str, default: str | None = None) -> str | None:
        """
        Retrieve the value for a given key.
        """
        data = self.MiscData.get(name=key)
        return data.value if data else default

    def drop_indexes(self) -> None:
        """
        Drop the indices for this database.
        """
        cursor = self.db.get_connection().cursor()
        cursor.execute("select name from sqlite_master where type='index' and name like 'idx_%'")
        for [index_name] in cursor.fetchall():
            cursor.execute(f"drop index {index_name}")

    def get_objects_to_create(self) -> list[Entity]:
        """
        Get the objects that need to be created.
        """
        connection = self.db.get_connection()
        schema = self.db.schema
        provider = schema.provider
        return [db_object for table in schema.order_tables_to_create()
                for db_object in table.get_objects_to_create(set())
                if not db_object.exists(provider, connection)]

    def get_db_file_size(self) -> int:
        """
        Get the physical size on disk (always 0 for memory dbs).
        """
        return 0 if self.db_path == ":memory:" else getsize(self.db_path)

    def drop_fts_triggers(self) -> None:
        """
        Drop the FTS triggers.
        """
        cursor = self.db.get_connection().cursor()
        cursor.execute("select name from sqlite_master where type='trigger' and name like 'fts_%'")
        for [trigger_name] in cursor.fetchall():
            cursor.execute(f"drop trigger {trigger_name}")

    def create_fts_triggers(self) -> None:
        """
        Create the FTS triggers.
        """
        cursor = self.db.get_connection().cursor()
        cursor.execute(sql_add_fts_trigger_insert)
        cursor.execute(sql_add_fts_trigger_delete)
        cursor.execute(sql_add_fts_trigger_update)

    def fill_fts_index(self) -> None:
        """
        Insert the FTS indices.
        """
        cursor = self.db.get_connection().cursor()
        cursor.execute("insert into FtsIndex(rowid, title) select rowid, title from ChannelNode")

    def create_torrentstate_triggers(self) -> None:
        """
        Create the torrent state triggers.
        """
        cursor = self.db.get_connection().cursor()
        cursor.execute(sql_add_torrentstate_trigger_after_insert)
        cursor.execute(sql_add_torrentstate_trigger_after_update)

    def shutdown(self) -> None:
        """
        Disconnect the connection to the database.
        """
        self._shutting_down = True
        self.db.disconnect()

    async def run_threaded(self, func: Callable, *args: Any, **kwargs) -> Any:  # noqa: ANN401
        """
        Run ``func`` threaded and close DB connection at the end of the execution.

        :param func: the function to be executed threaded
        :param args: args for the function call
        :param kwargs: kwargs for the function call
        :return: a result of the func call.
        """

        def wrapper():  # noqa: ANN202
            try:
                return func(*args, **kwargs)
            finally:
                is_main_thread = threading.current_thread() is threading.main_thread()
                if not is_main_thread:
                    self.db.disconnect()

        return await get_running_loop().run_in_executor(None, wrapper)

    async def process_compressed_mdblob_threaded(self, compressed_data: bytes, **kwargs) -> list[ProcessingResult]:
        """
        Decompress the given data in a thread and return a list of uncompressed results.
        """
        try:
            return await self.run_threaded(self.process_compressed_mdblob, compressed_data, **kwargs)
        except Exception as e:
            self._logger.exception("DB transaction error when tried to process compressed mdblob: %s: %s",
                                   e.__class__.__name__, str(e), exc_info=e)
            return []

    def process_compressed_mdblob(self, compressed_data: bytes,
                                  skip_personal_metadata_payload: bool = True) -> list[ProcessingResult]:
        """
        Decompress the given data and return a list of uncompressed results.
        """
        try:
            with LZ4FrameDecompressor() as decompressor:
                decompressed_data = decompressor.decompress(compressed_data)
                unused_data = decompressor.unused_data
        except RuntimeError as e:
            self._logger.warning("Unable to decompress mdblob: %s", str(e))
            return []

        health_info = None
        if unused_data:
            try:
                health_info = HealthItemsPayload.unpack(unused_data)
            except Exception as e:
                self._logger.warning("Unable to parse health information: %s: %s", type(e).__name__, str(e))
                raise

        return self.process_squashed_mdblob(decompressed_data, health_info=health_info,
                                            skip_personal_metadata_payload=skip_personal_metadata_payload)

    def process_torrent_health(self, health: HealthInfo) -> bool:
        """
        Adds or updates information about a torrent health for the torrent with the specified infohash value.

        :param health: a health info of a torrent
        :return: True if a new TorrentState object was added
        """
        if not health.is_valid():
            self._logger.warning("Invalid health info ignored: %s", str(health))
            return False

        torrent_state = self.TorrentState.get_for_update(infohash=health.infohash)

        if torrent_state and health.should_replace(torrent_state.to_health()):
            self._logger.debug("Update health info %s", str(health))
            torrent_state.set(seeders=health.seeders, leechers=health.leechers, last_check=health.last_check,
                              self_checked=False)
            return False

        if not torrent_state:
            self._logger.debug("Add health info %s", str(health))
            self.TorrentState.from_health(health)
            return True

        return False

    def process_squashed_mdblob(self, chunk_data: bytes, external_thread: bool = False,  # noqa: C901
                                health_info: list[tuple[int, int, int]] | None = None,
                                skip_personal_metadata_payload: bool = True) -> list[ProcessingResult]:
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
            if payload and isinstance(payload, TorrentMetadataPayload):
                # Silently ignore deprecated payloads
                payload_list.append(payload)

        if health_info and len(health_info) == len(payload_list):
            with db_session:
                for payload, (seeders, leechers, last_check) in zip(payload_list, health_info):
                    if hasattr(payload, "infohash"):
                        health = HealthInfo(payload.infohash, last_check=last_check,
                                            seeders=seeders, leechers=leechers)
                        self.process_torrent_health(health)

        result = []
        total_size = len(payload_list)
        start = 0
        while start < total_size:
            end = start + self.batch_size
            batch = payload_list[start:end]
            batch_start_time = datetime.now()  # noqa: DTZ005

            # We separate the sessions to minimize database locking.
            with db_session(immediate=True):
                for payload in batch:
                    result.extend(self.process_payload(payload, skip_personal_metadata_payload))

            # Batch size adjustment
            batch_end_time = datetime.now() - batch_start_time  # noqa: DTZ005
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
    def process_payload(self, payload: TorrentMetadataPayload,
                        skip_personal_metadata_payload: bool = True) -> list[ProcessingResult]:
        """
        Write a payload to our database (if necessary).
        """
        # Don't process our own torrents
        if skip_personal_metadata_payload and payload.public_key == self.my_public_key_bin:
            return []

        # Don't process unknown/deprecated payloads
        if payload.metadata_type != REGULAR_TORRENT:
            return []

        # Don't process torrents with a bad signature
        if payload.has_signature() and not payload.check_signature():
            return []

        # Process unsigned torrents
        if payload.public_key == NULL_KEY:
            node = self.TorrentMetadata.add_ffa_from_dict(payload.to_dict())
            return [ProcessingResult(md_obj=node, obj_state=ObjState.NEW_OBJECT)] if node else []

        # Do we already know about this object? In that case, we keep the first one (i.e., no versioning).
        node = self.TorrentMetadata.get_for_update(public_key=payload.public_key, id_=payload.id_)
        if node:
            return [ProcessingResult(md_obj=node, obj_state=ObjState.DUPLICATE_OBJECT)]

        # Process signed torrents
        obj = self.TorrentMetadata.from_payload(payload)
        return [ProcessingResult(md_obj=obj, obj_state=ObjState.NEW_OBJECT)]

    @db_session
    def get_num_torrents(self) -> int:
        """
        Get the number of torrents in the database.
        """
        return orm.count(self.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT))

    def search_keyword(self, query: str, origin_id: int | None = None) -> Query:
        """
        Search for an FTS query, potentially restricted to a given origin id.

        Requires FTS5 table "FtsIndex" to be generated and populated. FTS table is maintained automatically by SQL
        triggers. BM25 ranking is embedded in FTS5.
        """
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
        return left_join(g for g in self.TorrentMetadata if g.rowid in fts_ids)

    @db_session
    def get_entries_query(  # noqa: C901, PLR0913
            self,
            metadata_type: int | None = None,
            channel_pk: bytes | None = None,
            hide_xxx: bool = False,
            origin_id: int | None = None,
            sort_by: str | None = None,
            sort_desc: bool = True,
            max_rowid: int | None = None,
            txt_filter: str | None = None,
            category: str | None = None,
            infohash: bytes | None =None,
            infohash_set: set[bytes] | None = None,
            id_: int | None = None,
            self_checked_torrent: bool | None = None,
            health_checked_after: int | None = None,
            popular: bool | None = None,
            **kwargs
    ) -> Query:
        """
        This method implements REST-friendly way to get entries from the database.

        Warning! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere!

        :return: PonyORM query object corresponding to the given params.
        """
        if kwargs:
            self._logger.info("get_entries_query got ignored kwargs: %s", ", ".join(kwargs.keys()))

        if txt_filter:
            pony_query = self.search_keyword(txt_filter, origin_id=origin_id)
        elif popular:
            if metadata_type != REGULAR_TORRENT:
                msg = "With `popular=True`, only `metadata_type=REGULAR_TORRENT` is allowed"
                raise TypeError(msg)

            t = time() - POPULAR_TORRENTS_FRESHNESS_PERIOD
            return select(
                    g for g in self.TorrentMetadata
                    for health in self.TorrentState
                    if health.has_data == 1  # The condition had to be written this way for the partial index to work
                    and health.last_check >= t and (health.seeders > 0 or health.leechers > 0)
                    and g.health == health
                ).order_by(
                    lambda g: (desc(g.health.seeders), desc(g.health.leechers), desc(g.health.last_check))
                ).limit(POPULAR_TORRENTS_COUNT)
        else:
            pony_query = left_join(g for g in self.TorrentMetadata)

        infohash_set = infohash_set or ({infohash} if infohash else None)

        if max_rowid is not None:
            pony_query = pony_query.where(lambda g: g.rowid <= max_rowid)

        if metadata_type is not None:
            pony_query = pony_query.where(lambda g: g.metadata_type == metadata_type)

        pony_query = (
            pony_query.where(public_key=(b"" if channel_pk == NULL_KEY_SUBST else channel_pk))
            if channel_pk is not None
            else pony_query
        )

        # origin_id can be zero, for e.g. root channel
        pony_query = pony_query.where(id_=id_) if id_ is not None else pony_query
        pony_query = pony_query.where(origin_id=origin_id) if origin_id is not None else pony_query
        pony_query = pony_query.where(lambda g: g.tags == category) if category else pony_query
        pony_query = pony_query.where(lambda g: g.xxx == 0) if hide_xxx else pony_query
        pony_query = pony_query.where(lambda g: g.infohash in infohash_set) if infohash_set else pony_query
        pony_query = (
            pony_query.where(lambda g: g.health.self_checked == self_checked_torrent)
            if self_checked_torrent is not None
            else pony_query
        )

        if health_checked_after is not None:
            pony_query = pony_query.where(lambda g: g.health.has_data == 1  # Has to be written this way for index
                                          and g.health.last_check >= health_checked_after)

        # Sort the query
        pony_query = pony_query.sort_by("desc(g.rowid)" if sort_desc else "g.rowid")

        if sort_by == "HEALTH":
            pony_query = pony_query.sort_by(
                "(desc(g.health.seeders), desc(g.health.leechers))"
                if sort_desc
                else "(g.health.seeders, g.health.leechers)"
            )
        elif sort_by == "size":
            # Remark: this can be optimized to skip cases where size field does not matter
            # When querying for mixed channels / torrents lists, channels should have priority over torrents
            sort_expression = "desc(g.size)" if sort_desc else "g.size"
            pony_query = pony_query.sort_by(sort_expression)
        elif sort_by:
            sort_expression = raw_sql(f"g.{sort_by} COLLATE NOCASE" + (" DESC" if sort_desc else ""))
            pony_query = pony_query.sort_by(sort_expression)

        if sort_by is None and txt_filter:
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

        return pony_query

    async def get_entries_threaded(self, **kwargs) -> list[TorrentMetadata]:
        """
        Retrieve entries in a thread and return a list of results.
        """
        return await self.run_threaded(self.get_entries, **kwargs)

    @db_session
    def get_entries(self, first: int = 1, last: int | None = None, **kwargs) -> list[TorrentMetadata]:
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
    def get_total_count(self, **kwargs) -> int | None:
        """
        Get total count of torrents that would be returned if there would be no pagination/limits/sort.
        """
        for p in ["first", "last", "sort_by", "sort_desc"]:
            kwargs.pop(p, None)
        return self.get_entries_query(**kwargs).count()

    @db_session
    def get_entries_count(self, **kwargs) -> int | None:
        """
        Get the count of torrents that would be returned if there would be no pagination/limits.
        """
        for p in ["first", "last"]:
            kwargs.pop(p, None)
        return self.get_entries_query(**kwargs).count()

    @db_session
    def get_max_rowid(self) -> int:
        """
        Get the highest-known row id.
        """
        return select(max(obj.rowid) for obj in self.TorrentMetadata).get() or 0

    fts_keyword_search_re = re.compile(r'\w+', re.UNICODE)

    def get_auto_complete_terms(self, text: str, max_terms: int) -> list[str]:
        """
        Get the auto-completion terms for a given query.
        """
        if not text:
            return []

        words = self.fts_keyword_search_re.findall(text)
        if not words:
            return []

        fts_query = '"{}"*'.format(" ".join(f"{word}" for word in words))
        suggestion_pattern = r'\W+'.join(word for word in words) + r'(\W*)((?:[.-]?\w)*)'
        suggestion_re = re.compile(suggestion_pattern, re.UNICODE)

        with db_session:
            titles = self.db.select("""
                cn.title
                FROM ChannelNode cn
                LEFT JOIN TorrentState ts ON cn.health = ts.rowid
                WHERE cn.rowid in (
                    SELECT rowid FROM FtsIndex WHERE FtsIndex MATCH $fts_query ORDER BY rowid DESC LIMIT $max_terms
                )
                ORDER BY coalesce(ts.seeders, 0) DESC
            """, globals={"fts_query": fts_query, "max_terms": max_terms})

        result = []
        for title in titles:
            match = suggestion_re.search(title.lower())
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
