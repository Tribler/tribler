from Tribler.Core.CacheDB.db_versions import LATEST_DB_VERSION
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Upgrade.db_upgrader import DBUpgrader, VersionNoLongerSupportedError
from Tribler.Test.bak_tribler_sdb import init_bak_tribler_sdb
from Tribler.Test.test_as_server import AbstractServer


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
        dbpath = init_bak_tribler_sdb(u"bak_old_tribler.sdb", destination_path=self.getStateDir(), overwrite=True)

        self.sqlitedb = SQLiteCacheDB(self.session)
        self.sqlitedb.initialize(dbpath)

        class MockTorrentStore(object):

            def flush():
                pass

            def close():
                pass

        db_migrator = DBUpgrader(self.session, self.sqlitedb, torrent_store=MockTorrentStore())
        self.assertRaises(VersionNoLongerSupportedError, db_migrator.start_migrate)

    def test_upgrade_from_17(self):
        pass
        # TODO(emilon): Implement that one and 18 22 23
        # assert sqlitedb.version == LATEST_DB_VERSION, "Database didn't get upgraded to latest version (%s != %s)" % (
        #     sqlitedb.version, LATEST_DB_VERSION)
