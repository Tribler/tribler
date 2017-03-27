"""
Migration scripts for migrating to 6.4

Author(s): Elric Milon
"""
import logging
import os
from binascii import hexlify
from shutil import rmtree, move
from sqlite3 import Connection

from Tribler.Core.TorrentDef import TorrentDef


class TorrentMigrator64(object):

    """
    Migration tool for upgrading the collected torrent files/thumbnails on disk
    structure from Tribler version 6.3 to 6.4.
    """

    def __init__(self, torrent_collecting_dir, state_dir, status_update_func=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.status_update_func = status_update_func if status_update_func else lambda _: None

        self.torrent_collecting_dir = torrent_collecting_dir
        self.state_dir = state_dir

        self.swift_files_deleted = 0
        self.torrent_files_dropped = 0
        self.torrent_files_migrated = 0
        self.total_torrent_files_processed = 0

        self.total_swift_file_count = 0
        self.total_torrent_file_count = 0

        self.total_file_count = 0
        self.processed_file_count = 0

        # an empty file, if it doesn't exist then we need still need to migrate the torrent collecting directory
        self.tmp_migration_tcd_file = os.path.join(self.state_dir, u".tmp_migration_v64_tcd")

        # we put every migrated torrent file in a temporary directory
        self.tmp_migration_dir = os.path.abspath(os.path.join(self.state_dir, u".tmp_migration_v64"))

    def start_migrate(self):
        """
        Starts migrating from Tribler 6.3 to 6.4.
        """
        # remove some previous left files
        useless_files = [u"upgradingdb.txt", u"upgradingdb2.txt", u"upgradingdb3.txt", u"upgradingdb4.txt"]
        for i in xrange(len(useless_files)):
            useless_tmp_file = os.path.join(self.state_dir, useless_files[i])
            if os.path.exists(useless_tmp_file):
                os.unlink(useless_tmp_file)

        self._migrate_torrent_collecting_dir()

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
        self.status_update_func(
            u"Scanning torrent directory. This may take a while if you have a big torrent collection...")
        for root, _, files in os.walk(self.torrent_collecting_dir):
            for name in files:
                if name.endswith(u".mbinmap") or name.endswith(u".mhash") or name.startswith(u"tmp_"):
                    self.total_swift_file_count += 1
                else:
                    self.total_torrent_file_count += 1
                self.total_file_count += 1
                self.status_update_func(u"Getting file count: %s..." % self.total_file_count)
            # We don't want to walk through the child directories
            break

    def _delete_swift_reseeds(self):
        """
        Deletes the reseeds dir, not used anymore.
        """
        reseeds_path = os.path.join(self.torrent_collecting_dir, u"swift_reseeds")
        if os.path.exists(reseeds_path):
            if not os.path.isdir(reseeds_path):
                raise RuntimeError(u"The swift_reseeds path is not a directory: %s", reseeds_path)
            rmtree(reseeds_path)
            self.swift_files_deleted += 1

    def _delete_swift_files(self):
        """
        Deletes all partial swift downloads, also clean up obsolete .mhash and .mbinmap files.
        """
        def update_status():
            progress = 1.0
            if self.total_swift_file_count > 0:
                progress = float(self.swift_files_deleted) / self.total_swift_file_count
            progress *= 100
            self.status_update_func(u"Deleting swift files %.1f%%..." % progress)

        for root, _, files in os.walk(self.torrent_collecting_dir):
            for name in files:
                if name.endswith(u".mbinmap") or name.endswith(u".mhash") or name.startswith(u"tmp_"):
                    os.unlink(os.path.join(root, name))
                    # update progress
                    self.swift_files_deleted += 1
                    self.processed_file_count += 1
                    update_status()

            # We don't want to walk through the child directories
            break

    def _rename_torrent_files(self):
        """
        Renames all the torrent files to INFOHASH.torrent and delete unparseable ones.
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
                    move(file_path, os.path.join(self.tmp_migration_dir, hexlify(tdef.infohash) + u".torrent"))
                    self.torrent_files_migrated += 1
                except Exception as e:
                    self._logger.error(u"dropping corrupted torrent file %s: %s", file_path, str(e))
                    os.unlink(file_path)
                    self.torrent_files_dropped += 1
                self.total_torrent_files_processed += 1
                update_status()

            # We don't want to walk through the child directories
            break

    def _delete_all_directories(self):
        """
        Deletes all directories in the torrent collecting directory.
        """
        self.status_update_func(u"Checking all directories in torrent collecting directory...")
        for root, dirs, files in os.walk(self.torrent_collecting_dir):
            for d in dirs:
                dir_path = os.path.join(root, d)
                rmtree(dir_path, ignore_errors=True)

    def _update_dispersy(self):
        """
        Cleans up all SearchCommunity and MetadataCommunity stuff in dispersy database.
        """
        db_path = os.path.join(self.state_dir, u"sqlite", u"dispersy.db")
        if not os.path.isfile(db_path):
            return

        communities_to_delete = (u"SearchCommunity", u"MetadataCommunity")

        connection = Connection(db_path)
        cursor = connection.cursor()

        data_updated = False
        for community in communities_to_delete:
            try:
                result = list(cursor.execute(u"SELECT id FROM community WHERE classification == ?", (community,)))

                for community_id, in result:
                    self._logger.info(u"deleting all data for community %s...", community_id)
                    cursor.execute(u"DELETE FROM community WHERE id == ?", (community_id,))
                    cursor.execute(u"DELETE FROM meta_message WHERE community == ?", (community_id,))
                    cursor.execute(u"DELETE FROM sync WHERE community == ?", (community_id,))
                    data_updated = True
            except StopIteration:
                continue

        if data_updated:
            connection.commit()
        cursor.close()
        connection.close()
