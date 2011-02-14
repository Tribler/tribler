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

        # database configuration (pragma)
        if __debug__:
            cache_size, = self._cursor.execute(u"PRAGMA cache_size").next()
            page_size, = self._cursor.execute(u"PRAGMA page_size").next()
            page_count, = self._cursor.execute(u"PRAGMA page_count").next()
            dprint("page_size: ", page_size, " (for currently ", page_count * page_size, " bytes in database)")
            dprint("cache_size: ", cache_size, " (for maximal ", cache_size * page_size, " bytes in memory)")

        synchronous, = self._cursor.execute(u"PRAGMA synchronous").next()
        if __debug__: dprint("synchronous: ", synchronous, " (", {0:"OFF", 1:"NORMAL", 2:"FULL"}[synchronous])
        if not synchronous == 0:
            if __debug__: dprint("synchronous: ", synchronous, " (", {0:"OFF", 1:"NORMAL", 2:"FULL"}[synchronous], ") --> 0 (OFF)")
            self._cursor.execute(u"PRAGMA synchronous = 0")

        temp_store, = self._cursor.execute(u"PRAGMA temp_store").next()
        if __debug__: dprint("temp_store: ", temp_store, " (", {0:"DEFAULT", 1:"FILE", 2:"MEMORY"}[temp_store])
        if not temp_store == 3:
            if __debug__: dprint("temp_store: ", temp_store, " (", {0:"DEFAULT", 1:"FILE", 2:"MEMORY"}[temp_store], ") --> 3 (MEMORY)")
            self._cursor.execute(u"PRAGMA temp_store = 3")

        # get version from required 'option' table
        try:
            version, = self.execute(u"SELECT value FROM option WHERE key == 'database_version' LIMIT 1").next()
        except sqlite3.Error:
            # the 'option' table probably hasn't been created yet
            version = u"0"
        except StopIteration:
            # the 'database_version' key was not found
            version = u"0"

        self.check_database(version)

    def __enter__(self):
        """
        Start a database transaction block.

        Each insert or update query requires a transaction block.  The sqlite3 module that we use
        will create transaction blocks automatically.  However, a transaction block needs to be
        committed.

        Using the __enter__ and __exit__ methods we can group multiple insert and update queries
        together, causing only one transaction block to be used, hence increasing database
        performance.  When __exit__ is called the transaction block is commited.

        >>> with database as execute:
        >>>    execute(u"INSERT INTO ...")
        >>>    execute(u"INSERT INTO ...")
        >>>    execute(u"INSERT INTO ...")

        @return: The method self.execute
        """
        self._connection.__enter__()
        return self.execute

    def __exit__(self, exc_type, exc_value, traceback):
        """
        End a database transaction block.

        @see: _enter__
        """
        return self._connection.__exit__(exc_type, exc_value, traceback)

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

    def execute(self, statements, bindings=()):
        """
        Execute one of more SQL statements.

        All SQL queries must be presented in unicode format.  This is to ensure that no unicode
        exeptions occur when the bindings are merged into the statements.

        Furthermore, the bindings may not contain any strings either.  For a 'string' the unicode
        type must be used.  For a binary string the buffer(...) type must be used.

        The SQL query may contain placeholder entries defined with a '?'.  Each of these
        placeholders will be used to store one value from bindings.  The placeholders are filled by
        sqlite and all proper escaping is done, making this the preferred way of adding variables to
        the SQL query.

        @param statements: the SQL statements that are to be executed.
        @type statements: unicode

        @param bindings: the values that must be set to the placeholders in statements.
        @type bindings: tuple

        @returns: unknown
        @raise sqlite.Error: unknown
        """
        assert self._debug_thread_ident == thread.get_ident(), "Calling Database.execute on the wrong thread"
        assert isinstance(statements, unicode), "The SQL statement must be given in unicode"
        assert isinstance(bindings, (tuple, list, dict)), "The bindinds must be a tuple, list, or dictionary"
        assert not filter(lambda x: isinstance(x, str), bindings), "The bindings may not contain a string. \nProvide unicode for TEXT and buffer(...) for BLOB. \nGiven types: %s" % str([type(binding) for binding in bindings])
        if __debug__:
            changes_before = self._connection.total_changes
            dprint(statements, " <-- ", bindings)
        try:
            return self._cursor.execute(statements, bindings)

        except sqlite3.Error, exception:
            if __debug__:
                dprint(exception=True, level="warning")
                dprint("Filename: ", self._debug_file_path, level="warning")
                dprint("Changes (UPDATE, INSERT, DELETE): ", self._connection.total_changes - changes_before, level="warning")
                dprint(statements, level="warning")
                dprint(bindings, level="warning")
            raise

    def executescript(self, statements):
        assert self._debug_thread_ident == thread.get_ident(), "Calling Database.execute on the wrong thread"
        assert isinstance(statements, unicode), "The SQL statement must be given in unicode"
        if __debug__:
            changes_before = self._connection.total_changes
            dprint(statements)
        try:
            return self._cursor.executescript(statements)

        except sqlite3.Error, exception:
            if __debug__:
                dprint(exception=True, level="warning")
                dprint("Filename: ", self._debug_file_path, level="warning")
                dprint("Changes (UPDATE, INSERT, DELETE): ", self._connection.total_changes - changes_before, level="warning")
                dprint(statements, level="warning")
            raise

    def executemany(self, statements, sequenceofbindings):
        """
        Execute one of more SQL statements several times.

        All SQL queries must be presented in unicode format.  This is to ensure that no unicode
        exeptions occur when the bindings are merged into the statements.

        Furthermore, the bindings may not contain any strings either.  For a 'string' the unicode
        type must be used.  For a binary string the buffer(...) type must be used.

        The SQL query may contain placeholder entries defined with a '?'.  Each of these
        placeholders will be used to store one value from bindings.  The placeholders are filled by
        sqlite and all proper escaping is done, making this the preferred way of adding variables to
        the SQL query.

        @param statements: the SQL statements that are to be executed.
        @type statements: unicode

        @param bindings: a sequence of values that must be set to the placeholders in statements.
         Each element in sequence is another tuple containing bindings.
        @type bindings: list containing tuples

        @returns: unknown
        @raise sqlite.Error: unknown
        """
        assert self._debug_thread_ident == thread.get_ident()
        assert isinstance(statements, unicode)
        assert isinstance(sequenceofbindings, (tuple, list))
        assert not filter(lambda x: isinstance(x, (tuple, list, dict)), sequenceofbindings)
        assert not filter(lambda x: not filter(lambda y: isinstance(y, str), bindings), sequenceofbindings), "None of the bindings may be string type"
        if __debug__:
            changes_before = self._connection.total_changes
            dprint(statements)
        try:
            return self._cursor.executemany(statements, sequenceofbindings)

        except sqlite3.Error, exception:
            if __debug__:
                dprint(exception=True)
                dprint("Filename: ", self._debug_file_path)
                dprint("Changes (UPDATE, INSERT, DELETE): ", self._connection.total_changes - changes_before)
                dprint(statements)
            raise

    def commit(self):
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
