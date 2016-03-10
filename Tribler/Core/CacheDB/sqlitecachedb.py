# Written by Jie Yang
# see LICENSE.txt for license information
import logging
import os
from base64 import encodestring, decodestring
from threading import currentThread, RLock

import apsw
from apsw import CantOpenError, SQLError
from twisted.python.threadable import isInIOThread

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread

from Tribler import LIBRARYNAME
from Tribler.Core.CacheDB.db_versions import LATEST_DB_VERSION


DB_SCRIPT_NAME = u"schema_sdb_v%s.sql" % str(LATEST_DB_VERSION)
DB_SCRIPT_RELATIVE_PATH = os.path.join(LIBRARYNAME, DB_SCRIPT_NAME)

DB_FILE_NAME = u"tribler.sdb"
DB_DIR_NAME = u"sqlite"
DB_FILE_RELATIVE_PATH = os.path.join(DB_DIR_NAME, DB_FILE_NAME)


DEFAULT_BUSY_TIMEOUT = 10000

TRHEADING_DEBUG = False

forceDBThread = call_on_reactor_thread
forceAndReturnDBThread = blocking_call_on_reactor_thread


class CorruptedDatabaseError(Exception):
    pass


def bin2str(bin_data):
    return encodestring(bin_data).replace("\n", "")


def str2bin(str_data):
    return decodestring(str_data)


class SQLiteCacheDB(TaskManager):

    def __init__(self, db_path, db_script_path, busytimeout=DEFAULT_BUSY_TIMEOUT):
        super(SQLiteCacheDB, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self._cursor_lock = RLock()
        self._cursor_table = {}

        self._connection = None
        self.sqlite_db_path = db_path
        self.db_script_path = db_script_path
        self._busytimeout = busytimeout  # busytimeout is in milliseconds

        self._version = None

        self._should_commit = False
        self._show_execute = False

    @property
    def version(self):
        """The version of this database."""
        return self._version

    @blocking_call_on_reactor_thread
    def initialize(self):
        """ Initializes the database. If the database doesn't exist, we create a new one. Otherwise, we check the
            version and upgrade to the latest version.
        """

        # open a connection to the database
        self._open_connection()

    @blocking_call_on_reactor_thread
    def close(self):
        self.cancel_all_pending_tasks()
        with self._cursor_lock:
            for cursor in self._cursor_table.itervalues():
                cursor.close()
            self._cursor_table = {}
            self._connection.close()
            self._connection = None

    def _open_connection(self):
        """ Opens a connection to the database. If the database doesn't exist, we create a new one and run the
            initialization SQL scripts. If the database doesn't exist, we simply connect to it.
            And finally, we read the database version.
        """
        # check if it is in memory
        is_in_memory = self.sqlite_db_path == u":memory:"
        is_new_db = is_in_memory

        # check if database file exists
        if not is_in_memory:
            if not os.path.exists(self.sqlite_db_path):
                # create a new one
                is_new_db = True
            elif not os.path.isfile(self.sqlite_db_path):
                msg = u"Not a file: %s" % self.sqlite_db_path
                raise OSError(msg)

        # create connection
        try:
            self._connection = apsw.Connection(self.sqlite_db_path)
            self._connection.setbusytimeout(self._busytimeout)
        except CantOpenError as e:
            msg = u"Failed to open connection to %s: %s" % (self.sqlite_db_path, e)
            raise CantOpenError(msg)

        cursor = self.get_cursor()

        # apply pragma
        page_size, = next(cursor.execute(u"PRAGMA page_size"))
        if page_size < 8192:
            # journal_mode and page_size only need to be set once.  because of the VACUUM this
            # is very expensive
            self._logger.info(u"begin page_size upgrade...")
            cursor.execute(u"PRAGMA journal_mode = DELETE;")
            cursor.execute(u"PRAGMA page_size = 8192;")
            cursor.execute(u"VACUUM;")
            self._logger.info(u"...end page_size upgrade")

        # http://www.sqlite.org/pragma.html
        # When synchronous is NORMAL, the SQLite database engine will still
        # pause at the most critical moments, but less often than in FULL
        # mode. There is a very small (though non-zero) chance that a power
        # failure at just the wrong time could corrupt the database in
        # NORMAL mode. But in practice, you are more likely to suffer a
        # catastrophic disk failure or some other unrecoverable hardware
        # fault.
        #
        cursor.execute(u"PRAGMA synchronous = NORMAL;")
        cursor.execute(u"PRAGMA cache_size = 10000;")

        # Niels 19-09-2012: even though my database upgraded to increase the pagesize it did not keep wal mode?
        # Enabling WAL on every starup
        cursor.execute(u"PRAGMA journal_mode = WAL;")

        # create tables if this is a new database
        if is_new_db:
            self._logger.info(u"Initializing new database...")
            # check if the SQL script exists
            if not os.path.exists(self.db_script_path):
                msg = u"SQL script doesn't exist: %s" % self.db_script_path
                raise OSError(msg)
            if not os.path.isfile(self.db_script_path):
                msg = u"SQL script is not a file: %s" % self.db_script_path
                raise OSError(msg)

            try:
                f = open(self.db_script_path, "r")
                sql_script = f.read()
                f.close()
            except IOError as e:
                msg = u"Failed to load SQL script %s: %s" % (self.db_script_path, e)
                raise IOError(msg)

            cursor.execute(sql_script)

        # read database version
        self._logger.info(u"Reading database version...")
        try:
            version_str, = cursor.execute(u"SELECT value FROM MyInfo WHERE entry == 'version'").next()
            self._version = int(version_str)
            self._logger.info(u"Current database version is %s", self._version)
        except (StopIteration, SQLError) as e:
            msg = u"Failed to load database version: %s" % e
            raise CorruptedDatabaseError(msg)

    def get_cursor(self):
        thread_name = currentThread().getName()

        with self._cursor_lock:
            if thread_name not in self._cursor_table:
                self._cursor_table[thread_name] = self._connection.cursor()
            return self._cursor_table[thread_name]

    @blocking_call_on_reactor_thread
    def initial_begin(self):
        try:
            self._logger.info(u"Beginning the first transaction...")
            self.execute(u"BEGIN;")

        except:
            self._logger.exception(u"Failed to begin the first transaction")
            raise
        self._should_commit = False

    @blocking_call_on_reactor_thread
    def write_version(self, version):
        assert isinstance(version, int), u"Invalid version type: %s is not int" % type(version)
        assert version <= LATEST_DB_VERSION, u"Invalid version value: %s > the latest %s" % (version, LATEST_DB_VERSION)

        sql = u"UPDATE MyInfo SET value = ? WHERE entry == 'version'"
        self.execute_write(sql, (version,))
        self.commit_now()
        self._version = version

    @call_on_reactor_thread
    def commit_now(self, vacuum=False, exiting=False):
        if self._should_commit and isInIOThread():
            try:
                self._logger.info(u"Start committing...")
                self.execute(u"COMMIT;")
            except:
                self._logger.exception(u"COMMIT FAILED")
                raise
            self._should_commit = False

            if vacuum:
                self._logger.info(u"Start vacuuming...")
                self.execute(u"VACUUM;")

            if not exiting:
                try:
                    self._logger.info(u"Beginning another transaction...")
                    self.execute(u"BEGIN;")
                except:
                    self._logger.exception(u"Failed to execute BEGIN")
                    raise
            else:
                self._logger.info(u"Exiting, not beginning another transaction")

        elif vacuum:
            self.execute(u"VACUUM;")

    def clean_db(self, vacuum=False, exiting=False):
        self.execute_write(u"DELETE FROM TorrentFiles WHERE torrent_id IN (SELECT torrent_id FROM CollectedTorrent)")
        self.execute_write(u"DELETE FROM Torrent WHERE name IS NULL"
                           u" AND torrent_id NOT IN (SELECT torrent_id FROM _ChannelTorrents)")

        if vacuum:
            self.commit_now(vacuum, exiting=exiting)

    def set_show_sql(self, switch):
        self._show_execute = switch

    # --------- generic functions -------------

    @blocking_call_on_reactor_thread
    def execute(self, sql, args=None):
        cur = self.get_cursor()

        if self._show_execute:
            thread_name = currentThread().getName()
            self._logger.info(u"===%s===\n%s\n-----\n%s\n======\n", thread_name, sql, args)

        try:
            if args is None:
                return cur.execute(sql)
            else:
                return cur.execute(sql, args)

        except Exception as msg:
            if str(msg).startswith(u"BusyError"):
                self._logger.error(u"cachedb: busylock error")

            else:
                thread_name = currentThread().getName()
                self._logger.exception(u"cachedb: ===%s===\nSQL Type: %s\n-----\n%s\n-----\n%s\n======\n",
                                       thread_name, type(sql), sql, args)

            raise msg

    @blocking_call_on_reactor_thread
    def executemany(self, sql, args=None):
        self._should_commit = True

        cur = self.get_cursor()
        if self._show_execute:
            thread_name = currentThread().getName()
            self._logger.info(u"===%s===\n%s\n-----\n%s\n======\n", thread_name, sql, args)

        try:
            if args is None:
                result = cur.executemany(sql)
            else:
                result = cur.executemany(sql, args)

            return result

        except Exception as msg:
            thread_name = currentThread().getName()
            self._logger.exception(u"===%s===\nSQL Type: %s\n-----\n%s\n-----\n%s\n======\n",
                                   thread_name, type(sql), sql, args)
            raise msg

    def execute_read(self, sql, args=None):
        return self.execute(sql, args)

    def execute_write(self, sql, args=None):
        self._should_commit = True

        self.execute(sql, args)

    def insert_or_ignore(self, table_name, **argv):
        if len(argv) == 1:
            sql = u'INSERT OR IGNORE INTO %s (%s) VALUES (?);' % (table_name, argv.keys()[0])
        else:
            questions = '?,' * len(argv)
            sql = u'INSERT OR IGNORE INTO %s %s VALUES (%s);' % (table_name, tuple(argv.keys()), questions[:-1])
        self.execute_write(sql, argv.values())

    def insert(self, table_name, **argv):
        if len(argv) == 1:
            sql = u'INSERT INTO %s (%s) VALUES (?);' % (table_name, argv.keys()[0])
        else:
            questions = '?,' * len(argv)
            sql = u'INSERT INTO %s %s VALUES (%s);' % (table_name, tuple(argv.keys()), questions[:-1])
        self.execute_write(sql, argv.values())

    # TODO: may remove this, only used by test_sqlitecachedb.py
    def insertMany(self, table_name, values, keys=None):
        """ values must be a list of tuples """

        questions = u'?,' * len(values[0])
        if keys is None:
            sql = u'INSERT INTO %s VALUES (%s);' % (table_name, questions[:-1])
        else:
            sql = u'INSERT INTO %s %s VALUES (%s);' % (table_name, tuple(keys), questions[:-1])
        self.executemany(sql, values)

    def update(self, table_name, where=None, **argv):
        assert len(argv) > 0, 'NO VALUES TO UPDATE SPECIFIED'
        if len(argv) > 0:
            sql = u'UPDATE %s SET ' % table_name
            arg = []
            for k, v in argv.iteritems():
                if isinstance(v, tuple):
                    sql += u'%s %s ?,' % (k, v[0])
                    arg.append(v[1])
                else:
                    sql += u'%s=?,' % k
                    arg.append(v)
            sql = sql[:-1]
            if where is not None:
                sql += u' WHERE %s' % where
            self.execute_write(sql, arg)

    def delete(self, table_name, **argv):
        sql = u'DELETE FROM %s WHERE ' % table_name
        arg = []
        for k, v in argv.iteritems():
            if isinstance(v, tuple):
                sql += u'%s %s ? AND ' % (k, v[0])
                arg.append(v[1])
            else:
                sql += u'%s=? AND ' % k
                arg.append(v)
        sql = sql[:-5]
        self.execute_write(sql, argv.values())

    # -------- Read Operations --------
    def size(self, table_name):
        num_rec_sql = u"SELECT count(*) FROM %s LIMIT 1" % table_name
        result = self.fetchone(num_rec_sql)
        return result

    @blocking_call_on_reactor_thread
    def fetchone(self, sql, args=None):
        find = self.execute_read(sql, args)
        if not find:
            return
        else:
            find = list(find)
            if len(find) > 0:
                if len(find) > 1:
                    self._logger.debug(
                        u"FetchONE resulted in many more rows than one, consider putting a LIMIT 1 in the sql statement %s, %s", sql, len(find))
                find = find[0]
            else:
                return
        if len(find) > 1:
            return find
        else:
            return find[0]

    @blocking_call_on_reactor_thread
    def fetchall(self, sql, args=None):
        res = self.execute_read(sql, args)
        if res is not None:
            find = list(res)
            return find
        else:
            return []  # should it return None?

    def getOne(self, table_name, value_name, where=None, conj=u"AND", **kw):
        """ value_name could be a string, a tuple of strings, or '*'
        """
        if isinstance(value_name, tuple):
            value_names = u",".join(value_name)
        elif isinstance(value_name, list):
            value_names = u",".join(value_name)
        else:
            value_names = value_name

        if isinstance(table_name, tuple):
            table_names = u",".join(table_name)
        elif isinstance(table_name, list):
            table_names = u",".join(table_name)
        else:
            table_names = table_name

        sql = u'SELECT %s FROM %s' % (value_names, table_names)

        if where or kw:
            sql += u' WHERE '
        if where:
            sql += where
            if kw:
                sql += u' %s ' % conj
        if kw:
            arg = []
            for k, v in kw.iteritems():
                if isinstance(v, tuple):
                    operator = v[0]
                    arg.append(v[1])
                else:
                    operator = "="
                    arg.append(v)
                sql += u' %s %s ? ' % (k, operator)
                sql += conj
            sql = sql[:-len(conj)]
        else:
            arg = None

        # print >> sys.stderr, 'SQL: %s %s' % (sql, arg)
        return self.fetchone(sql, arg)

    def getAll(self, table_name, value_name, where=None, group_by=None, having=None, order_by=None, limit=None,
               offset=None, conj=u"AND", **kw):
        """ value_name could be a string, or a tuple of strings
            order by is represented as order_by
            group by is represented as group_by
        """
        if isinstance(value_name, tuple):
            value_names = u",".join(value_name)
        elif isinstance(value_name, list):
            value_names = u",".join(value_name)
        else:
            value_names = value_name

        if isinstance(table_name, tuple):
            table_names = u",".join(table_name)
        elif isinstance(table_name, list):
            table_names = u",".join(table_name)
        else:
            table_names = table_name

        sql = u'SELECT %s FROM %s' % (value_names, table_names)

        if where or kw:
            sql += u' WHERE '
        if where:
            sql += where
            if kw:
                sql += u' %s ' % conj
        if kw:
            arg = []
            for k, v in kw.iteritems():
                if isinstance(v, tuple):
                    operator = v[0]
                    arg.append(v[1])
                else:
                    operator = u"="
                    arg.append(v)

                sql += u' %s %s ?' % (k, operator)
                sql += conj
            sql = sql[:-len(conj)]
        else:
            arg = None

        if group_by is not None:
            sql += u' GROUP BY ' + group_by
        if having is not None:
            sql += u' HAVING ' + having
        if order_by is not None:
            # you should add desc after order_by to reversely sort, i.e, 'last_seen desc' as order_by
            sql += u' ORDER BY ' + order_by
        if limit is not None:
            sql += u' LIMIT %d' % limit
        if offset is not None:
            sql += u' OFFSET %d' % offset

        try:
            return self.fetchall(sql, arg) or []
        except Exception as msg:
            self._logger.exception(u"Wrong getAll sql statement: %s", sql)
            raise Exception(msg)
