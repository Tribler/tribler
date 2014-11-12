# see LICENSE.txt for license information

# upgrade64.py ---
#
# Filename: upgrade64.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Thu Nov  6 18:13:34 2014 (+0100)

import logging
import md5
import os
from binascii import hexlify
from shutil import rmtree, move

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.CacheDB.sqlitecachedb import str2bin


class TorrentMigrator64(object):
    """
    Migration tool for upgrading the collected torrent files/thumbnails on disk
    structure from Tribler version 6.3 to 6.4.
    """

    def __init__(self, session, db, status_update_func=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.db = db
        if status_update_func:
            self.status_update_func = status_update_func
        else:
            def default_status_update(text):
                pass
            self.status_update_func = default_status_update

        self.torrent_collecting_dir = self.session.get_torrent_collecting_dir()

        self.swift_files_deleted = 0
        self.torrent_files_dropped = 0
        self.torrent_files_migrated = 0
        self.total_torrent_files_processed = 0

        self.total_swift_file_count = 0
        self.total_torrent_file_count = 0

        self.total_file_count = 0
        self.processed_file_count = 0

        # an empty file, if it doesn't exist then we need still need to migrate the torrent collecting directory
        self.tmp_migration_tcd_file = os.path.join(self.session.get_state_dir(), u".tmp_migration_v64_tcd")

        # we put every migrated torrent file in a temporary directory
        self.tmp_migration_dir = os.path.abspath(os.path.join(self.torrent_collecting_dir,
                                                              u"..", u".tmp_migration_v64"))

    def start_migrate(self):
        """
        Starts migrating from Tribler 6.3 to 6.4.
        """
        # remove some previous left files
        useless_files = [u"upgradingdb.txt", u"upgradingdb2.txt", u"upgradingdb3.txt", u"upgradingdb4.txt"]
        for i in xrange(len(useless_files)):
            useless_tmp_file = os.path.join(self.session.get_state_dir(), useless_files[i])
            if os.path.exists(useless_tmp_file):
                os.unlink(useless_tmp_file)

        self._migrate_torrent_collecting_dir()
        self._migrate_database()

        # remove the temporary file if exists
        if os.path.exists(self.tmp_migration_tcd_file):
            os.unlink(self.tmp_migration_tcd_file)

    def _migrate_database(self):
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

        # update database version
        self.db.write_version(23)

        # remove the temporary file if exists
        if os.path.exists(self.tmp_migration_tcd_file):
            os.unlink(self.tmp_migration_tcd_file)

    def _migrate_torrent_collecting_dir(self):
        """
        Migrates the torrent collecting directory.
        """
        if os.path.exists(self.tmp_migration_tcd_file):
            return

        # check and create the temporary migration directory if necessary
        if not os.path.exists(self.tmp_migration_dir):
            try:
                os.mkdir(self.tmp_migration_dir)
            except OSError as e:
                msg = u"Failed to create temporary torrent collecting migration directory %s: %s" %\
                      (self.tmp_migration_dir, e)
                raise OSError(msg)
        elif not os.path.isdir(self.tmp_migration_dir):
            msg = u"The temporary torrent collecting migration path is not a directory: %s" % self.tmp_migration_dir
            raise RuntimeError(msg)

        if not os.path.isdir(self.torrent_collecting_dir):
            raise RuntimeError(u"The torrent collecting directory doesn't exist: %s", self.torrent_collecting_dir)

        self._delete_swift_reseeds()

        # get total file numbers and then start cleaning up
        self._get_total_file_count()
        self._delete_swift_files()
        self._rename_torrent_files()

        # delete all directories in the torrent collecting directory, we don't migrate thumbnails
        self._delete_all_directories()

        # replace the old directory with the new one
        rmtree(self.torrent_collecting_dir)
        move(self.tmp_migration_dir, self.torrent_collecting_dir)

        # create the empty file to indicate that we have finished the torrent collecting directory migration
        open(self.tmp_migration_tcd_file, "wb").close()

    def _get_total_file_count(self):
        """
        Walks through the torrent collecting directory and gets the total number of file.
        """
        for root, _, files in os.walk(self.torrent_collecting_dir):
            for name in files:
                if name.endswith(u".mhash") or name.endswith(u".mhash") or name.startswith(u"tmp_"):
                    self.total_swift_file_count += 1
                else:
                    self.total_torrent_file_count += 1
                self.total_file_count += 1
                self.status_update_func(u"Getting file count: %s..." % self.total_file_count)
            # We don't want to walk through the child directories
            break

    def _delete_swift_reseeds(self):
        """
        Delete the reseeds dir, not used anymore.
        """
        reseeds_path = os.path.join(self.torrent_collecting_dir, u"swift_reseeds")
        if os.path.exists(reseeds_path):
            if not os.path.isdir(reseeds_path):
                raise RuntimeError(u"The swift_reseeds path is not a directory: %s", reseeds_path)
            rmtree(reseeds_path)
            self.swift_files_deleted += 1

    def _delete_swift_files(self):
        """
        Delete all partial swift downloads, also clean up obsolete .mhash and .mbinmap files.
        """
        def update_status():
            progress = 1.0
            if self.total_swift_file_count > 0:
                progress = float(self.swift_files_deleted) / self.total_swift_file_count
            progress *= 100
            self.status_update_func(u"Deleting swift files %.2f%%..." % progress)

        for root, _, files in os.walk(self.torrent_collecting_dir):
            for name in files:
                if name.endswith(u".mhash") or name.endswith(u".mhash") or name.startswith(u"tmp_"):
                    os.unlink(os.path.join(root, name))
                    # update progress
                    self.swift_files_deleted += 1
                    self.processed_file_count += 1
                    update_status()

            # We don't want to walk through the child directories
            break

    def _rename_torrent_files(self):
        """
        Rename all the torrent files to INFOHASH.torrent and delete unparseable ones.
        """
        def update_status():
            progress = 1.0
            if self.total_torrent_file_count > 0:
                progress = float(self.total_torrent_files_processed) / self.total_torrent_file_count
            progress *= 100
            self.status_update_func(u"Migrating torrent files %.2f%%..." % progress)

        for root, _, files in os.walk(self.torrent_collecting_dir):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    tdef = TorrentDef.load(file_path)
                    os.rename(file_path, os.path.join(self.tmp_migration_dir, hexlify(tdef.infohash) + u".torrent"))
                    self.torrent_files_migrated += 1
                except Exception as e:
                    #self._logger.error(u"Torrent file %s is corrupted, dropping it: %s", file_path, str(e))
                    os.unlink(file_path)
                    self.torrent_files_dropped += 1
                self.total_torrent_files_processed += 1
                update_status()

            # We don't want to walk through the child directories
            break

    def _delete_all_directories(self):
        """
        Delets all directories in the torrent collecting directory.
        """
        self.status_update_func(u"Deleting all directories in torrent collecting directory...")
        for root, dirs, files in os.walk(self.torrent_collecting_dir):
            for d in dirs:
                dir_path = os.path.join(root, d)
                rmtree(dir_path, ignore_errors=True)
