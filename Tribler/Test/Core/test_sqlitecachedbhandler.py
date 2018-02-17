import os
import tarfile

from configobj import ConfigObj
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.CacheDB.SqliteCacheDBHandler import (BasicDBHandler, LimitedOrderedDict)
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Core.Config.tribler_config import TriblerConfig, CONFIG_SPEC_PATH
from Tribler.Core.Session import Session
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.dispersy.util import blocking_call_on_reactor_thread


BUSYTIMEOUT = 5000


class TestLimitedOrderedDict(TriblerCoreTest):

    def test_limited_ordered_dict(self):
        od = LimitedOrderedDict(3)
        od['foo'] = 'bar'
        od['bar'] = 'foo'
        od['foobar'] = 'foobar'
        self.assertEqual(len(od), 3)
        od['another'] = 'another'
        self.assertEqual(len(od), 3)


class AbstractDB(TriblerCoreTest):

    def setUpPreSession(self):
        self.config = TriblerConfig(ConfigObj(configspec=CONFIG_SPEC_PATH))
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking_enabled(False)
        self.config.set_megacache_enabled(False)
        self.config.set_dispersy_enabled(False)
        self.config.set_mainline_dht_enabled(False)
        self.config.set_torrent_collecting_enabled(False)
        self.config.set_libtorrent_enabled(False)
        self.config.set_video_server_enabled(False)
        self.config.set_torrent_store_enabled(False)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(AbstractDB, self).setUp()

        self.setUpPreSession()
        self.session = Session(self.config)

        tar = tarfile.open(os.path.join(TESTS_DATA_DIR, 'bak_new_tribler.sdb.tar.gz'), 'r|gz')
        tar.extractall(self.session_base_dir)

        db_path = os.path.join(self.session_base_dir, 'bak_new_tribler.sdb')

        self.sqlitedb = SQLiteCacheDB(db_path, busytimeout=BUSYTIMEOUT)
        self.sqlitedb.initialize()
        self.session.sqlite_db = self.sqlitedb

    def tearDown(self):
        self.sqlitedb.close()
        self.sqlitedb = None
        self.session = None

        super(AbstractDB, self).tearDown(self)

class TestSqliteBasicDBHandler(AbstractDB):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(TestSqliteBasicDBHandler, self).setUp()
        self.db = BasicDBHandler(self.session, u"Peer")

    @blocking_call_on_reactor_thread
    def test_size(self):
        size = self.db.size()  # there are 3995 peers in the table, however the upgrade scripts remove 8 superpeers
        assert size == 3987, size
