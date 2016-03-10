import os

from Tribler.Test.test_as_server import AbstractServer
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, DB_SCRIPT_RELATIVE_PATH
from Tribler.dispersy.util import blocking_call_on_reactor_thread


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

        db_path = u":memory:"
        db_script_path = os.path.join(self.session.get_install_dir(), DB_SCRIPT_RELATIVE_PATH)

        self.sqlite_test = SQLiteCacheDB(db_path, db_script_path)
        self.sqlite_test.initialize()

    def tearDown(self):
        super(TestSqliteCacheDB, self).tearDown()
        self.sqlite_test.close()
        self.sqlite_test = None
        self.session.del_instance()
        self.session = None

    @blocking_call_on_reactor_thread
    def test_create_db(self):
        sql = u"CREATE TABLE person(lastname, firstname);"
        self.sqlite_test.execute(sql)

    @blocking_call_on_reactor_thread
    def test_insert(self):
        self.test_create_db()

        self.sqlite_test.insert('person', lastname='a', firstname='b')
        assert self.sqlite_test.size('person') == 1

    @blocking_call_on_reactor_thread
    def test_fetchone(self):
        self.test_insert()
        one = self.sqlite_test.fetchone(u"SELECT * FROM person")
        assert one == ('a', 'b')

        one = self.sqlite_test.fetchone(u"SELECT lastname FROM person WHERE firstname == 'b'")
        assert one == 'a'

        one = self.sqlite_test.fetchone(u"SELECT lastname FROM person WHERE firstname == 'c'")
        assert one is None

    @blocking_call_on_reactor_thread
    def test_insertmany(self):
        self.test_create_db()

        values = []
        for i in range(100):
            value = (str(i), str(i ** 2))
            values.append(value)
        self.sqlite_test.insertMany('person', values)
        assert self.sqlite_test.size('person') == 100

    @blocking_call_on_reactor_thread
    def test_fetchall(self):
        self.test_insertmany()

        all = self.sqlite_test.fetchall('select * from person')
        assert len(all) == 100

        all = self.sqlite_test.fetchall("select * from person where lastname=='101'")
        assert all == []

    @blocking_call_on_reactor_thread
    def test_insertorder(self):
        self.test_insertmany()

        self.sqlite_test.insert('person', lastname='1', firstname='abc')
        one = self.sqlite_test.fetchone("select firstname from person where lastname == '1'")
        assert one == '1' or one == 'abc'

        all = self.sqlite_test.fetchall("select firstname from person where lastname == '1'")
        assert len(all) == 2

    @blocking_call_on_reactor_thread
    def test_update(self):
        self.test_insertmany()

        self.sqlite_test.update('person', "lastname == '2'", firstname='56')
        one = self.sqlite_test.fetchone("select firstname from person where lastname == '2'")
        assert one == '56', one

        self.sqlite_test.update('person', "lastname == '3'", firstname=65)
        one = self.sqlite_test.fetchone("select firstname from person where lastname == '3'")
        assert one == 65, one

        self.sqlite_test.update('person', "lastname == '4'", firstname=654, lastname=44)
        one = self.sqlite_test.fetchone("select firstname from person where lastname == 44")
        assert one == 654, one
