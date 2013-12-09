import unittest
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB


class TestSqliteCacheDB(unittest.TestCase):

    def setUp(self):
        self.sqlite_test = SQLiteCacheDB.getInstance()
        self.db_path = ':memory:'

        self._table_name = u'Person'

    def tearDown(self):
        SQLiteCacheDB.getInstance().close_all()
        SQLiteCacheDB.delInstance()

    def test_open_db(self):
        self.sqlite_test.openDB(self.db_path, 0)

    def test_create_db(self):
        sql = "create table person(lastname, firstname);"
        self.sqlite_test.createDBTable(sql, self.db_path)

    def test_get_del_instance(self):
        SQLiteCacheDB.delInstance()
        sqlite_test2 = SQLiteCacheDB.getInstance()

        assert sqlite_test2 != self.sqlite_test

    def test_insert_one(self):
        """Tests the new_insertOne() method.
        """
        self.test_create_db()

        column_tuple = (u'lastname', u'firstname')
        value_tuple = (u'a', u'b')
        self.sqlite_test.new_insertOne(self._table_name,
            column_tuple, value_tuple)

        assert self.sqlite_test.size(self._table_name) == 1

    def test_insert_many(self):
        """Tests the new_insertMany() method.
        """
        self.test_create_db()

        column_tuple = (u'lastname', u'firstname')
        value_tuple_list = list()
        for i in xrange(100):
            value = (str(i), str(i ** 2))
            value_tuple_list.append(value)

        self.sqlite_test.new_insertMany(self._table_name,
            column_tuple, value_tuple_list)

        assert self.sqlite_test.size(self._table_name) == 100

    def test_get_one(self):
        """Tests the new_getOne() method.
        """
        self.test_insert_one()

        column_tuple = (u'lastname', u'firstname')
        result = self.sqlite_test.new_getOne(self._table_name, column_tuple)
        assert result == (u'a', u'b'), result

        column_tuple = (u'lastname',)
        where_column_tuple = (u'firstname',)
        where_value_tuple = (u'b',)
        result = self.sqlite_test.new_getOne(self._table_name, column_tuple,
                    where_column_tuple, where_value_tuple)
        assert result == u'a', result

        column_tuple = (u'lastname',)
        where_column_tuple = (u'firstname',)
        where_value_tuple = (u'c',)
        result = self.sqlite_test.new_getOne(self._table_name, column_tuple,
                    where_column_tuple, where_value_tuple)
        assert result is None, result

    def test_get_all(self):
        """Tests the new_getAll() method.
        """
        self.test_insert_many()

        column_tuple = (u'lastname', u'firstname')
        result = self.sqlite_test.new_getMany(self._table_name, column_tuple)
        assert len(result) == 100, result

        column_tuple = (u'lastname', u'firstname')
        where_column_tuple = (u'lastname',)
        where_value_tuple = (u'101',)
        result = self.sqlite_test.new_getMany(self._table_name, column_tuple,
                    where_column_tuple, where_value_tuple)
        assert len(result) == 0, result

    def test_update_one(self):
        """Tests the new_updateOne() method.
        """
        self.test_create_db()

        column_tuple = (u'lastname', u'firstname')

        # insert a record: (a,b)
        value_tuple = (u'a', u'b')
        self.sqlite_test.new_insertOne(self._table_name,
            column_tuple, value_tuple)
        assert self.sqlite_test.size(self._table_name) == 1

        # update the record: (a,b) -> (c,d)
        value_tuple = (u'c', u'd')
        where_column_tuple = (u'lastname', u'firstname')
        where_value_tuple = (u'a', u'b')
        self.sqlite_test.new_updateOne(self._table_name,
            column_tuple, value_tuple,
            where_column_tuple, where_value_tuple)

        result = self.sqlite_test.new_getOne(self._table_name, column_tuple)
        assert result == (u'c', u'd'), result

        where_column_tuple = (u'lastname',)
        where_value_tuple = (u'a',)
        result = self.sqlite_test.new_getOne(self._table_name, column_tuple,
            where_column_tuple, where_value_tuple)
        assert result is None, result

    def test_update_many(self):
        """Tests the new_updateMany() method.
        """
        self.test_create_db()

        column_tuple = (u'lastname', u'firstname')

        # insert two records: (1,2) and (a,b)
        value_tuple_list = list()
        value_tuple_list.append((u'1', u'2'))
        value_tuple_list.append((u'a', u'b'))
        self.sqlite_test.new_insertMany(self._table_name,
            column_tuple, value_tuple_list)
        assert self.sqlite_test.size(self._table_name) == 2

        # update the two records: (1,2) -> (3,4) and (a,b) -> (c,d)
        where_column_tuple = (u'lastname', u'firstname')

        value_tuple_list = list()
        value_tuple_list.append((u'3', u'4'))
        value_tuple_list.append((u'c', u'd'))
        where_value_tuple_list = list()
        where_value_tuple_list.append((u'1', u'2'))
        where_value_tuple_list.append((u'a', u'b'))
        self.sqlite_test.new_updateMany(self._table_name,
            column_tuple, value_tuple_list,
            where_column_tuple, where_value_tuple_list)

        column_tuple = (u'lastname', u'firstname')
        result = self.sqlite_test.new_getMany(self._table_name, column_tuple)
        assert (u'3', u'4') in result, result
        assert (u'c', u'd') in result, result
        assert (u'1', u'2') not in result, result
        assert (u'a', u'b') not in result, result

    def test_insert_order(self):
        """TODO: I am not sure what this test is for. Someone may add comments.
        """
        self.test_insert_many()

        column_tuple = (u'lastname', u'firstname')
        value_tuple = (u'1', u'abc')
        self.sqlite_test.new_insertOne(self._table_name,
            column_tuple, value_tuple)

        column_tuple = (u'firstname',)
        where_column_tuple = (u'lastname',)
        where_value_tuple = (u'1')
        result = self.sqlite_test.new_getOne(self._table_name,
            column_tuple, where_column_tuple, where_value_tuple)
        assert result == '1' or result == 'abc'

        result = self.sqlite_test.new_getMany(self._table_name,
            column_tuple, where_column_tuple, where_value_tuple)
        assert len(result) == 2