#!/usr/bin/env python

# upgrade64.py ---
#
# Filename: upgrade64.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Thu Nov  6 18:13:34 2014 (+0100)

# Commentary:
#
#
#
#

# Change Log:
#
#
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
#
#

# Code:
import logging
import md5
import os
from binascii import hexlify
from shutil import rmtree
from sys import argv

from Tribler.Core.TorrentDef import TorrentDef


class TorrentMigrator64(object):

    """
    Migration tool for upgrading the collected torrent files/thumbnails on disk
    structure from Tribler version < 6.4 to >= 6.4.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.swift_files_deleted = 0
        self.torrent_files_dropped = 0
        self.torrent_files_migrated = 0
        self.thumbnails_migrated = 0

    def __str__(self):
        return "Torrents processed: %d, dropped: %d, migrated: %d, obsolete swift \
 files deleted: %d, thumbnails migrated: %d" % (
            self.torrent_files_dropped + self.torrent_files_migrated,
            self.torrent_files_dropped, self.torrent_files_migrated,
            self.swift_files_deleted, self.thumbnails_migrated)

    def migrate(self, path):
        collected_torrents_path = self._check_if_correct_dir(path)
        self._delete_swift_reseeds(collected_torrents_path)
        self._delete_swift_files(collected_torrents_path)
        self._rename_torrent_files(collected_torrents_path)
        # self._migrate_metadata_dirs(collected_torrents_path)
        self._delete_all_empty_dirs(collected_torrents_path)

    def _check_if_correct_dir(self, path):
        """
        Check if we actually are going to attempt to migrate a collected torrents
        dir and return the absolute path to it.

        """
        collected_torrents_path = os.path.join(path, u'collected_torrent_files')
        if not os.path.isdir(collected_torrents_path):
            raise RuntimeError("This path doesn't contain the 'collected_torrent_files' _dir.")
        return collected_torrents_path

    def _delete_swift_reseeds(self, path):
        """
        Delete the reseeds dir, not used anymore.
        """
        reseeds_path = os.path.join(path, u'swift_reseeds')
        if os.path.exists(reseeds_path):
            rmtree(reseeds_path)
            self.swift_files_deleted += 1

    def _delete_swift_files(self, path):
        """
        Delete all partial swift downloads, also clean up obsolete .mhash and .mbinmap files.
        """
        for root, _, files in os.walk(path):
            for name in files:
                if name.endswith(u'mhash') or name.endswith(u'mbinmap') or name.startswith(u'tmp_'):
                    os.unlink(os.path.join(root, name))
                    self.swift_files_deleted += 1
            # We don't want to walk through the child directories
            break

    def _rename_torrent_files(self, path):
        """
        Rename all the torrent files to INFOHASH.torrent and delete unparseable ones.
        """
        for root, _, files in os.walk(path):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    tdef = TorrentDef.load(file_path)
                    os.rename(file_path, os.path.join(root, hexlify(tdef.infohash) + u'.torrent'))
                    self.torrent_files_migrated += 1
                except Exception as e:
                    print "Torrent file %s is corrupted, dropping it: %s" % (file_path, str(e))
                    os.unlink(file_path)
                    self.torrent_files_dropped += 1
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
                placeholder_path = os.path.join(subdir_path, '.mfplaceholder')
                if os.path.exists(placeholder_path):
                    os.unlink(placeholder_path)
                    self.swift_files_deleted += 1

    def _migrate_metadata_dirs(self, path):
        """
        Find all thumbnails dirs and migrate them to the new on disk structure.
        """
        for root, dirs, _ in os.walk(path):
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

    def _delete_all_empty_dirs(self, path):
        """
        As a last step, delete all empty dirs left.
        """
        for root, dirs, files in os.walk(path):
            if not dirs and not files:
                os.rmdir(root)
                self.swift_files_deleted += 1

if __name__ == "__main__":
    tm = TorrentMigrator64()
    tm.migrate(argv[1])
    print tm

#
# upgrade64.py ends here
