import os

from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler
from Tribler.Core.CacheDB.db_versions import LATEST_DB_VERSION

from Tribler.Core.Upgrade.db_upgrader import DBUpgrader, VersionNoLongerSupportedError, DatabaseUpgradeError
from Tribler.Core.Utilities.utilities import fix_torrent
from Tribler.Core.leveldbstore import LevelDbStore
from Tribler.Test.Core.Upgrade.upgrade_base import AbstractUpgrader, MockTorrentStore
from Tribler.Test.common import TORRENT_FILE_INFOHASH, TORRENT_FILE


class TestDBUpgrader(AbstractUpgrader):

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
        self.assertFalse(os.path.exists(os.path.join(self.session.get_torrent_collecting_dir(), 'dir1')))

    def test_upgrade_17_to_latest_no_dispersy(self):
        # upgrade without dispersy DB should not raise an error
        self.copy_and_initialize_upgrade_database('tribler_v17.sdb')
        os.unlink(os.path.join(self.session.get_state_dir(), 'sqlite', 'dispersy.db'))
        db_migrator = DBUpgrader(self.session, self.sqlitedb, torrent_store=MockTorrentStore())
        db_migrator.start_migrate()
        self.assertEqual(self.sqlitedb.version, LATEST_DB_VERSION)

        # Check whether the torrents in the database are reindexed
        results = self.sqlitedb.fetchall("SELECT * FROM FullTextIndex")
        self.assertEqual(len(results), 1)
        self.assertTrue('test' in results[0][0])
        self.assertTrue('random' in results[0][1])
        self.assertTrue('tribler' in results[0][1])
        self.assertTrue('txt' in results[0][2])
        self.assertTrue('txt' in results[0][2])

    def test_upgrade_wrong_version(self):
        self.copy_and_initialize_upgrade_database('tribler_v17.sdb')
        db_migrator = DBUpgrader(self.session, self.sqlitedb, torrent_store=MockTorrentStore())
        db_migrator.db._version = LATEST_DB_VERSION + 1
        self.assertRaises(DatabaseUpgradeError, db_migrator.start_migrate)

    def test_reimport_torrents(self):
        self.copy_and_initialize_upgrade_database('tribler_v17.sdb')
        self.torrent_store = LevelDbStore(self.session.get_torrent_store_dir())
        db_migrator = DBUpgrader(self.session, self.sqlitedb, torrent_store=self.torrent_store)
        db_migrator.start_migrate()

        # Import a torrent
        self.torrent_store[TORRENT_FILE_INFOHASH] = fix_torrent(TORRENT_FILE)
        self.torrent_store.flush()

        db_migrator.reimport_torrents()

        torrent_db_handler = TorrentDBHandler(self.session)
        self.assertEqual(torrent_db_handler.getTorrentID(TORRENT_FILE_INFOHASH), 3)
