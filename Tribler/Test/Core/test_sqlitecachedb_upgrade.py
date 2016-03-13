import os
import shutil

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, DB_SCRIPT_RELATIVE_PATH
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Upgrade.db_upgrader import DBUpgrader, VersionNoLongerSupportedError
from Tribler.Test.test_as_server import AbstractServer, TESTS_DATA_DIR


class TestSqliteCacheDB(AbstractServer):

    def setUp(self):
        super(TestSqliteCacheDB, self).setUp()
        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(False)
        self.config.set_dispersy(False)
        self.config.set_mainline_dht(False)
        self.config.set_torrent_collecting(False)
        self.config.set_libtorrent(False)
        self.config.set_dht_torrent_collecting(False)
        self.config.set_videoplayer(False)
        self.session = Session(self.config, ignore_singleton=True)
        self.sqlitedb = None

    def tearDown(self):
        super(TestSqliteCacheDB, self).tearDown()
        if self.sqlitedb:
            self.sqlitedb.close()
        self.sqlitedb = None
        self.session.del_instance()
        self.session = None

    def test_upgrade_from_obsolete_version(self):
        """We no longer support DB versions older than 17 (Tribler 6.0)"""
        shutil.copyfile(os.path.join(TESTS_DATA_DIR, 'tribler_v12.sdb'),
                        os.path.join(self.session_base_dir, 'tribler.sdb'))
        db_path = os.path.join(self.session_base_dir, 'tribler.sdb')
        db_script_path = os.path.join(self.session.get_install_dir(), DB_SCRIPT_RELATIVE_PATH)

        self.sqlitedb = SQLiteCacheDB(db_path, db_script_path)
        self.sqlitedb.initialize()

        class MockTorrentStore(object):

            def flush(self):
                pass

            def close(self):
                pass

        db_migrator = DBUpgrader(self.session, self.sqlitedb, torrent_store=MockTorrentStore())
        self.assertRaises(VersionNoLongerSupportedError, db_migrator.start_migrate)

    def test_upgrade_from_17(self):
        pass
        # TODO(emilon): Implement that one and 18 22 23
        # assert sqlitedb.version == LATEST_DB_VERSION, "Database didn't get upgraded to latest version (%s != %s)" % (
        #     sqlitedb.version, LATEST_DB_VERSION)
