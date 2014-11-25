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
from sqlite3 import Connection

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

    def __init__(self, session, db, status_update_func=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.db = db
        self.status_update_func = status_update_func if status_update_func else lambda _:None

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

        communities_to_delete = (u"SearchCommunity", u"MetadataCommunity")

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
                keys = (u"torrent_id", u"infohash", u"name", u"torrent_file_name", u"length", u"creation_date", u"num_files",
                        u"thumbnail", u"insert_time", u"secret", u"relevance", u"source_id", u"category_id", u"status_id",
                        u"num_seeders", u"num_leechers", u"comment", u"dispersy_id", u"last_tracker_check",
                        u"tracker_check_retries", u"next_tracker_check")
                keys_str = u", ".join(keys)
                results = self.db.execute(u"SELECT %s FROM Torrent;" % keys_str)

                keys_str = u", ".join(keys)
                values_str = u"?," * len(keys)
                insert_stmt = u"INSERT INTO _tmp_Torrent(%s) VALUES(%s)" % (keys_str, values_str[:-1])
                current_count = 0
                for torrent in results:
                    torrent_id, infohash, name, torrent_file_name = torrent[:4]

                    filepath = os.path.join(self.torrent_collecting_dir, hexlify(str2bin(infohash)) + u".torrent")

                    # check if torrent matches
                    torrent_file_name = None
                    if os.path.exists(filepath):
                        tdef = TorrentDef.load(filepath)
                        if tdef.get_name_as_unicode() == name:
                            torrent_file_name = filepath

                    new_torrent = [torrent_id, infohash, name, torrent_file_name]
                    for d in torrent[4:]:
                        new_torrent.append(d)
                    new_torrent = tuple(new_torrent)

                    self.db.execute(insert_stmt, new_torrent)

                    current_count += 1
                    self.status_update_func(u"Upgrading database, %s records upgraded..." % current_count)

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
