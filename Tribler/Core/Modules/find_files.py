from __future__ import absolute_import

import os

# Finds files that match torrent to seed
class FindSeedFiles:

    def __init__(self, watch_directory, torrent_defs):
        self.watch_directory = watch_directory
        self.torrent_defs = torrent_defs

    def scan(self):
        # return dictionary with torrent as key and list of files to seed
        seed_files = {}
        for torrent in self.torrent_defs:
            seed_files[torrent.get_infohash()] = []
            torrent_files = torrent.get_files_with_length()
            for root, dirs, files in os.walk(self.watch_directory):
                for tfile in torrent_files:
                    if tfile[0] in files and self.is_seed_file(tfile, torrent):
                        seed_files[torrent.get_infohash()].append(root + '/' + tfile[0])
        return seed_files

    def is_seed_file(self, file_, torrent):
        return True

    def __load_db(self):
        # load directory structure from db
        pass

    def __save_db(self):
        # save directory structure to db
        pass
