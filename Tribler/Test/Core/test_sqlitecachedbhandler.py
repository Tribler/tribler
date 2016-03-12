import os

from Tribler.Core.CacheDB.SqliteCacheDBHandler import (BasicDBHandler,
                                                       PeerDBHandler, LimitedOrderedDict)
from Tribler.Core.CacheDB.sqlitecachedb import str2bin, SQLiteCacheDB, DB_SCRIPT_RELATIVE_PATH
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.bak_tribler_sdb import init_bak_tribler_sdb
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
        self.config.set_torrent_store(False)

    def setUp(self):
        super(AbstractDB, self).setUp()

        self.setUpPreSession()
        self.session = Session(self.config, ignore_singleton=True)

        db_path = init_bak_tribler_sdb('bak_new_tribler.sdb', destination_path=self.getStateDir(), overwrite=True)
        db_script_path = os.path.join(self.session.get_install_dir(), DB_SCRIPT_RELATIVE_PATH)

        self.sqlitedb = SQLiteCacheDB(db_path, db_script_path, busytimeout=BUSYTIMEOUT)
        self.sqlitedb.initialize()
        self.session.sqlite_db = self.sqlitedb

    @blocking_call_on_reactor_thread
    def tearDown(self):
        self.sqlitedb.close()
        self.sqlitedb = None
        self.session.del_instance()
        self.session = None

        super(AbstractDB, self).tearDown(self)


class TestSqliteBasicDBHandler(AbstractDB):

    def setUp(self):
        super(TestSqliteBasicDBHandler, self).setUp()
        self.db = BasicDBHandler(self.session, u"Peer")

    @blocking_call_on_reactor_thread
    def test_size(self):
        size = self.db.size()  # there are 3995 peers in the table, however the upgrade scripts remove 8 superpeers
        assert size == 3987, size
