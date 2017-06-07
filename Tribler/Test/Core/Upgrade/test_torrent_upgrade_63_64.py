import os
import shutil
from apsw import Connection
from nose.tools import raises
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Upgrade.torrent_upgrade64 import TorrentMigrator64
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTorrentUpgrade63to64(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    DB_DATA_DIR = os.path.abspath(os.path.join(FILE_DIR, u"../data/upgrade_databases/"))

    def write_data_to_file(self, file_name):
        with open(file_name, 'w') as file:
            file.write("lorem ipsum")
            file.close()


    # This setup creates a directory with files that should be used for the 6.3 -> 6.4 upgrade
    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(AbstractTorrentUpgrade63to64, self).setUp()

        self.torrent_collecting_dir = os.path.join(self.session_base_dir, "torrent_collecting")
        self.sqlite_path = os.path.join(self.session_base_dir, "sqlite")
        os.mkdir(self.torrent_collecting_dir)
        os.mkdir(os.path.join(self.torrent_collecting_dir, "test_dir"))
        os.mkdir(self.sqlite_path)

        # write and create files
        self.write_data_to_file(os.path.join(self.session_base_dir, "upgradingdb.txt"))
        self.write_data_to_file(os.path.join(self.torrent_collecting_dir, "test1.mbinmap"))
        self.write_data_to_file(os.path.join(self.torrent_collecting_dir, "test2.mhash"))
        self.write_data_to_file(os.path.join(self.torrent_collecting_dir, "tmp_test3"))
        self.write_data_to_file(os.path.join(self.torrent_collecting_dir, "torrent1.torrent"))
        self.write_data_to_file(os.path.join(self.torrent_collecting_dir, "torrent2.torrent"))
        os.mkdir(os.path.join(self.torrent_collecting_dir, "swift_reseeds"))
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(self.torrent_collecting_dir, "torrent3.torrent"))
        shutil.copyfile(os.path.join(self.DB_DATA_DIR, "torrent_upgrade_64_dispersy.db"),
                        os.path.join(self.sqlite_path, "dispersy.db"))

        self.torrent_upgrader = TorrentMigrator64(self.torrent_collecting_dir, self.session_base_dir)

    def assert_upgrade_successful(self):
        self.assertFalse(os.path.isfile(os.path.join(self.session_base_dir, "upgradingdb.txt")))
        self.assertGreater(self.torrent_upgrader.swift_files_deleted, 0)
        self.assertGreater(self.torrent_upgrader.total_swift_file_count, 0)
        self.assertGreater(self.torrent_upgrader.total_torrent_file_count, 0)
        self.assertGreater(self.torrent_upgrader.processed_file_count, 0)
        self.assertGreater(self.torrent_upgrader.torrent_files_dropped, 0)
        self.assertGreater(self.torrent_upgrader.total_file_count, 0)
        self.assertGreater(self.torrent_upgrader.torrent_files_migrated, 0)
        self.assertFalse(os.path.isdir(os.path.join(self.torrent_collecting_dir, "test_dir")))


class TestUpgrade63to64(AbstractTorrentUpgrade63to64):

    def test_upgrade_success(self):
        self.torrent_upgrader.start_migrate()
        self.torrent_upgrader._update_dispersy()
        self.assert_upgrade_successful()

    @raises(OSError)
    def test_upgrade_no_valid_basedir(self):
        self.torrent_upgrader = TorrentMigrator64(self.torrent_collecting_dir,
                                                  os.path.join(self.session_base_dir, "bla"))
        self.torrent_upgrader.start_migrate()

    @raises(RuntimeError)
    def test_upgrade_no_valid_torrent_collecting_dir(self):
        self.torrent_upgrader = TorrentMigrator64(os.path.join(self.torrent_collecting_dir, "bla"),
                                                  self.session_base_dir)
        self.torrent_upgrader.start_migrate()

    @raises(RuntimeError)
    def test_upgrade_temp_torrent_dir_is_file(self):
        self.write_data_to_file(os.path.join(self.session_base_dir, ".tmp_migration_v64"))
        self.torrent_upgrader = TorrentMigrator64(self.torrent_collecting_dir, self.session_base_dir)
        self.torrent_upgrader.start_migrate()

    @raises(RuntimeError)
    def test_upgrade_swift_reseeds_dir_no_dir(self):
        os.rmdir(os.path.join(self.torrent_collecting_dir, "swift_reseeds"))
        self.write_data_to_file(os.path.join(self.torrent_collecting_dir, "swift_reseeds"))
        self.torrent_upgrader.start_migrate()

    def test_upgrade_torrent_tcd_file_exists(self):
        tcd_path = os.path.join(self.session_base_dir, ".tmp_migration_v64_tcd")
        self.write_data_to_file(tcd_path)
        self.torrent_upgrader.start_migrate()
        self.assertFalse(os.path.exists(tcd_path))

    def test_upgrade_migration_dir_already_exists(self):
        os.mkdir(os.path.join(self.session_base_dir, ".tmp_migration_v64"))
        self.torrent_upgrader.start_migrate()
        self.assert_upgrade_successful()

    def test_upgrade_empty_torrent_dir(self):
        shutil.rmtree(self.torrent_collecting_dir)
        os.mkdir(self.torrent_collecting_dir)
        self.torrent_upgrader.start_migrate()
        self.assertEqual(self.torrent_upgrader.total_torrent_file_count, 0)
        self.assertEqual(self.torrent_upgrader.total_swift_file_count, 0)

    def test_upgrade_dispersy_no_database(self):
        os.unlink(os.path.join(self.sqlite_path, "dispersy.db"))
        self.torrent_upgrader._update_dispersy()

    def test_upgrade_dispersy(self):
        self.torrent_upgrader._update_dispersy()

        db_path = os.path.join(self.sqlite_path, u"dispersy.db")
        connection = Connection(db_path)
        cursor = connection.cursor()
        self.assertFalse(list(cursor.execute(u"SELECT * FROM community WHERE classification == 'SearchCommunity'")))
        self.assertFalse(list(cursor.execute(u"SELECT * FROM community WHERE classification == 'MetadataCommunity'")))
        cursor.close()
        connection.close()
