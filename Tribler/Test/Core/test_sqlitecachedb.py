import os
import sys
import shutil

from apsw import SQLError, CantOpenError
from unittest import skipIf
from nose.tools import raises
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, DB_SCRIPT_NAME, CorruptedDatabaseError
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestSqliteCacheDB(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    SQLITE_SCRIPTS_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/sqlite_scripts/"))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(TestSqliteCacheDB, self).setUp()

        db_path = u":memory:"

        self.sqlite_test = SQLiteCacheDB(db_path)
        self.sqlite_test.set_show_sql(True)
        self.sqlite_test.initialize()

        import Tribler
        self.tribler_db_script = os.path.join(os.path.dirname(Tribler.__file__), DB_SCRIPT_NAME)

    def tearDown(self):
        super(TestSqliteCacheDB, self).tearDown()
        self.sqlite_test.close()
        self.sqlite_test = None

    @blocking_call_on_reactor_thread
    def test_create_db(self):
        sql = u"CREATE TABLE person(lastname, firstname);"
        self.sqlite_test.execute(sql)

        self.assertIsInstance(self.sqlite_test.version, int)

    @blocking_call_on_reactor_thread
    @raises(OSError)
    def test_no_file_db_error(self):
        file_dir = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
        sqlite_test_2 = SQLiteCacheDB(file_dir)
        sqlite_test_2.initialize()

    @blocking_call_on_reactor_thread
    def test_open_db_new_file(self):
        db_path = os.path.join(self.session_base_dir, "test_db.db")
        sqlite_test_2 = SQLiteCacheDB(db_path)
        sqlite_test_2.initialize()
        self.assertTrue(os.path.isfile(db_path))

    @blocking_call_on_reactor_thread
    @raises(OSError)
    def test_open_db_script_file_invalid_location(self):
        sqlite_test_2 = SQLiteCacheDB(os.path.join(self.session_base_dir, "test_db.db"), u'myfakelocation')
        sqlite_test_2.initialize()

    @blocking_call_on_reactor_thread
    @raises(OSError)
    def test_open_db_script_file_directory(self):
        file_dir = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
        sqlite_test_2 = SQLiteCacheDB(os.path.join(self.session_base_dir, "test_db.db"), file_dir)
        sqlite_test_2.initialize()

    @blocking_call_on_reactor_thread
    def test_open_db_script_file(self):
        sqlite_test_2 = SQLiteCacheDB(os.path.join(self.session_base_dir, "test_db.db"), self.tribler_db_script)
        sqlite_test_2.initialize()

        sqlite_test_2.initial_begin()
        sqlite_test_2.write_version(4)
        self.assertEqual(sqlite_test_2.version, 4)

    @blocking_call_on_reactor_thread
    def test_initial_begin(self):
        self.sqlite_test.initial_begin()

    @blocking_call_on_reactor_thread
    @raises(SQLError)
    def test_failed_commit(self):
        sqlite_test_2 = SQLiteCacheDB(os.path.join(self.session_base_dir, "test_db.db"), self.tribler_db_script)
        sqlite_test_2.initialize()
        sqlite_test_2.write_version(4)

    @blocking_call_on_reactor_thread
    @raises(Exception)
    def test_initial_begin_no_connection(self):
        db_path = os.path.join(self.session_base_dir, "test_db.db")
        sqlite_test_2 = SQLiteCacheDB(db_path)
        sqlite_test_2.initial_begin()

    @blocking_call_on_reactor_thread
    @skipIf(sys.platform == "win32", "chmod does not work on Windows")
    @raises(IOError)
    def test_no_permission_on_script(self):
        db_path = os.path.join(self.session_base_dir, "test_db.db")
        new_script_path = os.path.join(self.session_base_dir, "script.sql")
        shutil.copyfile(self.tribler_db_script, new_script_path)
        os.chmod(new_script_path, 0)
        sqlite_test_2 = SQLiteCacheDB(db_path, new_script_path)
        sqlite_test_2.initialize()

    @blocking_call_on_reactor_thread
    @raises(CorruptedDatabaseError)
    def test_no_version_info_in_database(self):
        sqlite_test_2 = SQLiteCacheDB(os.path.join(self.session_base_dir, "test_db.db"),
                                      os.path.join(self.SQLITE_SCRIPTS_DIR, "script1.sql"))
        sqlite_test_2.initialize()

    @blocking_call_on_reactor_thread
    def test_clean_db(self):
        sqlite_test_2 = SQLiteCacheDB(os.path.join(self.session_base_dir, "test_db.db"), self.tribler_db_script)
        sqlite_test_2.initialize()
        sqlite_test_2.initial_begin()
        sqlite_test_2.clean_db(vacuum=True, exiting=True)

    @blocking_call_on_reactor_thread
    @skipIf(sys.platform == "win32", "chmod does not work on Windows")
    @raises(CantOpenError)
    def test_open_db_connection_no_permission(self):
        os.chmod(os.path.join(self.session_base_dir), 0)
        sqlite_test_2 = SQLiteCacheDB(os.path.join(self.session_base_dir, "test_db.db"))
        sqlite_test_2.initialize()

    @blocking_call_on_reactor_thread
    def test_insert(self):
        self.test_create_db()

        self.sqlite_test.insert('person', lastname='a', firstname='b')
        self.assertEqual(self.sqlite_test.size('person'), 1)

    @blocking_call_on_reactor_thread
    def test_fetchone(self):
        self.test_insert()
        one = self.sqlite_test.fetchone(u"SELECT * FROM person")
        self.assertEqual(one, ('a', 'b'))

        one = self.sqlite_test.fetchone(u"SELECT lastname FROM person WHERE firstname == 'b'")
        self.assertEqual(one, 'a')

        one = self.sqlite_test.fetchone(u"SELECT lastname FROM person WHERE firstname == 'c'")
        self.assertIsNone(one)

    @blocking_call_on_reactor_thread
    def test_insertmany(self):
        self.test_create_db()

        values = []
        for i in range(100):
            value = (str(i), str(i ** 2))
            values.append(value)
        self.sqlite_test.insertMany('person', values)
        self.assertEqual(self.sqlite_test.size('person'), 100)

    @blocking_call_on_reactor_thread
    def test_fetchall(self):
        self.test_insertmany()

        all = self.sqlite_test.fetchall('select * from person')
        self.assertEqual(len(all), 100)

        all = self.sqlite_test.fetchall("select * from person where lastname=='101'")
        self.assertEqual(all, [])

    @blocking_call_on_reactor_thread
    def test_insertorder(self):
        self.test_insertmany()

        self.sqlite_test.insert('person', lastname='1', firstname='abc')
        one = self.sqlite_test.fetchone("select firstname from person where lastname == '1'")
        self.assertTrue(one == '1' or one == 'abc')

        all = self.sqlite_test.fetchall("select firstname from person where lastname == '1'")
        self.assertEqual(len(all), 2)

    @blocking_call_on_reactor_thread
    def test_update(self):
        self.test_insertmany()

        self.sqlite_test.update('person', "lastname == '2'", firstname='56')
        one = self.sqlite_test.fetchone("select firstname from person where lastname == '2'")
        self.assertEqual(one, '56')

        self.sqlite_test.update('person', "lastname == '3'", firstname=65)
        one = self.sqlite_test.fetchone("select firstname from person where lastname == '3'")
        self.assertEqual(one, 65)

        self.sqlite_test.update('person', "lastname == '4'", firstname=654, lastname=44)
        one = self.sqlite_test.fetchone("select firstname from person where lastname == 44")
        self.assertEqual(one, 654)

    @blocking_call_on_reactor_thread
    def test_delete_single_element(self):
        """
        This test tests whether deleting using a single element as value works.
        """
        self.test_insert()
        self.sqlite_test.insert('person', lastname='x', firstname='z')
        one = self.sqlite_test.fetchone(u"SELECT * FROM person")
        self.assertEqual(one, ('a', 'b'))
        self.sqlite_test.delete("person", lastname="a")
        one = self.sqlite_test.fetchone(u"SELECT * FROM person")
        self.assertEqual(one, ('x', 'z'))

    @blocking_call_on_reactor_thread
    def test_delete_tuple(self):
        """
        This test tests whether deleting using a tuple as value works.
        """
        self.test_insert()
        self.sqlite_test.insert('person', lastname='x', firstname='z')
        one = self.sqlite_test.fetchone(u"SELECT * FROM person")
        self.assertEqual(one, ('a', 'b'))
        self.sqlite_test.delete("person", lastname=("LIKE", "a"))
        one = self.sqlite_test.fetchone(u"SELECT * FROM person")
        self.assertEqual(one, ('x', 'z'))
