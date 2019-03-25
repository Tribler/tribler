from __future__ import absolute_import

import os
from Tribler.Core.Modules.find_files import FindSeedFiles
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.Core.base_test import TriblerCoreTest

import unittest

class TestFindSeedFiles(unittest.TestCase):

    def setUp(self):
        self.tdef = [TorrentDef.load(os.path.join(TESTS_DATA_DIR, 'video.avi.torrent'))]

    def test_no_watchfolder(self):
        pass

    def test_no_torrent_files(self):
        pass

    def test_watchfolder_invalid_dir(self):
        pass

    def test_no_files_found(self):
        pass

    def test_file_found(self):
        find_seeds = FindSeedFiles(TESTS_DATA_DIR, self.tdef)
        seeds = find_seeds.scan()
        self.assertEqual(seeds[self.tdef[0].get_infohash()], [os.path.join(TESTS_DATA_DIR, 'video.avi')])


