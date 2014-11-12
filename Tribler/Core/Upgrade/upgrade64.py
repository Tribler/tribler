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
        self.thumbnails_migrated = 0

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

        self.db.execute(u"DROP INDEX IF EXISTS Torrent_swift_torrent_hash_idx;")

        self.db.execute(u"""
DROP TABLE IF EXISTS BarterCast;
DROP INDEX IF EXISTS bartercast_idx;

DROP INDEX Torrent_swift_torrent_hash_idx;

UPDATE MetaDataTypes SET name = 'url' WHERE name == 'swift-url';
UPDATE MetaDataTypes SET name = 'thumbnails' WHERE name == 'swift-thumbnails';
""")

        # migrate the Torrent table
        try:
            next(self.db.execute(u"SELECT name FROM sqlite_master WHERE type == 'table' AND name == '_tmp_Torrent';"))
        except StopIteration:
            # create the temporary table
            self.db.execute(u"""
CREATE TABLE _tmp_Torrent (
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
);""")
        self.db.execute(u"CREATE TABLE IF NOT EXISTS _tmp_Torrent;")

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
            tdef = TorrentDef.load(filepath)
            match = tdef.get_name_as_unicode() == name

            # only keep the torrent_file_name if the file exists or the information match
            torrent_file_name = filepath if os.path.exists(filepath) and match else None

            new_torrent = [torrent_id, infohash, name, torrent_file_name]
            for d in torrent[4:]:
                new_torrent.append(d)
            new_torrent = tuple(new_torrent)

            self.db.execute(insert_stmt, new_torrent)

            current_count += 1
            self.status_update_func(u"Upgrading database, %s records upgraded..." % current_count)

        self.db.execute(u"""
DROP TABLE Torrent;
ALTER TABLE _tmp_Torrent RENAME TO Torrent;
""")

        # update database version
        self.db.write_version(23)

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

        # self._migrate_metadata_dirs(collected_torrents_path)
        self._delete_all_empty_dirs()

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
            progress = float(self.swift_files_deleted) / self.total_swift_file_count
            self.status_update_func(u"Deleting swift files %s%%..." % progress)

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
            progress = float(self.total_torrent_files_processed) / self.total_swift_file_count
            self.status_update_func(u"Migrating torrent files %s%%..." % progress)

        for root, _, files in os.walk(self.torrent_collecting_dir):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    tdef = TorrentDef.load(file_path)
                    os.rename(file_path, os.path.join(root, hexlify(tdef.infohash) + u".torrent"))
                    self.torrent_files_migrated += 1
                    # delete the old one
                    os.unlink(file_path)
                except Exception as e:
                    self._logger.error(u"Torrent file %s is corrupted, dropping it: %s", file_path, str(e))
                    os.unlink(file_path)
                    self.torrent_files_dropped += 1
                self.total_torrent_files_processed += 1
                update_status()

            # We don't want to walk through the child directories
            break

    def _hash_thumbdir(self, path):
        """
        Rename all the thumbnail files to MD5SUM.extension.
        Also clean up all the placeholder files found.
        """
        for root, dirs, files in os.walk(path):
            for name in files:
                file_path = os.path.join(root, name)
                file_ext = os.path.splitext(name)[-1]
                _hash = md5.new()
                _hash.update(open(file_path, 'r').read())
                new_file_path = os.path.join(path, _hash.hexdigest() + file_ext)
                os.rename(file_path, new_file_path)
                self.thumbnails_migrated += 1

            for _dir in dirs:
                subdir_path = os.path.join(path, _dir)
                # Delete the obsolete .mfplaceholder file if there's one.
                placeholder_path = os.path.join(subdir_path, u".mfplaceholder")
                if os.path.exists(placeholder_path):
                    os.unlink(placeholder_path)
                    self.swift_files_deleted += 1

    def _migrate_metadata_dirs(self):
        """
        Find all thumbnails dirs and migrate them to the new on disk structure.
        """
        for root, dirs, _ in os.walk(self.torrent_collecting_dir):
            for name in dirs:
                if name.startswith(u"thumbs-"):
                    new_name = u'-'.join(reversed(name.split(u'-')))
                    new_file_path = os.path.join(root, new_name)
                    file_path = os.path.join(root, name)

                    self._hash_thumbdir(file_path)
                    # This thumbdir has been migrated to the new structure and
                    # it's clean now, move it to the new name.
                    os.rename(file_path, new_file_path)
            # We don't want to walk through the child directories
            break

    def _delete_all_empty_dirs(self):
        """
        As a last step, delete all empty dirs left.
        """
        for root, dirs, files in os.walk(self.torrent_collecting_dir):
            if not dirs and not files:
                os.rmdir(root)
                self.swift_files_deleted += 1
