import sys
import unittest

from Tribler.Core.CacheDB import sqlitecachedb
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Test.bak_tribler_sdb import init_bak_tribler_sdb
from Tribler.Core.Session import Session
from Tribler.Test.test_as_server import AbstractServer

class TestSqliteCacheDB(AbstractServer):

    def setUp(self):
        self.setUpCleanup()
        
        # Speed up upgrade, otherwise this test would take ages.
        self.original_values = [sqlitecachedb.INITIAL_UPGRADE_PAUSE, sqlitecachedb.SUCCESIVE_UPGRADE_PAUSE, sqlitecachedb.UPGRADE_BATCH_SIZE, sqlitecachedb.TEST_OVERRIDE]

        sqlitecachedb.INITIAL_UPGRADE_PAUSE = 10
        sqlitecachedb.SUCCESIVE_UPGRADE_PAUSE = 1
        sqlitecachedb.UPGRADE_BATCH_SIZE = sys.maxint
        sqlitecachedb.TEST_OVERRIDE = True

    def tearDown(self):
        if SQLiteCacheDB.hasInstance():
            SQLiteCacheDB.getInstance().close_all()
            SQLiteCacheDB.delInstance()

        if Session.has_instance():  # Upgrading will create a session instance
            Session.del_instance()
        
        sqlitecachedb.INITIAL_UPGRADE_PAUSE, sqlitecachedb.SUCCESIVE_UPGRADE_PAUSE, sqlitecachedb.UPGRADE_BATCH_SIZE, sqlitecachedb.TEST_OVERRIDE = self.original_values
        self.tearDownCleanup()

    def test_perform_upgrade(self):
        dbpath = init_bak_tribler_sdb('bak_old_tribler.sdb', destination_path=self.getStateDir(), overwrite=True)

        self.sqlitedb = SQLiteCacheDB.getInstance()
        self.sqlitedb.initDB(dbpath)
        self.sqlitedb.waitForUpdateComplete()