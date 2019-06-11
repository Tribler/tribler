from __future__ import absolute_import, division

import base64
import datetime
import logging
import os
import sqlite3

from ipv8.database import database_blob

from pony import orm
from pony.orm import CacheIndexError, TransactionIntegrityError, db_session

from six import text_type

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED, LEGACY_ENTRY, NEW
from Tribler.Core.Modules.MetadataStore.OrmBindings.torrent_metadata import infohash_to_id
from Tribler.Core.Modules.MetadataStore.serialization import REGULAR_TORRENT
from Tribler.Core.Modules.MetadataStore.store import BETA_DB_VERSIONS, CURRENT_DB_VERSION
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url

BATCH_SIZE = 10000

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


def pseudo_signature():
    return database_blob(os.urandom(32))


def final_timestamp():
    return 1 << 62


class DispersyToPonyMigration(object):
    select_channels_sql = "SELECT id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam " \
                          + "FROM Channels " \
                          + "WHERE nr_torrents >= 3 " \
                          + "AND name not NULL;"

    select_trackers_sql = "SELECT tracker_id, tracker, last_check, failures, is_alive FROM TrackerInfo"

    select_full = "SELECT" \
                  " (SELECT ti.tracker FROM TorrentTrackerMapping ttm, TrackerInfo ti WHERE " \
                  "ttm.torrent_id == t.torrent_id AND ttm.tracker_id == ti.tracker_id AND ti.tracker != 'DHT' " \
                  "AND ti.tracker != 'http://retracker.local/announce' ORDER BY ti.is_alive ASC, ti.failures DESC, " \
                  "ti.last_check ASC), chs.dispersy_cid, ct.name, t.infohash, t.length, t.creation_date, " \
                  "t.torrent_id, t.category, t.num_seeders, t.num_leechers, t.last_tracker_check " \
                  "FROM _ChannelTorrents ct, Torrent t, Channels chs WHERE ct.name NOT NULL and t.length > 0 AND " \
                  "t.category NOT NULL AND ct.deleted_at IS NULL AND t.torrent_id == ct.torrent_id AND " \
                  "t.infohash NOT NULL AND ct.channel_id == chs.id"
    select_torrents_sql = " FROM _ChannelTorrents ct, Torrent t WHERE " + \
                          "ct.name NOT NULL and t.length>0 AND t.category NOT NULL AND ct.deleted_at IS NULL " + \
                          " AND t.torrent_id == ct.torrent_id AND t.infohash NOT NULL "

    def __init__(self, tribler_db, notifier_callback=None, logger=None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self.notifier_callback = notifier_callback
        self.tribler_db = tribler_db
        self.mds = None
        self.shutting_down = False

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
        connection = sqlite3.connect(self.tribler_db)
        cursor = connection.cursor()

        channels = []
        for id_, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam in cursor.execute(
                self.select_channels_sql):
            if nr_torrents and nr_torrents > 0:
                channels.append({"id_": infohash_to_id(dispersy_cid),
                                 # converting this to str is a workaround for python 2.7 'writable buffers not hashable'
                                 # problem with Pony
                                 "infohash": str(dispersy_cid),
                                 "title": name or '',
                                 "public_key": "",
                                 "timestamp": final_timestamp(),
                                 "origin_id": 0,
                                 "size": 0,
                                 "subscribed": False,
                                 "status": LEGACY_ENTRY,
                                 "num_entries": int(nr_torrents or 0)})
        connection.close()
        return channels

    def get_personal_channel_id_title(self):
        connection = sqlite3.connect(self.tribler_db)
        cursor = connection.cursor()
        cursor.execute('SELECT id,name FROM Channels WHERE peer_id ISNULL LIMIT 1')
        result = cursor.fetchone()
        connection.close()
        return result

    def get_old_trackers(self):
        connection = sqlite3.connect(self.tribler_db)
        cursor = connection.cursor()

        trackers = {}
        for tracker_id, tracker, last_check, failures, is_alive in cursor.execute(self.select_trackers_sql):
            try:
                tracker_url_sanitized = get_uniformed_tracker_url(tracker)
                if not tracker_url_sanitized:
                    continue
            except:
                # Skip malformed trackers
                continue
            trackers[tracker_url_sanitized] = ({
                "last_check": last_check,
                "failures": failures,
                "alive": is_alive})
        connection.close()
        return trackers

    def get_old_torrents_count(self, personal_channel_only=False):
        personal_channel_filter = ""
        if self.personal_channel_id:
            personal_channel_filter = " AND ct.channel_id " + \
                                      (" == " if personal_channel_only else " != ") + \
                                      (" %i " % self.personal_channel_id)

        connection = sqlite3.connect(self.tribler_db)
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM (SELECT t.torrent_id " + self.select_torrents_sql + \
                       personal_channel_filter + "group by infohash )")
        result = cursor.fetchone()[0]
        connection.close()
        return result

    def get_personal_channel_torrents_count(self):
        connection = sqlite3.connect(self.tribler_db)
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM (SELECT t.torrent_id " + self.select_torrents_sql + \
                       (" AND ct.channel_id == %s " % self.personal_channel_id) + \
                       " group by infohash )")
        result = cursor.fetchone()[0]
        connection.close()
        return result

    def get_old_torrents(self, personal_channel_only=False, batch_size=BATCH_SIZE, offset=0,
                         sign=False):
        connection = sqlite3.connect(self.tribler_db)
        cursor = connection.cursor()

        personal_channel_filter = ""
        if self.personal_channel_id:
            personal_channel_filter = " AND ct.channel_id " + \
                                      (" == " if personal_channel_only else " != ") + \
                                      (" %i " % self.personal_channel_id)

        torrents = []
        for tracker_url, channel_id, name, infohash, length, creation_date, torrent_id, category, num_seeders, \
            num_leechers, last_tracker_check in \
                cursor.execute(
                    self.select_full + personal_channel_filter + " group by infohash" +
                    (" LIMIT " + str(batch_size) + " OFFSET " + str(offset))):
            # check if name is valid unicode data
            try:
                name = text_type(name)
            except UnicodeDecodeError:
                continue

            try:
                if len(base64.decodestring(infohash)) != 20:
                    continue
                if not torrent_id or int(torrent_id) == 0:
                    continue

                if not length:
                    continue

                infohash = base64.decodestring(infohash)

                torrent_dict = {
                    "status": NEW,
                    "infohash": infohash,
                    "size": int(length),
                    "torrent_date": datetime.datetime.utcfromtimestamp(creation_date or 0),
                    "title": name or '',
                    "tags": category or '',
                    "tracker_info": tracker_url or '',
                    "xxx": int(category == u'xxx')}
                if not sign:
                    torrent_dict.update({"origin_id": infohash_to_id(channel_id)})
                health_dict = {
                    "seeders": int(num_seeders or 0),
                    "leechers": int(num_leechers or 0),
                    "last_check": int(last_tracker_check or 0)}
                torrents.append((torrent_dict, health_dict))
            except:
                continue

        connection.close()
        return torrents

    @db_session
    def convert_personal_channel(self):
        # Reflect conversion state
        v = self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_PERSONAL)
        if v:
            if v.value == CONVERSION_STARTED:
                # Just drop the entries from the previous try
                my_channel = self.mds.ChannelMetadata.get_my_channel()
                if my_channel:
                    my_channel.contents.delete(bulk=True)
                    my_channel.delete()
            else:
                # Something is wrong, this should never happen
                return
        else:
            v = self.mds.MiscData(name=CONVERSION_FROM_72_PERSONAL, value=CONVERSION_STARTED)

        # Make sure every necessary bit is there and nothing is left of the old personal channel, just in case
        if (self.personal_channel_id and
                self.get_personal_channel_torrents_count() and
                not self.mds.ChannelMetadata.get_my_channel()):
            old_torrents = self.get_old_torrents(personal_channel_only=True, sign=True)
            my_channel = self.mds.ChannelMetadata.create_channel(title=self.personal_channel_title, description='')
            for (torrent, _) in old_torrents:
                try:
                    md = self.mds.TorrentMetadata(**torrent)
                    md.parents.add(my_channel)
                except:
                    continue

            my_channel.consolidate_channel_torrent()

        v.value = CONVERSION_FINISHED

    @inlineCallbacks
    def update_convert_total(self, amount, elapsed):
        if self.notifier_callback:
            self.notifier_callback("%i entries converted in %i seconds (%i e/s)" % (amount, int(elapsed),
                                                                                    int(amount / elapsed)))
            yield deferLater(reactor, 0.001, lambda: None)

    @inlineCallbacks
    def update_convert_progress(self, amount, total, elapsed):
        if self.notifier_callback:
            elapsed = 0.0001 if elapsed == 0.0 else elapsed
            amount = amount or 1
            est_speed = amount / elapsed
            eta = str(datetime.timedelta(seconds=int((total - amount) / est_speed)))
            self.notifier_callback("Converting old channels.\nTorrents converted: %i/%i (%i%%).\nTime remaining: %s" %
                                   (amount, total, (amount * 100) // total, eta))
            yield deferLater(reactor, 0.001, lambda: None)

    @inlineCallbacks
    def convert_discovered_torrents(self):
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

        start_time = datetime.datetime.utcnow()
        batch_size = 100
        total_to_convert = self.get_old_torrents_count()

        reference_timedelta = datetime.timedelta(milliseconds=1000)
        start = 0 + offset
        elapsed = 1
        while start < total_to_convert:
            batch = self.get_old_torrents(batch_size=batch_size, offset=start)
            if not batch or self.shutting_down:
                break

            end = start + len(batch)

            batch_start_time = datetime.datetime.now()
            try:
                with db_session:
                    for (t, _) in batch:
                        try:
                            self.mds.TorrentMetadata.add_ffa_from_dict(t)
                        except (TransactionIntegrityError, CacheIndexError):
                            pass
            except (TransactionIntegrityError, CacheIndexError):
                pass
            batch_end_time = datetime.datetime.now() - batch_start_time

            elapsed = (datetime.datetime.utcnow() - start_time).total_seconds()
            yield self.update_convert_progress(start, total_to_convert, elapsed)
            target_coeff = (batch_end_time.total_seconds() / reference_timedelta.total_seconds())
            if len(batch) == batch_size:
                # Adjust batch size only for full batches
                if target_coeff < 0.8:
                    batch_size += batch_size
                elif target_coeff > 1.1:
                    batch_size = int(float(batch_size) / target_coeff)
                # we want to guarantee that at least some entries will go through
                batch_size = batch_size if batch_size > 10 else 10
            self._logger.info("Converted old torrents: %i/%i %f ",
                              start + batch_size, total_to_convert, float(batch_end_time.total_seconds()))
            start = end

        with db_session:
            v = self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_DISCOVERED)
            v.value = CONVERSION_FINISHED

        yield self.update_convert_total(start, elapsed)

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
                if contents_len:
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

    @inlineCallbacks
    def do_migration(self):
        self.convert_personal_channel()
        self.mds.clock = None  # We should never touch the clock during legacy conversions
        yield self.convert_discovered_torrents()
        self.convert_discovered_channels()
        self.update_trackers_info()
        self.mark_conversion_finished()


def old_db_version_ok(old_database_path):
    # Check the old DB version
    connection = sqlite3.connect(old_database_path)
    with connection:
        cursor = connection.cursor()
        cursor.execute('SELECT value FROM MyInfo WHERE entry == "version"')
        version = int(cursor.fetchone()[0])
        if version == 29:
            return True
    connection.close()
    return False


def cleanup_pony_experimental_db(new_database_path):
    # Check for the old experimental version database
    # ACHTUNG!!! NUCLEAR OPTION!!! DO NOT MESS WITH IT!!!
    connection = sqlite3.connect(new_database_path)
    with connection:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'MiscData'")
        result = cursor.fetchone()
        delete_old_pony_db = not bool(result[0] if result else False)
        if not delete_old_pony_db:
            cursor.execute('SELECT value FROM MiscData WHERE name == "db_version"')
            version = int(cursor.fetchone()[0])
            delete_old_pony_db = version in BETA_DB_VERSIONS  # Delete the older betas DB
    connection.close()
    # We're looking at the old experimental version database. Delete it.
    if delete_old_pony_db:
        os.unlink(new_database_path)


def new_db_version_ok(new_database_path):
    # Let's check if we converted all/some entries before
    connection = sqlite3.connect(new_database_path)
    with connection:
        cursor = connection.cursor()
        cursor.execute('SELECT value FROM MiscData WHERE name == "db_version"')
        version = int(cursor.fetchone()[0])
        if version != CURRENT_DB_VERSION:
            return False
    connection.close()
    return True


def already_upgraded(new_database_path):
    connection = sqlite3.connect(new_database_path)
    with connection:
        # Check if already upgraded
        cursor = connection.cursor()
        cursor.execute('SELECT value FROM MiscData WHERE name == "%s"' % CONVERSION_FROM_72)
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
    if not os.path.exists(old_database_path):
        # no old DB to upgrade
        return False

    try:
        if not old_db_version_ok(old_database_path):
            return False
    except:
        logger.error("Can't open the old tribler.sdb file")
        return False

    if os.path.exists(new_database_path):
        try:
            if not new_db_version_ok(new_database_path):
                return False
            if already_upgraded(new_database_path):
                return False
        except:
            logger.error("Error while trying to open Pony DB file %s", new_database_path)
            return False

    return True
