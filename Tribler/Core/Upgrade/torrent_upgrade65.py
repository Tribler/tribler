# torrent_upgrade65.py ---
#
# Filename: torrent_upgrade65.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Tue Jan 27 15:50:05 2015 (+0100)

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
import os
from binascii import hexlify
from shutil import rmtree

from .torrent_upgrade64 import TorrentMigrator64
from Tribler.Core.TorrentDef import TorrentDef


class TorrentMigrator65(TorrentMigrator64):

    def __init__(self, torrent_collecting_dir, state_dir, torrent_store, status_update_func=None):
        super(TorrentMigrator65, self).__init__(torrent_collecting_dir, state_dir, status_update_func)
        self.torrent_store = torrent_store

    def _migrate_torrent_collecting_dir(self):
        """
        Migrates the torrent collecting directory.
        """
        if self.torrent_collecting_dir is None or not os.path.isdir(self.torrent_collecting_dir):
            self._logger.info(u"torrent collecting directory not found, skip: %s", self.torrent_collecting_dir)
            return

        self._delete_swift_reseeds()

        # get total file numbers and then start cleaning up
        self._get_total_file_count()
        self._delete_swift_files()
        self._ingest_torrent_files()

        # delete all directories in the torrent collecting directory, we don't migrate thumbnails
        self._delete_all_directories()

        # replace the old directory with the new one
        rmtree(self.torrent_collecting_dir)

    def _ingest_torrent_files(self):
        """
        Renames all the torrent files to INFOHASH.torrent and delete unparseable ones.
        """
        def update_status():
            progress = 1.0
            if self.total_torrent_file_count > 0:
                progress = float(self.total_torrent_files_processed) / self.total_torrent_file_count
            progress *= 100
            self.status_update_func(u"Ingesting torrent files %.1f%% (%d/%d)..."
                                    % (progress, self.torrent_files_migrated,
                                       self.torrent_files_dropped))

        self.status_update_func("Ingesting torrent files...")
        for root, _, files in os.walk(self.torrent_collecting_dir):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    tdef = TorrentDef.load(file_path)
                    # TODO(emilon): This should be moved out of the try block so
                    # an error there doesn't wipe the whole torrent collection.
                    with open(file_path, 'rb') as torrent_file:
                        self.torrent_store[hexlify(tdef.infohash)] = torrent_file.read()
                    # self.torrent_store[hexlify(tdef.infohash)] = tdef.encode()
                    self.torrent_files_migrated += 1
                except Exception as e:
                    self._logger.error(u"dropping corrupted torrent file %s: %s", file_path, str(e))
                    self.torrent_files_dropped += 1
                os.unlink(file_path)
                self.total_torrent_files_processed += 1
                if not self.total_torrent_files_processed % 2000:
                    self.torrent_store.flush()
                update_status()

            # We don't want to walk through the child directories
            break
        self.status_update_func("All torrent files processed.")


#
# torrent_upgrade65.py ends here
