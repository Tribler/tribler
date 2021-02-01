import base64
import contextlib
import datetime
import logging
import os
import sqlite3
from asyncio import sleep
from pathlib import Path

from pony import orm
from pony.orm import db_session

from tribler_core.modules.category_filter.l2_filter import is_forbidden
from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import BLOB_EXTENSION
from tribler_core.modules.metadata_store.orm_bindings.channel_node import LEGACY_ENTRY, NEW
from tribler_core.modules.metadata_store.orm_bindings.torrent_metadata import infohash_to_id
from tribler_core.modules.metadata_store.serialization import REGULAR_TORRENT, int2time, time2int
from tribler_core.modules.metadata_store.store import BETA_DB_VERSIONS, CURRENT_DB_VERSION
from tribler_core.utilities.path_util import str_path
from tribler_core.utilities.tracker_utils import get_uniformed_tracker_url

DISCOVERED_CONVERSION_STARTED = "discovered_conversion_started"
CHANNELS_CONVERSION_STARTED = "channels_conversion_started"
TRACKERS_CONVERSION_STARTED = "trackers_conversion_started"
PERSONAL_CONVERSION_STARTED = "personal_conversion_started"

CONVERSION_STARTED = "conversion_started"
CONVERSION_FINISHED = "conversion_finished"

CONVERSION_FROM_72 = "conversion_from_72"
CONVERSION_FROM_72_PERSONAL = "conversion_from_72_personal"
CONVERSION_FROM_72_DISCOVERED = "conversion_from_72_discovered"
CONVERSION_FROM_72_CHANNELS = "conversion_from_72_channels"


def final_timestamp():
    return 1 << 62


class DispersyToPonyMigration:
    select_channels_sql = (
        "SELECT id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam "
        "FROM Channels "
        "WHERE nr_torrents >= 3 "
        "AND name not NULL;"
    )
    select_trackers_sql = "SELECT tracker_id, tracker, last_check, failures, is_alive FROM TrackerInfo"

    select_full = (
        "SELECT"
        " (SELECT ti.tracker FROM TorrentTrackerMapping ttm, TrackerInfo ti WHERE "
        "ttm.torrent_id == t.torrent_id AND ttm.tracker_id == ti.tracker_id AND ti.tracker != 'DHT' "
        "AND ti.tracker != 'http://retracker.local/announce' ORDER BY ti.is_alive ASC, ti.failures DESC, "
        "ti.last_check ASC), chs.dispersy_cid, ct.name, t.infohash, t.length, t.creation_date, "
        "t.torrent_id, t.category, t.num_seeders, t.num_leechers, t.last_tracker_check "
        "FROM _ChannelTorrents ct, Torrent t, Channels chs WHERE ct.name NOT NULL and t.length > 0 AND "
        "t.category NOT NULL AND ct.deleted_at IS NULL AND t.torrent_id == ct.torrent_id AND "
        "t.infohash NOT NULL AND ct.channel_id == chs.id"
    )
    select_torrents_sql = (
        "FROM _ChannelTorrents ct, Torrent t WHERE "
        "ct.name NOT NULL and t.length>0 AND t.category NOT NULL AND ct.deleted_at IS NULL "
        " AND t.torrent_id == ct.torrent_id AND t.infohash NOT NULL"
    )

    def __init__(self, tribler_db, notifier_callback=None, logger=None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self.notifier_callback = notifier_callback
        self.tribler_db = tribler_db
        self.mds = None
        self.shutting_down = False
        self.conversion_start_timestamp_int = time2int(datetime.datetime.utcnow())

        self.personal_channel_id = None
        self.personal_channel_title = None

    def initialize(self, mds):
        self.mds = mds
        try:
            self.personal_channel_id, self.personal_channel_title = self.get_personal_channel_id_title()
            self.personal_channel_title = self.personal_channel_title[:200]  # limit the title size
        except:
            self._logger.info("No personal channel found")

    def get_old_channels(self):
        with contextlib.closing(sqlite3.connect(self.tribler_db)) as connection, connection:
            cursor = connection.cursor()

            channels = []
            for id_, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam in cursor.execute(
                    self.select_channels_sql):
                if nr_torrents and nr_torrents > 0:
                    channels.append({"id_": infohash_to_id(dispersy_cid),
                                     "infohash": bytes(dispersy_cid),
                                     "title": name or '',
                                     "public_key": b"",
                                     "timestamp": final_timestamp(),
                                     "origin_id": 0,
                                     "size": 0,
                                     "subscribed": False,
                                     "status": LEGACY_ENTRY,
                                     "votes": -1,
                                     "num_entries": int(nr_torrents or 0)})
        return channels

    def get_personal_channel_id_title(self):
        with contextlib.closing(sqlite3.connect(self.tribler_db)) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT id,name FROM Channels WHERE peer_id ISNULL LIMIT 1')
            result = cursor.fetchone()
        return result

    def get_old_trackers(self):
        with contextlib.closing(sqlite3.connect(self.tribler_db)) as connection, connection:
            cursor = connection.cursor()

            trackers = {}
            for tracker_id, tracker, last_check, failures, is_alive in cursor.execute(self.select_trackers_sql):
                try:
                    tracker_url_sanitized = get_uniformed_tracker_url(tracker)
                    if not tracker_url_sanitized:
                        continue
                except Exception as e:
                    self._logger.warning("Encountered malformed tracker: %s", e)
                    # Skip malformed trackers
                    continue
                trackers[tracker_url_sanitized] = ({
                    "last_check": last_check,
                    "failures": failures,
                    "alive": is_alive})
        return trackers

    def get_old_torrents_count(self, personal_channel_only=False):
        personal_channel_filter = ""
        if self.personal_channel_id:
            equality_sign = " == " if personal_channel_only else " != "
            personal_channel_filter = f"AND ct.channel_id {equality_sign} {self.personal_channel_id}"

        command = (
            f"SELECT COUNT(*) FROM (SELECT t.torrent_id {self.select_torrents_sql} {personal_channel_filter} "
            "group by infohash )"
        )
        with contextlib.closing(sqlite3.connect(self.tribler_db)) as connection, connection:
            cursor = connection.cursor()
            cursor.execute(command)
            result = cursor.fetchone()[0]
        return result

    def get_personal_channel_torrents_count(self):
        command = (
            f"SELECT COUNT(*) FROM (SELECT t.torrent_id {self.select_torrents_sql} "
            f"AND ct.channel_id == {self.personal_channel_id} group by infohash )"
        )
        with contextlib.closing(sqlite3.connect(self.tribler_db)) as connection, connection:
            cursor = connection.cursor()
            cursor.execute(command)
            result = cursor.fetchone()[0]
        return result

    def get_old_torrents(self, personal_channel_only=False, batch_size=10000, offset=0,
                         sign=False):
        with contextlib.closing(sqlite3.connect(self.tribler_db)) as connection, connection:
            cursor = connection.cursor()
            cursor.execute("PRAGMA temp_store = 2")

            personal_channel_filter = ""
            if self.personal_channel_id:
                equality_sign = " == " if personal_channel_only else " != "
                personal_channel_filter = f"AND ct.channel_id {equality_sign} {self.personal_channel_id}"

            torrents = []
            batch_not_empty = False # This is a dumb way to indicate that this batch got zero entries from DB

            for tracker_url, channel_id, name, infohash, length, creation_date, torrent_id, category, num_seeders, \
                num_leechers, last_tracker_check in cursor.execute(
                        f"{self.select_full} {personal_channel_filter} group by infohash "
                        f"LIMIT {batch_size} OFFSET {offset}"
            ):
                batch_not_empty = True
                # check if name is valid unicode data
                try:
                    name = str(name)
                except UnicodeDecodeError:
                    continue

                try:
                    invalid_decoding = len(base64.decodebytes(infohash.encode('utf-8'))) != 20
                    invalid_id = not torrent_id or int(torrent_id) == 0
                    invalid_length = not length or (int(length) <= 0) or (int(length) > (1 << 45))
                    invalid_name = not name or is_forbidden(name)
                    if invalid_decoding or invalid_id or invalid_length or invalid_name:
                        continue

                    infohash = base64.decodebytes(infohash.encode())

                    torrent_date = datetime.datetime.utcfromtimestamp(creation_date or 0)
                    torrent_date = torrent_date if 0 <= time2int(torrent_date) <= self.conversion_start_timestamp_int \
                        else int2time(0)
                    torrent_dict = {
                        "status": NEW,
                        "infohash": infohash,
                        "size": int(length),
                        "torrent_date": torrent_date,
                        "title": name or '',
                        "tags": category or '',
                        "tracker_info": tracker_url or '',
                        "xxx": int(category == 'xxx')}
                    if not sign:
                        torrent_dict.update({"origin_id": infohash_to_id(channel_id)})
                    seeders = int(num_seeders or 0)
                    leechers = int(num_leechers or 0)
                    last_tracker_check = int(last_tracker_check or 0)
                    health_dict = {
                        "seeders": seeders,
                        "leechers": leechers,
                        "last_check": last_tracker_check
                    } if (last_tracker_check >= 0 and seeders >= 0 and leechers >= 0) else None
                    torrents.append((torrent_dict, health_dict))
                except Exception as e:
                    self._logger.warning("During retrieval of old torrents an exception was raised: %s", e)
                    continue

        return torrents if batch_not_empty else None

    async def convert_personal_channel(self):
        with db_session:
            # Reflect conversion state
            v = self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_PERSONAL)
            if v:
                if v.value == CONVERSION_STARTED:
                    # Just drop the entries from the previous try
                    my_channels = self.mds.ChannelMetadata.get_my_channels()
                    for my_channel in my_channels:
                        my_channel.contents.delete(bulk=True)
                        my_channel.delete()
                else:
                    # Something is wrong, this should never happen
                    raise Exception("Previous conversion resulted in invalid state")
            else:
                self.mds.MiscData(name=CONVERSION_FROM_72_PERSONAL, value=CONVERSION_STARTED)
            my_channels_count = self.mds.ChannelMetadata.get_my_channels().count()

        # Make sure every precondition is met
        if self.personal_channel_id and not my_channels_count:
            total_to_convert = self.get_personal_channel_torrents_count()

            with db_session:
                my_channel = self.mds.ChannelMetadata.create_channel(title=self.personal_channel_title, description='')

            def get_old_stuff(batch_size, offset):
                return self.get_old_torrents(personal_channel_only=True, sign=True,
                                             batch_size=batch_size, offset=offset)

            def add_to_pony(t):
                return self.mds.TorrentMetadata(origin_id=my_channel.id_, **t)

            await self.convert_async(add_to_pony, get_old_stuff, total_to_convert,
                                     offset=0, message="Converting personal channel torrents.")

            with db_session:
                my_channel = self.mds.ChannelMetadata.get_my_channels().first()
                folder = Path(my_channel._channels_dir) / my_channel.dirname

                # We check if we need to re-create the channel dir in case it was deleted for some reason
                if not folder.is_dir():
                    os.makedirs(str_path(folder))
                for filename in os.listdir(folder):
                    file_path = folder / filename
                    # We only remove mdblobs and leave the rest as it is
                    if filename.endswith(BLOB_EXTENSION) or filename.endswith(BLOB_EXTENSION + '.lz4'):
                        os.unlink(str_path(file_path))
                my_channel.commit_channel_torrent()

        with db_session:
            v = self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_PERSONAL)
            v.value = CONVERSION_FINISHED

    async def update_convert_total(self, amount, elapsed):
        if self.notifier_callback:
            elapsed = 0.0001 if elapsed == 0.0 else elapsed
            self.notifier_callback(
                f"{amount} entries converted in {int(elapsed)} seconds ({amount // elapsed} e/s)"
            )
            await sleep(0.001)

    async def update_convert_progress(self, amount, total, elapsed, message=""):
        if self.notifier_callback:
            elapsed = 0.0001 if elapsed == 0.0 else elapsed
            amount = amount or 1
            est_speed = amount / elapsed
            eta = str(datetime.timedelta(seconds=int((total - amount) / est_speed)))
            self.notifier_callback(
                f"{message}\nConverted: {amount}/{total} ({(amount * 100) // total}).\nTime remaining: {eta}"
            )
            await sleep(0.001)

    async def convert_async(self, add_to_pony, get_old_stuff, total_to_convert, offset=0, message=""):
        """
        This method converts old stuff into the pony database splitting the process into chunks dynamically.
        Chunks splitting uses congestion-control-like algorithm. Yields are necessary so the
        reactor can get an opportunity at serving other tasks, such as sending progress notifications to
        the GUI through the REST API.
        This method is made semi-general, so it is possible to use it as a wrapper for actual conversion
        routines for both personal and non-personal channels.
        """
        start_time = datetime.datetime.utcnow()
        batch_size = 100

        reference_timedelta = datetime.timedelta(milliseconds=1000)
        start = 0 + offset
        elapsed = 1
        while start < total_to_convert:
            batch = get_old_stuff(batch_size=batch_size, offset=start)

            if batch is None or self.shutting_down:
                break

            end = start + batch_size

            batch_start_time = datetime.datetime.now()
            with db_session:
                for (torrent_dict, health) in batch:
                    try:
                        torrent = add_to_pony(torrent_dict)
                        if torrent and health:
                            torrent.health.set(**health)
                    except:
                        self._logger.warning("Error while converting torrent entry: %s %s", torrent_dict, health)
            batch_end_time = datetime.datetime.now() - batch_start_time

            elapsed = (datetime.datetime.utcnow() - start_time).total_seconds()
            await self.update_convert_progress(start, total_to_convert, elapsed, message)
            target_coeff = (batch_end_time.total_seconds() / reference_timedelta.total_seconds())
            if len(batch) == batch_size:
                # Adjust batch size only for full batches
                if target_coeff < 0.8:
                    batch_size += batch_size
                elif target_coeff > 1.1:
                    batch_size = int(float(batch_size) / target_coeff)
                # we want to guarantee that at least some entries will go through
                batch_size = batch_size if batch_size > 10 else 10
            self._logger.info("Converted: %i/%i %f ",
                              start + batch_size, total_to_convert, float(batch_end_time.total_seconds()))
            start = end

        await self.update_convert_total(start, elapsed)

    async def convert_discovered_torrents(self):
        offset = 0
        # Reflect conversion state
        with db_session:
            v = self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_DISCOVERED)
            if v:
                offset = orm.count(
                    g for g in self.mds.TorrentMetadata if
                    g.status == LEGACY_ENTRY and g.metadata_type == REGULAR_TORRENT)
                v.set(value=CONVERSION_STARTED)
            else:
                self.mds.MiscData(name=CONVERSION_FROM_72_DISCOVERED, value=CONVERSION_STARTED)

        await self.convert_async(self.mds.TorrentMetadata.add_ffa_from_dict,
                                 self.get_old_torrents,
                                 self.get_old_torrents_count(),
                                 offset=offset,
                                 message="Converting old torrents.")

        with db_session:
            v = self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_DISCOVERED)
            v.value = CONVERSION_FINISHED

    def convert_discovered_channels(self):
        # Reflect conversion state
        with db_session:
            v = self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_CHANNELS)
            if v:
                if v.value == CONVERSION_STARTED:
                    # Just drop the entries from the previous try
                    orm.delete(g for g in self.mds.ChannelMetadata if g.status == LEGACY_ENTRY)
                else:
                    v.set(value=CONVERSION_STARTED)
            else:
                self.mds.MiscData(name=CONVERSION_FROM_72_CHANNELS, value=CONVERSION_STARTED)

        old_channels = self.get_old_channels()
        # We break it up into separate sessions and add sleep because this is going to be executed
        # on a background thread and we do not want to hold the DB lock for too long
        with db_session:
            for c in old_channels:
                if self.shutting_down:
                    break
                try:
                    self.mds.ChannelMetadata(**c)
                except:
                    continue

        with db_session:
            for c in self.mds.ChannelMetadata.select().for_update()[:]:
                contents_len = c.contents_len
                title = c.title
                if is_forbidden(title):
                    c.delete()
                elif contents_len:
                    c.num_entries = contents_len
                else:
                    c.delete()

        with db_session:
            v = self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_CHANNELS)
            v.value = CONVERSION_FINISHED

    def update_trackers_info(self):
        old_trackers = self.get_old_trackers()
        with db_session:
            trackers = self.mds.TrackerState.select().for_update()[:]
            for tracker in trackers:
                if tracker.url in old_trackers:
                    tracker.set(**old_trackers[tracker.url])

    def mark_conversion_finished(self):
        with db_session:
            v = self.mds.MiscData.get(name=CONVERSION_FROM_72)
            if v:
                v.set(value=CONVERSION_FINISHED)
            else:
                self.mds.MiscData(name=CONVERSION_FROM_72, value=CONVERSION_FINISHED)

    async def do_migration(self):
        await self.convert_personal_channel()
        self.mds.clock = None  # We should never touch the clock during legacy conversions
        await self.convert_discovered_torrents()
        self.convert_discovered_channels()
        self.update_trackers_info()
        self.mark_conversion_finished()


def old_db_version_ok(old_database_path):
    # Check the old DB version
    with contextlib.closing(sqlite3.connect(old_database_path)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute('SELECT value FROM MyInfo WHERE entry == "version"')
        version = int(cursor.fetchone()[0])
    return True if version == 29 else False


def cleanup_pony_experimental_db(new_database_path):
    # Check for the old experimental version database
    # ACHTUNG!!! NUCLEAR OPTION!!! DO NOT MESS WITH IT!!!
    with contextlib.closing(sqlite3.connect(new_database_path)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'MiscData'")
        result = cursor.fetchone()
        delete_old_pony_db = not bool(result[0] if result else False)
        if not delete_old_pony_db:
            cursor.execute('SELECT value FROM MiscData WHERE name == "db_version"')
            version = int(cursor.fetchone()[0])
            delete_old_pony_db = version in BETA_DB_VERSIONS  # Delete the older betas DB
    # We're looking at the old experimental version database. Delete it.
    if delete_old_pony_db:
        os.unlink(new_database_path)


def new_db_version_ok(new_database_path):
    # Let's check if we converted all/some entries before
    with contextlib.closing(sqlite3.connect(new_database_path)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute('SELECT value FROM MiscData WHERE name == "db_version"')
        version = int(cursor.fetchone()[0])
    return False if version != CURRENT_DB_VERSION else True


def already_upgraded(new_database_path):
    connection = sqlite3.connect(new_database_path)
    # Check if already upgraded
    cursor = connection.cursor()
    cursor.execute(f'SELECT value FROM MiscData WHERE name == "{CONVERSION_FROM_72}"')
    result = cursor.fetchone()
    if result:
        state = result[0]
        if state == CONVERSION_FINISHED:
            return True
    connection.close()
    return False


def should_upgrade(old_database_path, new_database_path, logger=None):
    """
    Decide if we can migrate data from old DB to Pony
    :return: False if something goes wrong, or we don't need/cannot migrate data
    """
    if not old_database_path.exists():
        # no old DB to upgrade
        return False

    try:
        if not old_db_version_ok(old_database_path):
            return False
    except:
        logger.error("Can't open the old tribler.sdb file")
        return False

    if new_database_path.exists():
        try:
            if not new_db_version_ok(new_database_path):
                return False
            if already_upgraded(new_database_path):
                return False
        except:
            logger.error("Error while trying to open Pony DB file %s", new_database_path)
            return False

    return True
