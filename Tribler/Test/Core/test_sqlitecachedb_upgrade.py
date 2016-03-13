import os
import shutil
from Tribler.Core.CacheDB.db_versions import LATEST_DB_VERSION

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Upgrade.db_upgrader import DBUpgrader, VersionNoLongerSupportedError
from Tribler.Test.test_as_server import AbstractServer


class MockTorrentStore(object):
            pass


class TestSqliteCacheDB(AbstractServer):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    DATABASES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/upgrade_databases/"))

    def setUp(self):
        super(TestSqliteCacheDB, self).setUp()
        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(False)
        self.config.set_dispersy(False)
        self.config.set_mainline_dht(False)
        self.config.set_torrent_collecting(True)
        self.config.set_libtorrent(False)
        self.config.set_dht_torrent_collecting(False)
        self.config.set_videoplayer(False)
        self.config.set_torrent_collecting_dir(os.path.join(self.session_base_dir, 'torrent_collecting_dir'))
        self.session = Session(self.config, ignore_singleton=True)
        self.sqlitedb = None

    def tearDown(self):
        super(TestSqliteCacheDB, self).tearDown()
        if self.sqlitedb:
            self.sqlitedb.close()
        self.sqlitedb = None
        self.session.del_instance()
        self.session = None

    def copy_and_initialize_upgrade_database(self, db_name):
        shutil.copyfile(os.path.join(self.DATABASES_DIR, db_name),
                        os.path.join(self.session_base_dir, 'tribler.sdb'))
        db_path = os.path.join(self.session_base_dir, 'tribler.sdb')
        db_script_path = os.path.join(self.session.get_install_dir())
        self.sqlitedb = SQLiteCacheDB(db_path, db_script_path)
        self.sqlitedb.initialize()
        self.sqlitedb.initial_begin()

    def test_upgrade_from_obsolete_version(self):
        """We no longer support DB versions older than 17 (Tribler 6.0)"""
        self.copy_and_initialize_upgrade_database('tribler_v12.sdb')

        db_migrator = DBUpgrader(self.session, self.sqlitedb, torrent_store=MockTorrentStore())
        self.assertRaises(VersionNoLongerSupportedError, db_migrator.start_migrate)

    def test_upgrade_17_to_latest(self):
        self.copy_and_initialize_upgrade_database('tribler_v17.sdb')
        db_migrator = DBUpgrader(self.session, self.sqlitedb, torrent_store=MockTorrentStore())
        db_migrator.start_migrate()
        self.assertEqual(self.sqlitedb.version, LATEST_DB_VERSION)
