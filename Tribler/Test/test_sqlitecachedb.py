import unittest
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB


class TestSqliteCacheDB(unittest.TestCase):

    def setUp(self):
        self.sqlite_test = SQLiteCacheDB.getInstance()
        self.db_path = u":memory:"
        self.sqlite_test.initDB(self.db_path)

    def tearDown(self):
        SQLiteCacheDB.getInstance().close_all()
        SQLiteCacheDB.delInstance()

    def test_create_db(self):
        sql = "create table person(lastname, firstname);"
        self.sqlite_test._execute(sql)

    def test_get_del_instance(self):
        SQLiteCacheDB.delInstance()
        sqlite_test2 = SQLiteCacheDB.getInstance()

        assert sqlite_test2 != self.sqlite_test

    def test_insert(self):
        self.test_create_db()

        self.sqlite_test.insert('person', lastname='a', firstname='b')
        assert self.sqlite_test.size('person') == 1

    def test_fetchone(self):
        self.test_insert()
        one = self.sqlite_test.fetchone('select * from person')
        assert one == ('a', 'b')

        one = self.sqlite_test.fetchone("select lastname from person where firstname == 'b'")
        assert one == 'a'

        one = self.sqlite_test.fetchone("select lastname from person where firstname == 'c'")
        assert one == None

    def test_insertmany(self):
        self.test_create_db()

        values = []
        for i in range(100):
            value = (str(i), str(i ** 2))
            values.append(value)
        self.sqlite_test.insertMany('person', values)
        assert self.sqlite_test.size('person') == 100

    def test_fetchall(self):
        self.test_insertmany()

        all = self.sqlite_test.fetchall('select * from person')
        assert len(all) == 100

        all = self.sqlite_test.fetchall("select * from person where lastname=='101'")
        assert all == []

    def test_insertorder(self):
        self.test_insertmany()

        self.sqlite_test.insert('person', lastname='1', firstname='abc')
        one = self.sqlite_test.fetchone("select firstname from person where lastname == '1'")
        assert one == '1' or one == 'abc'

        all = self.sqlite_test.fetchall("select firstname from person where lastname == '1'")
        assert len(all) == 2

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
