# see LICENSE.txt for license information

# upgrade64.py ---
#
# Filename: upgrade64.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Thu Nov  6 18:13:34 2014 (+0100)
import logging
import os
from binascii import hexlify
from shutil import rmtree
from sqlite3 import Connection

from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler
from Tribler.Core.CacheDB.db_versions import LOWEST_SUPPORTED_DB_VERSION, LATEST_DB_VERSION
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.TorrentDef import TorrentDef


class VersionNoLongerSupportedError(Exception):
    pass


class DatabaseUpgradeError(Exception):
    pass


class DBUpgrader(object):

    """
    Migration tool for upgrading the collected torrent files/thumbnails on disk
    structure from Tribler version 6.3 to 6.4.
    """

    def __init__(self, session, db, torrent_store, status_update_func=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.db = db
        self.status_update_func = status_update_func if status_update_func else lambda _: None
        self.torrent_store = torrent_store

        self.failed = True
        self.torrent_collecting_dir = self.session.get_torrent_collecting_dir()

    def start_migrate(self):
        """
        Starts migrating from Tribler 6.3 to 6.4.
        """

        if self.db.version == 17:
            self._upgrade_17_to_18()

        # version 18 -> 22
        if self.db.version == 18:
            self._upgrade_18_to_22()

        # version 22 -> 23
        if self.db.version == 22:
            self._upgrade_22_to_23()

        # version 23 -> 24 (24 is a dummy version in which we only cleans up thumbnail files
        if self.db.version == 23:
            self._upgrade_23_to_24()

        # version 24 -> 25 (25 is also a dummy version, where the torrent files get migrated to a levedb based store.
        if self.db.version == 24:
            self._upgrade_24_to_25()

        # version 25 -> 26
        if self.db.version == 25:
            self._upgrade_25_to_26()

        # version 26 -> 27
        if self.db.version == 26:
            self._upgrade_26_to_27()

        # version 27 -> 28
        if self.db.version == 27:
            self._upgrade_27_to_28()

        # check if we managed to upgrade to the latest DB version.
        if self.db.version == LATEST_DB_VERSION:
            self.status_update_func(u"Database upgrade finished.")
            self.failed = False
        else:
            if self.db.version < LOWEST_SUPPORTED_DB_VERSION:
                msg = u"Database is too old %s < %s" % (self.db.version, LOWEST_SUPPORTED_DB_VERSION)
                self.status_update_func(msg)
                raise VersionNoLongerSupportedError(msg)
            else:
                msg = u"Database upgrade failed: %s -> %s" % (self.db.version, LATEST_DB_VERSION)
                self.status_update_func(msg)
                raise DatabaseUpgradeError(msg)

    def _purge_old_search_metadata_communities(self):
        """
        Cleans up all SearchCommunity and MetadataCommunity stuff in dispersy database.
        """
        db_path = os.path.join(self.session.get_state_dir(), u"sqlite", u"dispersy.db")
        if not os.path.isfile(db_path):
            return

        communities_to_delete = (u"SearchCommunity", u"MetadataCommunity", u"TunnelCommunity")

        connection = Connection(db_path)
        cursor = connection.cursor()

        for community in communities_to_delete:
            try:
                result = list(cursor.execute(u"SELECT id FROM community WHERE classification == ?;", (community,)))

                for community_id, in result:
                    cursor.execute(u"DELETE FROM community WHERE id == ?;", (community_id,))
                    cursor.execute(u"DELETE FROM meta_message WHERE community == ?;", (community_id,))
                    cursor.execute(u"DELETE FROM sync WHERE community == ?;", (community_id,))
            except StopIteration:
                continue

        cursor.close()
        connection.commit()
        connection.close()

    def _upgrade_17_to_18(self):
        self.current_status = u"Upgrading database from v%s to v%s..." % (17, 18)

        self.db.execute(u"""
DROP TABLE IF EXISTS BarterCast;
DROP INDEX IF EXISTS bartercast_idx;
INSERT OR IGNORE INTO MetaDataTypes ('name') VALUES ('swift-thumbnails');
INSERT OR IGNORE INTO MetaDataTypes ('name') VALUES ('video-info');
""")
        # update database version
        self.db.write_version(18)

    def _upgrade_18_to_22(self):
        self.current_status = u"Upgrading database from v%s to v%s..." % (18, 22)

        self.db.execute(u"""
DROP INDEX IF EXISTS Torrent_swift_hash_idx;

DROP VIEW IF EXISTS Friend;

ALTER TABLE Peer RENAME TO __Peer_tmp;
CREATE TABLE IF NOT EXISTS Peer (
    peer_id    integer PRIMARY KEY AUTOINCREMENT NOT NULL,
    permid     text NOT NULL,
    name       text,
    thumbnail  text
);

INSERT INTO Peer (peer_id, permid, name, thumbnail) SELECT peer_id, permid, name, thumbnail FROM __Peer_tmp;

DROP TABLE IF EXISTS __Peer_tmp;

ALTER TABLE Torrent ADD COLUMN last_tracker_check integer DEFAULT 0;
ALTER TABLE Torrent ADD COLUMN tracker_check_retries integer DEFAULT 0;
ALTER TABLE Torrent ADD COLUMN next_tracker_check integer DEFAULT 0;

CREATE TABLE IF NOT EXISTS TrackerInfo (
  tracker_id  integer PRIMARY KEY AUTOINCREMENT,
  tracker     text    UNIQUE NOT NULL,
  last_check  numeric DEFAULT 0,
  failures    integer DEFAULT 0,
  is_alive    integer DEFAULT 1
);

CREATE TABLE IF NOT EXISTS TorrentTrackerMapping (
  torrent_id  integer NOT NULL,
  tracker_id  integer NOT NULL,
  FOREIGN KEY (torrent_id) REFERENCES Torrent(torrent_id),
  FOREIGN KEY (tracker_id) REFERENCES TrackerInfo(tracker_id),
  PRIMARY KEY (torrent_id, tracker_id)
);

INSERT OR IGNORE INTO TrackerInfo (tracker) VALUES ('no-DHT');
INSERT OR IGNORE INTO TrackerInfo (tracker) VALUES ('DHT');

DROP INDEX IF EXISTS torrent_biterm_phrase_idx;
DROP TABLE IF EXISTS TorrentBiTermPhrase;
DROP INDEX IF EXISTS termfrequency_freq_idx;
DROP TABLE IF EXISTS TermFrequency;
DROP INDEX IF EXISTS Torrent_insert_idx;
DROP INDEX IF EXISTS Torrent_info_roothash_idx;

DROP TABLE IF EXISTS ClicklogSearch;
DROP INDEX IF EXISTS idx_search_term;
DROP INDEX IF EXISTS idx_search_torrent;
""")
        # update database version
        self.db.write_version(22)

    def _upgrade_22_to_23(self):
        """
        Migrates the database to the new version.
        """
        self.status_update_func(u"Upgrading database from v%s to v%s..." % (22, 23))

        self.db.execute(u"""
DROP TABLE IF EXISTS BarterCast;
DROP INDEX IF EXISTS bartercast_idx;

DROP INDEX IF EXISTS Torrent_swift_torrent_hash_idx;
""")

        try:
            next(self.db.execute(u"SELECT * From sqlite_master WHERE name == '_tmp_Torrent' and type == 'table';"))

        except StopIteration:
            # no _tmp_Torrent table, check if the current Torrent table is new
            lines = [(0, u'torrent_id', u'integer', 1, None, 1),
                     (1, u'infohash', u'text', 1, None, 0),
                     (2, u'name', u'text', 0, None, 0),
                     (3, u'torrent_file_name', u'text', 0, None, 0),
                     (4, u'length', u'integer', 0, None, 0),
                     (5, u'creation_date', u'integer', 0, None, 0),
                     (6, u'num_files', u'integer', 0, None, 0),
                     (7, u'thumbnail', u'integer', 0, None, 0),
                     (8, u'insert_time', u'numeric', 0, None, 0),
                     (9, u'secret', u'integer', 0, None, 0),
                     (10, u'relevance', u'numeric', 0, u'0', 0),
                     (11, u'source_id', u'integer', 0, None, 0),
                     (12, u'category_id', u'integer', 0, None, 0),
                     (13, u'status_id', u'integer', 0, u'0', 0),
                     (14, u'num_seeders', u'integer', 0, None, 0),
                     (15, u'num_leechers', u'integer', 0, None, 0),
                     (16, u'comment', u'text', 0, None, 0),
                     (17, u'dispersy_id', u'integer', 0, None, 0),
                     (18, u'last_tracker_check', u'integer', 0, u'0', 0),
                     (19, u'tracker_check_retries', u'integer', 0, u'0', 0),
                     (20, u'next_tracker_check', u'integer', 0, u'0', 0)
                     ]
            i = 0
            is_new = True
            for line in self.db.execute(u"PRAGMA table_info(Torrent);"):
                if line != lines[i]:
                    is_new = False
                    break
                i += 1

            if not is_new:
                # create the temporary table
                self.db.execute(u"""
CREATE TABLE IF NOT EXISTS _tmp_Torrent (
  torrent_id       integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  infohash		   text NOT NULL,
  name             text,
  torrent_file_name text,
  length           integer,
  creation_date    integer,
  num_files        integer,
  thumbnail        integer,
  insert_time      numeric,
  secret           integer,
  relevance        numeric DEFAULT 0,
  source_id        integer,
  category_id      integer,
  status_id        integer DEFAULT 0,
  num_seeders      integer,
  num_leechers     integer,
  comment          text,
  dispersy_id      integer,
  last_tracker_check    integer DEFAULT 0,
  tracker_check_retries integer DEFAULT 0,
  next_tracker_check    integer DEFAULT 0
);
""")

                # migrate Torrent table
                keys = (u"torrent_id", u"infohash", u"name", u"torrent_file_name", u"length", u"creation_date",
                        u"num_files", u"thumbnail", u"insert_time", u"secret", u"relevance", u"source_id",
                        u"category_id", u"status_id", u"num_seeders", u"num_leechers", u"comment", u"dispersy_id",
                        u"last_tracker_check", u"tracker_check_retries", u"next_tracker_check")

                keys_str = u", ".join(keys)
                values_str = u"?," * len(keys)
                insert_stmt = u"INSERT INTO _tmp_Torrent(%s) VALUES(%s)" % (keys_str, values_str[:-1])
                current_count = 0

                results = self.db.execute(u"SELECT %s FROM Torrent;" % keys_str)
                new_torrents = []
                for torrent in results:
                    torrent_id, infohash, name, torrent_file_name = torrent[:4]

                    filepath = os.path.join(self.torrent_collecting_dir, hexlify(str2bin(infohash)) + u".torrent")

                    # Check if we have the actual .torrent
                    torrent_file_name = None
                    if os.path.exists(filepath):
                        torrent_file_name = filepath
                        tdef = TorrentDef.load(filepath)
                        # Use the name on the .torrent file instead of the one stored in the database.
                        name = tdef.get_name_as_unicode() or name

                    new_torrents.append((torrent_id, infohash, name, torrent_file_name) + torrent[4:])

                    current_count += 1
                    self.status_update_func(u"Upgrading database, %s records upgraded..." % current_count)

                self.status_update_func(u"All torrent entries processed, inserting in database...")
                self.db.executemany(insert_stmt, new_torrents)
                self.status_update_func(u"All updated torrent entries inserted.")

                self.db.execute(u"""
DROP TABLE IF EXISTS Torrent;
ALTER TABLE _tmp_Torrent RENAME TO Torrent;
""")

        # cleanup metadata tables
        self.db.execute(u"""
DROP TABLE IF EXISTS MetadataMessage;
DROP TABLE IF EXISTS MetadataData;

CREATE TABLE IF NOT EXISTS MetadataMessage (
  message_id             INTEGER PRIMARY KEY AUTOINCREMENT,
  dispersy_id            INTEGER NOT NULL,
  this_global_time       INTEGER NOT NULL,
  this_mid               TEXT NOT NULL,
  infohash               TEXT NOT NULL,
  previous_mid           TEXT,
  previous_global_time   INTEGER
);

CREATE TABLE IF NOT EXISTS MetadataData (
  message_id  INTEGER,
  data_key    TEXT NOT NULL,
  data_value  INTEGER,
  FOREIGN KEY (message_id) REFERENCES MetadataMessage(message_id) ON DELETE CASCADE
);
""")

        # cleanup all SearchCommunity and MetadataCommunity data in dispersy database
        self._purge_old_search_metadata_communities()

        # update database version
        self.db.write_version(23)

    def _upgrade_23_to_24(self):
        self.status_update_func(u"Upgrading database from v%s to v%s..." % (23, 24))

        # remove all thumbnail files
        for root, dirs, files in os.walk(self.session.get_torrent_collecting_dir()):
            for d in dirs:
                dir_path = os.path.join(root, d)
                rmtree(dir_path, ignore_errors=True)
            break

        # update database version
        self.db.write_version(24)

    def _upgrade_24_to_25(self):
        self.status_update_func(u"Upgrading database from v%s to v%s..." % (24, 25))

        # update database version (that one was easy :D)
        self.db.write_version(25)

    def _upgrade_25_to_26(self):
        self.status_update_func(u"Upgrading database from v%s to v%s..." % (25, 26))

        # remove UserEventLog, TorrentSource, and TorrentCollecting tables
        self.status_update_func(u"Removing unused tables...")
        self.db.execute(u"""
DROP TABLE IF EXISTS UserEventLog;
DROP TABLE IF EXISTS TorrentSource;
DROP TABLE IF EXISTS TorrentCollecting;
""")

        # remove click_position, reranking_strategy, and progress from MyPreference
        self.status_update_func(u"Updating MyPreference table...")
        self.db.execute(u"""
CREATE TABLE _tmp_MyPreference (
  torrent_id     integer PRIMARY KEY NOT NULL,
  destination_path text NOT NULL,
  creation_time  integer NOT NULL
);

INSERT INTO _tmp_MyPreference SELECT torrent_id, destination_path, creation_time FROM MyPreference;

DROP TABLE MyPreference;
ALTER TABLE _tmp_MyPreference RENAME TO MyPreference;
""")

        # remove source_id and thumbnail columns from Torrent table
        # replace torrent_file_name column with is_collected column
        # change CollectedTorrent view
        self.status_update_func(u"Updating Torrent table...")
        self.db.execute(u"""
CREATE TABLE _tmp_Torrent (
  torrent_id       integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  infohash		   text NOT NULL,
  name             text,
  length           integer,
  creation_date    integer,
  num_files        integer,
  insert_time      numeric,
  secret           integer,
  relevance        numeric DEFAULT 0,
  category_id      integer,
  status_id        integer DEFAULT 0,
  num_seeders      integer,
  num_leechers     integer,
  comment          text,
  dispersy_id      integer,
  is_collected     integer DEFAULT 0,
  last_tracker_check    integer DEFAULT 0,
  tracker_check_retries integer DEFAULT 0,
  next_tracker_check    integer DEFAULT 0
);

UPDATE Torrent SET torrent_file_name = '1' WHERE torrent_file_name IS NOT NULL;
UPDATE Torrent SET torrent_file_name = '0' WHERE torrent_file_name IS NULL;

INSERT INTO _tmp_Torrent
SELECT torrent_id, infohash, name, length, creation_date, num_files, insert_time, secret, relevance, category_id,
status_id, num_seeders, num_leechers, comment, dispersy_id, CAST(torrent_file_name AS INTEGER),
last_tracker_check, tracker_check_retries, next_tracker_check FROM Torrent;

DROP TABLE Torrent;
ALTER TABLE _tmp_Torrent RENAME TO Torrent;

DROP VIEW IF EXISTS CollectedTorrent;
CREATE VIEW CollectedTorrent AS SELECT * FROM Torrent WHERE is_collected == 1;
""")

        # update database version
        self.db.write_version(26)

    def _upgrade_26_to_27(self):
        self.status_update_func(u"Upgrading database from v%s to v%s..." % (26, 27))

        # replace status_id and category_id in Torrent table with status and category
        self.status_update_func(u"Updating Torrent table and removing unused tables...")
        self.db.execute(u"""
CREATE TABLE _tmp_Torrent (
  torrent_id       integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  infohash		   text NOT NULL,
  name             text,
  length           integer,
  creation_date    integer,
  num_files        integer,
  insert_time      numeric,
  secret           integer,
  relevance        numeric DEFAULT 0,
  category         text,
  status           text DEFAULT 'unknown',
  num_seeders      integer,
  num_leechers     integer,
  comment          text,
  dispersy_id      integer,
  is_collected     integer DEFAULT 0,
  last_tracker_check    integer DEFAULT 0,
  tracker_check_retries integer DEFAULT 0,
  next_tracker_check    integer DEFAULT 0
);

INSERT INTO _tmp_Torrent
SELECT torrent_id, infohash, T.name, length, creation_date, num_files, insert_time, secret, relevance, C.name, TS.name,
num_seeders, num_leechers, comment, dispersy_id, is_collected, last_tracker_check, tracker_check_retries,
next_tracker_check
FROM Torrent AS T
LEFT JOIN Category AS C ON T.category_id == C.category_id
LEFT JOIN TorrentStatus AS TS ON T.status_id == TS.status_id;

DROP TABLE Torrent;
ALTER TABLE _tmp_Torrent RENAME TO Torrent;

DROP TABLE Category;
DROP TABLE TorrentStatus;
""")

        # update database version
        self.db.write_version(27)

    def _upgrade_27_to_28(self):
        self.status_update_func(u"Upgrading database from v%s to v%s..." % (27, 28))

        # remove old metadata stuff
        self.status_update_func(u"Removing old metadata tables...")
        self.db.execute(u"""
DROP TABLE IF EXISTS MetadataMessage;
DROP TABLE IF EXISTS MetadataData;
""")
        # replace type_id with type in ChannelMetadata
        self.db.execute(u"""
DROP TABLE IF EXISTS _ChannelMetaData_new;

CREATE TABLE _ChannelMetaData_new (
  id                    integer         PRIMARY KEY ASC,
  dispersy_id           integer         NOT NULL,
  channel_id            integer         NOT NULL,
  peer_id               integer,
  type                  text            NOT NULL,
  value                 text            NOT NULL,
  prev_modification     integer,
  prev_global_time      integer,
  time_stamp            integer         NOT NULL,
  inserted              integer         DEFAULT (strftime('%s','now')),
  deleted_at            integer,
  UNIQUE (dispersy_id)
);

INSERT INTO _ChannelMetaData_new
SELECT _ChannelMetaData.id, dispersy_id, channel_id, peer_id, MetadataTypes.name, value, prev_modification, prev_global_time, time_stamp, inserted, deleted_at
FROM _ChannelMetaData
LEFT JOIN MetadataTypes ON _ChannelMetaData.type_id == MetadataTypes.id;

DROP VIEW IF EXISTS ChannelMetaData;
DROP TABLE IF EXISTS _ChannelMetaData;

ALTER TABLE _ChannelMetaData_new RENAME TO _ChannelMetaData;
CREATE VIEW ChannelMetaData AS SELECT * FROM _ChannelMetaData WHERE deleted_at IS NULL;
DROP TABLE IF EXISTS MetaDataTypes;
""")

        # update database version
        self.db.write_version(28)

    def reimport_torrents(self):
        """Import all torrent files in the collected torrent dir, all the files already in the database will be ignored.
        """
        self.status_update_func("Opening TorrentDBHandler...")
        # TODO(emilon): That's a freakishly ugly hack.
        torrent_db_handler = TorrentDBHandler(self.session)
        torrent_db_handler.category = Category.getInstance(self.session)

        # TODO(emilon): It would be nice to drop the corrupted torrent data from the store as a bonus.
        self.status_update_func("Registering recovered torrents...")
        try:
            for infoshash_str, torrent_data in self.torrent_store.itervalues():
                self.status_update_func("> %s" % infoshash_str)
                torrentdef = TorrentDef.load_from_memory(torrent_data)
                if torrentdef.is_finalized():
                    infohash = torrentdef.get_infohash()
                    if not torrent_db_handler.hasTorrent(infohash):
                        self.status_update_func(u"Registering recovered torrent: %s" % hexlify(infohash))
                        torrent_db_handler._addTorrentToDB(torrentdef, extra_info={"filename": infoshash_str})
        finally:
            torrent_db_handler.close()
            Category.delInstance()
            self.db.commit_now()
            return self.torrent_store.flush()
