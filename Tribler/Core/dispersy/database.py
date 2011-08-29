# Python 2.5 features
from __future__ import with_statement

"""
This module provides basic database functionalty and simple version control.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

import thread
import hashlib
import sqlite3

from singleton import Singleton

if __debug__:
    from dprint import dprint

class Database(Singleton):
    def __init__(self, file_path):
        """
        Initialize a new Database instance.

        @param file_path: the path to the database file.
        @type file_path: unicode
        """
        if __debug__:
            assert isinstance(file_path, unicode)
            dprint(file_path)
            self._debug_thread_ident = thread.get_ident()
            self._debug_file_path = file_path

        self._connection = sqlite3.Connection(file_path)
        # self._connection.setrollbackhook(self._on_rollback)
        self._cursor = self._connection.cursor()

        #
        # PRAGMA synchronous = 0 | OFF | 1 | NORMAL | 2 | FULL;
        #
        # Query or change the setting of the "synchronous" flag.  The first (query) form will return
        # the synchronous setting as an integer.  When synchronous is FULL (2), the SQLite database
        # engine will use the xSync method of the VFS to ensure that all content is safely written
        # to the disk surface prior to continuing.  This ensures that an operating system crash or
        # power failure will not corrupt the database.  FULL synchronous is very safe, but it is
        # also slower.  When synchronous is NORMAL (1), the SQLite database engine will still sync
        # at the most critical moments, but less often than in FULL mode.  There is a very small
        # (though non-zero) chance that a power failure at just the wrong time could corrupt the
        # database in NORMAL mode.  But in practice, you are more likely to suffer a catastrophic
        # disk failure or some other unrecoverable hardware fault.  With synchronous OFF (0), SQLite
        # continues without syncing as soon as it has handed data off to the operating system.  If
        # the application running SQLite crashes, the data will be safe, but the database might
        # become corrupted if the operating system crashes or the computer loses power before that
        # data has been written to the disk surface.  On the other hand, some operations are as much
        # as 50 or more times faster with synchronous OFF.
        #
        # The default setting is synchronous = FULL.
        #
        if __debug__: dprint("PRAGMA synchronous = NORMAL")
        self._cursor.execute(u"PRAGMA synchronous = NORMAL")

        # check is the database contains an 'option' table
        try:
            count, = self.execute(u"SELECT COUNT(1) FROM sqlite_master WHERE type = 'table' AND name = 'option'").next()
        except StopIteration:
            raise RuntimeError()

        if count:
            # get version from required 'option' table
            try:
                version, = self.execute(u"SELECT value FROM option WHERE key == 'database_version' LIMIT 1").next()
            except StopIteration:
                # the 'database_version' key was not found
                version = u"0"
        else:
            # the 'option' table probably hasn't been created yet
            version = u"0"

        self.check_database(version)

    def __enter__(self):
        """
        Enter a database transaction block.

        Using the __enter__ and __exit__ methods we can group multiple insert and update queries
        together, causing only one transaction block to be used, hence increasing database
        performance.  When __exit__ is called the transaction block is commited.

        >>> with database as execute:
        >>>    execute(u"INSERT INTO ...")
        >>>    execute(u"INSERT INTO ...")
        >>>    execute(u"INSERT INTO ...")

        @return: The method self.execute
        """
        if __debug__: dprint("COMMIT")
        self._connection.commit()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit a database transaction block.

        Using the __enter__ and __exit__ methods we can group multiple insert and update queries
        together, causing only one transaction block to be used, hence increasing database
        performance.  When __exit__ is called the transaction block is commited.
        """
        if exc_type is None:
            if __debug__: dprint("COMMIT")
            self._connection.commit()
            return True
        else:
            if __debug__: dprint("ROLLBACK", level="error")
            self._connection.rollback()
            return False

    @property
    def last_insert_rowid(self):
        """
        The row id of the most recent insert query.
        @rtype: int or long
        """
        assert self._debug_thread_ident == thread.get_ident()
        assert not self._cursor.lastrowid is None, "The last statement was NOT an insert query"
        return self._cursor.lastrowid

    @property
    def changes(self):
        """
        The number of changes that resulted from the most recent query.
        @rtype: int or long
        """
        assert self._debug_thread_ident == thread.get_ident()
        return self._cursor.rowcount
        # return self._connection.changes()

    def execute(self, statement, bindings=()):
        """
        Execute one SQL statement.

        A SQL query must be presented in unicode format.  This is to ensure that no unicode
        exeptions occur when the bindings are merged into the statement.

        Furthermore, the bindings may not contain any strings either.  For a 'string' the unicode
        type must be used.  For a binary string the buffer(...) type must be used.

        The SQL query may contain placeholder entries defined with a '?'.  Each of these
        placeholders will be used to store one value from bindings.  The placeholders are filled by
        sqlite and all proper escaping is done, making this the preferred way of adding variables to
        the SQL query.

        @param statement: the SQL statement that is to be executed.
        @type statement: unicode

        @param bindings: the values that must be set to the placeholders in statement.
        @type bindings: tuple

        @returns: unknown
        @raise sqlite.Error: unknown
        """
        assert self._debug_thread_ident == thread.get_ident(), "Calling Database.execute on the wrong thread"
        assert isinstance(statement, unicode), "The SQL statement must be given in unicode"
        assert isinstance(bindings, (tuple, list, dict)), "The bindings must be a tuple, list, or dictionary"
        assert not filter(lambda x: isinstance(x, str), bindings), "The bindings may not contain a string. \nProvide unicode for TEXT and buffer(...) for BLOB. \nGiven types: %s" % str([type(binding) for binding in bindings])

        try:
            if __debug__: dprint(statement, " <-- ", bindings)
            return self._cursor.execute(statement, bindings)

        except sqlite3.Error, exception:
            if __debug__:
                dprint(exception=True, level="warning")
                dprint("Filename: ", self._debug_file_path, level="warning")
                dprint(statement, level="warning")
                dprint(bindings, level="warning")
            raise

    def executescript(self, statements):
        assert self._debug_thread_ident == thread.get_ident(), "Calling Database.execute on the wrong thread"
        assert isinstance(statements, unicode), "The SQL statement must be given in unicode"

        try:
            if __debug__: dprint(statements)
            return self._cursor.executescript(statements)

        except sqlite3.Error, exception:
            if __debug__:
                dprint(exception=True, level="warning")
                dprint("Filename: ", self._debug_file_path, level="warning")
                dprint(statements, level="warning")
            raise

    def executemany(self, statement, sequenceofbindings):
        """
        Execute one SQL statement several times.

        All SQL queries must be presented in unicode format.  This is to ensure that no unicode
        exeptions occur when the bindings are merged into the statement.

        Furthermore, the bindings may not contain any strings either.  For a 'string' the unicode
        type must be used.  For a binary string the buffer(...) type must be used.

        The SQL query may contain placeholder entries defined with a '?'.  Each of these
        placeholders will be used to store one value from bindings.  The placeholders are filled by
        sqlite and all proper escaping is done, making this the preferred way of adding variables to
        the SQL query.

        @param statement: the SQL statement that is to be executed.
        @type statement: unicode

        @param bindings: a sequence of values that must be set to the placeholders in statement.
         Each element in sequence is another tuple containing bindings.
        @type bindings: list containing tuples

        @returns: unknown
        @raise sqlite.Error: unknown
        """
        assert self._debug_thread_ident == thread.get_ident(), "Calling Database.execute on the wrong thread"
        if __debug__:
            # we allow GeneratorType but must convert it to a list in __debug__ mode since a
            # generator can only iterate once
            from types import GeneratorType
            if isinstance(sequenceofbindings, GeneratorType):
                sequenceofbindings = list(sequenceofbindings)
        assert isinstance(statement, unicode), "The SQL statement must be given in unicode"
        assert isinstance(sequenceofbindings, (tuple, list)), "The sequenceofbindings must be a list with tuples, lists, or dictionaries"
        assert not filter(lambda x: not isinstance(x, (tuple, list, dict)), list(sequenceofbindings)), "The sequenceofbindings must be a list with tuples, lists, or dictionaries"
        assert not filter(lambda x: filter(lambda y: isinstance(y, str), x), list(sequenceofbindings)), "The bindings may not contain a string. \nProvide unicode for TEXT and buffer(...) for BLOB."

        try:
            if __debug__: dprint(statement)
            return self._cursor.executemany(statement, sequenceofbindings)

        except sqlite3.Error, exception:
            if __debug__:
                dprint(exception=True)
                dprint("Filename: ", self._debug_file_path)
                dprint(statement)
            raise

    def commit(self):
        if __debug__: dprint("COMMIT")
        return self._connection.commit()

    # def _on_rollback(self):
    #     if __debug__: dprint("ROLLBACK", level="warning")
    #     raise DatabaseRollbackException(1)

    def check_database(self, database_version):
        """
        Check the database and upgrade if required.

        This method is called once for each Database instance to ensure that the database structure
        and version is correct.  Each Database must contain one table of the structure below where
        the database_version is stored.  This value is used to keep track of the current database
        version.

        >>> CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
        >>> INSERT INTO option(key, value) VALUES('database_version', '1');

        @param database_version: the current database_version value from the option table. This
         value reverts to u'0' when the table could not be accessed.
        @type database_version: unicode
        """
        raise NotImplementedError()

if __debug__:
    if __name__ == "__main__":
        class TestDatabase(Database):
            def check_database(self, database_version):
                pass

        import time

        db = TestDatabase(u"test.db")
        db.execute(u"CREATE TABLE pair (key INTEGER, value TEXT)")

        a = time.time()
        for i in xrange(1000):
            db.execute(u"INSERT INTO pair (key, value) VALUES (?, ?)", (i, u"-%d-" % i))

        b = time.time()
        with db:
            for i in xrange(1000):
                db.execute(u"INSERT INTO pair (key, value) VALUES (?, ?)", (i, u"-%d-" % i))

        c = time.time()
        for i in xrange(1000):
            for row in db.execute(u"SELECT * FROM pair WHERE key = ?", (u"-%d-" % i,)):
                pass

        d = time.time()
        for i in xrange(2000, 3000):
            db.execute(u"INSERT INTO pair (key, value) VALUES (?, ?)", (i, u"-%d-" % i))

        try:
            db.execute(u"INSERT INTO invalid_table_name (foo, bar) VALUES (42, 42)")
            print "ERROR"
            assert False
        except:
            pass

        l = list(db.execute(u"SELECT * FROM pair WHERE key BETWEEN 2000 AND 3000"))
        if not len(l) == 1000:
            print "ERROR"
            assert False

        try:
            with db:
                db.execute(u"INSERT INTO pair (key, value) VALUES ('foo', 'bar')")
                db.execute(u"INSERT INTO invalid_table_name (foo, bar) VALUES (42, 42)")
        except:
            pass
        # there should not be a foo/bar entry
        try:
            key, value = db.execute(u"SELECT key, value FROM pair WHERE key = 'foo'").next()
            print "ERROR"
            assert False
        except StopIteration:
            pass

        try:
            with db:
                db.executescript(u"""
INSERT INTO pair (key, value) VALUES ('foo', 'bar');
INSERT INTO invalid_table_name (foo, bar) VALUES (42, 42);
""")
        except sqlite3.OperationalError, e:
            assert str(e) == "no such table: invalid_table_name", e
        # there should not be a foo/bar entry
        try:
            key, value = db.execute(u"SELECT key, value FROM pair WHERE key = 'foo'").next()
            print "ERROR"
            assert False
        except StopIteration:
            pass

        e = time.time()
        db.commit()

        f = time.time()
        print "implicit insert:", b - a
        print "explicit insert:", c - b
        print "select:", d - c
        print "test1: ", e - d
        print "close: ", f - e
