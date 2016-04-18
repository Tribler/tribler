import os
import shutil
from Tribler.Core.Upgrade.torrent_upgrade65 import TorrentMigrator65
from Tribler.Core.leveldbstore import LevelDbStore
from Tribler.Test.Core.Upgrade.test_torrent_upgrade_63_64 import AbstractTorrentUpgrade63to64


class AbstractTorrentUpgrade64to65(AbstractTorrentUpgrade63to64):

    def setUp(self):
        super(AbstractTorrentUpgrade64to65, self).setUp()

        leveldb_path = os.path.join(self.session_base_dir, "leveldbstore")
        os.mkdir(leveldb_path)
        self.torrent_store = LevelDbStore(leveldb_path)
        self.torrent_upgrader = TorrentMigrator65(self.torrent_collecting_dir,
                                                  self.session_base_dir, self.torrent_store)

    def tearDown(self, annotate=True):
        self.torrent_store.close()
        super(AbstractTorrentUpgrade64to65, self).tearDown()

    def assert_upgrade_successful(self):
        self.assertGreater(self.torrent_upgrader.torrent_files_migrated, 0)
        self.assertGreater(self.torrent_upgrader.processed_file_count, 0)
        self.assertGreater(len(self.torrent_store), 0)


class TestTorrentUpgrade63to64(AbstractTorrentUpgrade64to65):

    def test_upgrade_success(self):
        self.torrent_upgrader._migrate_torrent_collecting_dir()
        self.assert_upgrade_successful()

    def test_torrent_collecting_dir_no_dir(self):
        shutil.rmtree(self.torrent_collecting_dir)
        self.write_data_to_file(self.torrent_collecting_dir)
        self.torrent_upgrader._migrate_torrent_collecting_dir()

        self.assertEqual(self.torrent_upgrader.torrent_files_migrated, 0)
        self.assertEqual(self.torrent_upgrader.processed_file_count, 0)
        self.assertEqual(len(self.torrent_store), 0)
