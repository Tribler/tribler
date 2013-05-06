import sys
import unittest

from Tribler.Core.CacheDB import sqlitecachedb
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Test.bak_tribler_sdb import init_bak_tribler_sdb

class TestSqliteCacheDB(unittest.TestCase):

    def setUp(self):
        #Speed up upgrade, otherwise this test would take ages.
        self.original_values = [sqlitecachedb.INITIAL_UPGRADE_PAUSE, sqlitecachedb.SUCCESIVE_UPGRADE_PAUSE, sqlitecachedb.UPGRADE_BATCH_SIZE, sqlitecachedb.TEST_OVERRIDE]
        
        sqlitecachedb.INITIAL_UPGRADE_PAUSE = 10
        sqlitecachedb.SUCCESIVE_UPGRADE_PAUSE = 1
        sqlitecachedb.UPGRADE_BATCH_SIZE = sys.maxint
        sqlitecachedb.TEST_OVERRIDE = True

    def tearDown(self):
        SQLiteCacheDB.getInstance().close_all()
        SQLiteCacheDB.delInstance()
        
        sqlitecachedb.INITIAL_UPGRADE_PAUSE, sqlitecachedb.SUCCESIVE_UPGRADE_PAUSE, sqlitecachedb.UPGRADE_BATCH_SIZE, sqlitecachedb.TEST_OVERRIDE = self.original_values

    def test_perform_upgrade(self):
        dbpath = init_bak_tribler_sdb('bak_old_tribler.sdb', overwrite = True)
        
        self.sqlitedb = SQLiteCacheDB.getInstance()
        self.sqlitedb.initDB(dbpath)
        self.sqlitedb.waitForUpdateComplete()