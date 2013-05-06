# Written by Jie Yang
# see LICENSE.txt for license information

import sys
import os
from os import environ
from time import sleep, time
from base64 import encodestring, decodestring
import threading
from traceback import print_exc, print_stack

from Tribler.Core.simpledefs import INFOHASH_LENGTH, NTFY_DISPERSY, NTFY_STARTED
from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.Utilities.unicode import dunno2unicode

# ONLY USE APSW >= 3.5.9-r1
import apsw
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from threading import currentThread, Event, RLock, Lock
import inspect
from Tribler.Core.Swift.SwiftDef import SwiftDef

try:
    # python 2.7 only...
    from collections import OrderedDict
except ImportError:
    from Tribler.dispersy.python27_ordereddict import OrderedDict

# support_version = (3,5,9)
# support_version = (3,3,13)
# apsw_version = tuple([int(r) for r in apsw.apswversion().split('-')[0].split('.')])
# #print apsw_version
# assert apsw_version >= support_version, "Required APSW Version >= %d.%d.%d."%support_version + " But your version is %d.%d.%d.\n"%apsw_version + \
#                        "Please download and install it from http://code.google.com/p/apsw/"

# #Changed from 4 to 5 by andrea for subtitles support
# #Changed from 5 to 6 by George Milescu for ProxyService
# #Changed from 6 to 7 for Raynor's TermFrequency table
# #Changed from 7 to 8 for Raynor's BundlerPreference table
# #Changed from 8 to 9 for Niels's Open2Edit tables
# #Changed from 9 to 10 for Fix in Open2Edit PlayListTorrent table
# #Changed from 10 to 11 add a index on channeltorrent.torrent_id to improve search performance
# #Changed from 11 to 12 imposing some limits on the Tribler database
# #Changed from 12 to 13 introduced swift-url modification type
# #Changed from 13 to 14 introduced swift_hash/swift_torrent_hash torrent columns + upgrade script
# #Changed from 14 to 15 added indices on swift_hash/swift_torrent_hash torrent
# #Changed from 15 to 16 changed all swift_torrent_hash that was an empty string to NULL
# #Changed from 16 to 17 cleaning buddycast, preference, terms, and subtitles tables, removed indices
# #Changed from 17 to 18 added swift-thumbnails/video-info metadatatypes

# Arno, 2012-08-01: WARNING You must also update the version number that is
# written to the DB in the schema_sdb_v*.sql file!!!
CURRENT_MAIN_DB_VERSION = 18

CREATE_SQL_FILE = None
CREATE_SQL_FILE_POSTFIX = os.path.join(LIBRARYNAME, 'schema_sdb_v' + str(CURRENT_MAIN_DB_VERSION) + '.sql')
DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = 'sqlite'  # db file path = DB_DIR_NAME/DB_FILE_NAME
DEFAULT_BUSY_TIMEOUT = 10000
MAX_SQL_BATCHED_TO_TRANSACTION = 1000  # don't change it unless carefully tested. A transaction with 1000 batched updates took 1.5 seconds
NULL = None
icon_dir = None
SHOW_ALL_EXECUTE = False
costs = []
cost_reads = []
torrent_dir = None
config_dir = None
install_dir = None
TEST_OVERRIDE = False

DEBUG = False
DEBUG_THREAD = False
DEBUG_TIME = True

TRHEADING_DEBUG = False
DEPRECATION_DEBUG = False

__DEBUG_QUERIES__ = environ.has_key('TRIBLER_DEBUG_DATABASE_QUERIES')
if __DEBUG_QUERIES__:
    from random import randint
    from os.path import exists
    from time import time
    DB_DEBUG_FILE = "tribler_database_queries_%d.txt" % randint(1, 9999999)
    while exists(DB_DEBUG_FILE):
        DB_DEBUG_FILE = "tribler_database_queries_%d.txt" % randint(1, 9999999)


class Warning(Exception):
    pass

class LimitedOrderedDict(OrderedDict):
    def __init__(self, limit, *args, **kargs):
        super(LimitedOrderedDict, self).__init__(*args, **kargs)
        self._limit = limit

    def __setitem__(self, *args, **kargs):
        super(LimitedOrderedDict, self).__setitem__(*args, **kargs)
        if len(self) > self._limit:
            self.popitem(last=False)

def init(config, db_exception_handler=None):
    """ create sqlite database """
    global CREATE_SQL_FILE
    global icon_dir
    global torrent_dir
    global config_dir
    global install_dir
    torrent_dir = os.path.abspath(config['torrent_collecting_dir'])
    config_dir = config['state_dir']
    install_dir = config['install_dir']
    CREATE_SQL_FILE = os.path.join(install_dir, CREATE_SQL_FILE_POSTFIX)
    sqlitedb = SQLiteCacheDB.getInstance(db_exception_handler)

    sqlite_db_path = os.path.join(config_dir, DB_DIR_NAME, DB_FILE_NAME)
    print >> sys.stderr, "cachedb: init: SQL FILE", sqlite_db_path

    icon_dir = os.path.abspath(config['peer_icon_path'])

    sqlitedb.initDB(sqlite_db_path, CREATE_SQL_FILE)  # the first place to create db in Tribler
    return sqlitedb

def done():
    # Arno, 2012-07-04: Obsolete, each thread must close the DBHandler it uses
    # in its own shutdown procedure. There is no global close of all per-thread
    # cursors/connections.
    #
    SQLiteCacheDB.getInstance().close()

def make_filename(config_dir, filename):
    if config_dir is None:
        return filename
    else:
        return os.path.join(config_dir, filename)

def bin2str(bin):
    # Full BASE64-encoded
    return encodestring(bin).replace("\n", "")

def str2bin(str):
    return decodestring(str)

def print_exc_plus():
    """
    Print the usual traceback information, followed by a listing of all the
    local variables in each frame.
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52215
    http://initd.org/pub/software/pysqlite/apsw/3.3.13-r1/apsw.html#augmentedstacktraces
    """

    tb = sys.exc_info()[2]
    stack = []

    while tb:
        stack.append(tb.tb_frame)
        tb = tb.tb_next

    print_exc()
    print >> sys.stderr, "Locals by frame, innermost last"

    for frame in stack:
        print >> sys.stderr
        print >> sys.stderr, "Frame %s in %s at line %s" % (frame.f_code.co_name,
                                             frame.f_code.co_filename,
                                             frame.f_lineno)
        for key, value in frame.f_locals.items():
            print >> sys.stderr, "\t%20s = " % key,
            # We have to be careful not to cause a new error in our error
            # printer! Calling str() on an unknown object could cause an
            # error we don't want.
            try:
                print >> sys.stderr, value
            except:
                print >> sys.stderr, "<ERROR WHILE PRINTING VALUE>"

def debugTime(func):
    def invoke_func(*args, **kwargs):
        if DEBUG_TIME:
            t1 = time()

        result = func(*args, **kwargs)

        if DEBUG_TIME:
            diff = time() - t1
            if diff > 0.5:
                print >> sys.stderr, "TOOK", diff, args

        return result

    invoke_func.__name__ = func.__name__
    return invoke_func

class safe_dict(dict):
    def __init__(self, *args, **kw):
        self.lock = threading.RLock()
        dict.__init__(self, *args, **kw)

    def __getitem__(self, key):
        self.lock.acquire()
        try:
            return dict.__getitem__(self, key)
        finally:
            self.lock.release()

    def __setitem__(self, key, value):
        self.lock.acquire()
        try:
            dict.__setitem__(self, key, value)
        finally:
            self.lock.release()

    def __delitem__(self, key):
        self.lock.acquire()
        try:
            dict.__delitem__(self, key)
        finally:
            self.lock.release()

    def __contains__(self, key):
        self.lock.acquire()
        try:
            return dict.__contains__(self, key)
        finally:
            self.lock.release()

    def values(self):
        self.lock.acquire()
        try:
            return dict.values(self)
        finally:
            self.lock.release()

class SQLiteCacheDBBase:
    lock = threading.RLock()

    def __init__(self, db_exception_handler=None):
        self.exception_handler = db_exception_handler
        self.cursor_table = safe_dict()  # {thread_name:cur}
        self.cache_transaction_table = safe_dict()  # {thread_name:[sql]
        self.class_variables = safe_dict({'db_path':None, 'busytimeout':None})  # busytimeout is in milliseconds

        # Arno, 2012-08-02: As there is just Dispersy thread here, removing
        # safe_dict() here
        # 24/09/12 Boudewijn: changed into LimitedOrderedDict to limit memory consumption
        self.permid_id = LimitedOrderedDict(1024 * 5)  # {}  # safe_dict()
        self.infohash_id = LimitedOrderedDict(1024 * 5)  # {} # safe_dict()
        self.show_execute = False

        # TODO: All global variables must be protected to be thread safe?
        self.status_table = None
        self.category_table = None
        self.src_table = None
        self.applied_pragma = False

    def __del__(self):
        self.close()

    def close(self, clean=False):
        # only close the connection object in this thread, don't close other thread's connection object
        thread_name = threading.currentThread().getName()
        cur = self.getCursor(create=False)
        if cur:
            self._close_cur(thread_name, cur)

        if clean:  # used for test suite
            # Arno, 2012-08-02: As there is just Dispery thread here, removing
            # safe_dict() here
            self.permid_id = {}  # safe_dict()
            self.infohash_id = {}  # safe_dict()
            self.exception_handler = None
            self.class_variables = safe_dict({'db_path':None, 'busytimeout':None})
            self.cursor_table = safe_dict()
            self.cache_transaction_table = safe_dict()

    def close_all(self):
        for thread_name, cur in self.cursor_table.items():
            self._close_cur(thread_name, cur)

    def _close_cur(self, thread_name, cur):
        con = cur.getconnection()
        cur.close()
        con.close()

        del self.cursor_table[thread_name]
        # Arno, 2010-01-25: Remove entry in cache_transaction_table for this thread
        try:
            if thread_name in self.cache_transaction_table.keys():
                del self.cache_transaction_table[thread_name]
        except:
            print_exc()

    # --------- static functions --------
    def getCursor(self, create=True):
        thread_name = threading.currentThread().getName()
        curs = self.cursor_table
        cur = curs.get(thread_name, None)  # return [cur, cur, lib] or None
        # print >> sys.stderr, '-------------- getCursor::', len(curs), time(), curs.keys()
        if cur is None and create and self.class_variables['db_path']:
            self.openDB(self.class_variables['db_path'], self.class_variables['busytimeout'])  # create a new db obj for this thread
            cur = curs.get(thread_name)

        return cur

    def openDB(self, dbfile_path=None, busytimeout=DEFAULT_BUSY_TIMEOUT):
        """
        Open a SQLite database. Only one and the same database can be opened.
        @dbfile_path       The path to store the database file.
                           Set dbfile_path=':memory:' to create a db in memory.
        @busytimeout       Set the maximum time, in milliseconds, that SQLite will wait if the database is locked.
        """

        # already opened a db in this thread, reuse it
        thread_name = threading.currentThread().getName()
        # print >>sys.stderr,"sqlcachedb: openDB",dbfile_path,thread_name
        if thread_name in self.cursor_table:
            # assert dbfile_path == None or self.class_variables['db_path'] == dbfile_path
            return self.cursor_table[thread_name]

        assert dbfile_path, "You must specify the path of database file"

        if dbfile_path.lower() != ':memory:':
            db_dir, db_filename = os.path.split(dbfile_path)
            if db_dir and not os.path.isdir(db_dir):
                os.makedirs(db_dir)

        con = apsw.Connection(dbfile_path)
        con.setbusytimeout(busytimeout)

        cur = con.cursor()
        self.cursor_table[thread_name] = cur

        if not self.applied_pragma:
            self.applied_pragma = True
            page_size, = next(cur.execute("PRAGMA page_size"))
            if page_size < 8192:
                # journal_mode and page_size only need to be set once.  because of the VACUUM this
                # is very expensive
                print >> sys.stderr, "begin page_size upgrade..."
                cur.execute("PRAGMA journal_mode = DELETE;")
                cur.execute("PRAGMA page_size = 8192;")
                cur.execute("VACUUM;")
                print >> sys.stderr, "...end page_size upgrade"

            # http://www.sqlite.org/pragma.html
            # When synchronous is NORMAL, the SQLite database engine will still
            # pause at the most critical moments, but less often than in FULL
            # mode. There is a very small (though non-zero) chance that a power
            # failure at just the wrong time could corrupt the database in
            # NORMAL mode. But in practice, you are more likely to suffer a
            # catastrophic disk failure or some other unrecoverable hardware
            # fault.
            #
            cur.execute("PRAGMA synchronous = NORMAL;")
            cur.execute("PRAGMA cache_size = 10000;")

            # Niels 19-09-2012: even though my database upgraded to increase the pagesize it did not keep wal mode?
            # Enabling WAL on every starup
            cur.execute("PRAGMA journal_mode = WAL;")

        return cur

    def createDBTable(self, sql_create_table, dbfile_path, busytimeout=DEFAULT_BUSY_TIMEOUT):
        """
        Create a SQLite database.
        @sql_create_table  The sql statements to create tables in the database.
                           Every statement must end with a ';'.
        @dbfile_path       The path to store the database file. Set dbfile_path=':memory:' to creates a db in memory.
        @busytimeout       Set the maximum time, in milliseconds, that SQLite will wait if the database is locked.
                           Default = 10000 milliseconds
        """
        cur = self.openDB(dbfile_path, busytimeout)
        print dbfile_path
        cur.execute(sql_create_table)  # it is suggested to include begin & commit in the script

    def initDB(self, sqlite_filepath,
               create_sql_filename=None,
               busytimeout=DEFAULT_BUSY_TIMEOUT,
               check_version=True,
               current_db_version=CURRENT_MAIN_DB_VERSION):
        """
        Create and initialize a SQLite database given a sql script.
        Only one db can be opened. If the given dbfile_path is different with the opened DB file, warn and exit
        @configure_dir     The directory containing 'bsddb' directory
        @sql_filename      The path of sql script to create the tables in the database
                           Every statement must end with a ';'.
        @busytimeout       Set the maximum time, in milliseconds, to wait and retry
                           if failed to acquire a lock. Default = 5000 milliseconds
        """
        if create_sql_filename is None:
            create_sql_filename = CREATE_SQL_FILE
        try:
            self.lock.acquire()

            # verify db path identity
            class_db_path = self.class_variables['db_path']
            if sqlite_filepath is None:  # reuse the opened db file?
                if class_db_path is not None:  # yes, reuse it
                    # reuse the busytimeout
                    return self.openDB(class_db_path, self.class_variables['busytimeout'])
                else:  # no db file opened
                    raise Exception, "You must specify the path of database file when open it at the first time"
            else:
                if class_db_path is None:  # the first time to open db path, store it

                    # print 'quit now'
                    # sys.exit(0)
                    # open the db if it exists (by converting from bsd) and is not broken, otherwise create a new one
                    # it will update the db if necessary by checking the version number
                    self.safelyOpenTriblerDB(sqlite_filepath, create_sql_filename, busytimeout, check_version=check_version, current_db_version=current_db_version)

                    self.class_variables = {'db_path': sqlite_filepath, 'busytimeout': int(busytimeout)}

                    return self.openDB()  # return the cursor, won't reopen the db

                elif sqlite_filepath != class_db_path:  # not the first time to open db path, check if it is the same
                    raise Exception, "Only one database file can be opened. You have opened %s and are trying to open %s." % (class_db_path, sqlite_filepath)

        finally:
            self.lock.release()

    def safelyOpenTriblerDB(self, dbfile_path, sql_create, busytimeout=DEFAULT_BUSY_TIMEOUT, check_version=False, current_db_version=None):
        """
        open the db if possible, otherwise create a new one
        update the db if necessary by checking the version number

        safeOpenDB():
            try:
                if sqlite db doesn't exist:
                    raise Error
                open sqlite db
                read sqlite_db_version
                if sqlite_db_version dosen't exist:
                    raise Error
            except:
                close and delete sqlite db if possible
                create new sqlite db file without sqlite_db_version
                write sqlite_db_version at last
                commit
                open sqlite db
                read sqlite_db_version
                # must ensure these steps after except will not fail, otherwise force to exit

            if sqlite_db_version < current_db_version:
                updateDB(sqlite_db_version, current_db_version)
                commit
                update sqlite_db_version at last
                commit
        """
        try:
            if not os.path.isfile(dbfile_path):
                raise Warning("No existing database found. Attempting to creating a new database %s" % repr(dbfile_path))

            cur = self.openDB(dbfile_path, busytimeout)
            if check_version:
                sqlite_db_version = self.readDBVersion()
                if sqlite_db_version == NULL or int(sqlite_db_version) < 1:
                    raise NotImplementedError
        except Exception, exception:
            if isinstance(exception, Warning):
                # user friendly warning to log the creation of a new database
                print >> sys.stderr, exception

            else:
                # user unfriendly exception message because something went wrong
                print_exc()

            if os.path.isfile(dbfile_path):
                self.close(clean=True)
                os.remove(dbfile_path)

            if os.path.isfile(sql_create):
                f = open(sql_create)
                sql_create_tables = f.read()
                f.close()
            else:
                raise Exception, "Cannot open sql script at %s" % os.path.realpath(sql_create)

            self.createDBTable(sql_create_tables, dbfile_path, busytimeout)
            if check_version:
                sqlite_db_version = self.readDBVersion()

        if check_version:
            self.checkDB(sqlite_db_version, current_db_version)

    def checkDB(self, db_ver, curr_ver):
        # read MyDB and check the version number.
        if not db_ver or not curr_ver:
            self.updateDB(db_ver, curr_ver)
            return
        db_ver = int(db_ver)
        curr_ver = int(curr_ver)
        # print "check db", db_ver, curr_ver
        if db_ver != curr_ver or \
               (not config_dir is None and (os.path.exists(os.path.join(config_dir, "upgradingdb.txt")) or os.path.exists(os.path.join(config_dir, "upgradingdb2.txt")) or os.path.exists(os.path.join(config_dir, "upgradingdb3.txt")))):
            self.updateDB(db_ver, curr_ver)

    def updateDB(self, db_ver, curr_ver):
        pass  # TODO

    def readDBVersion(self):
        cur = self.getCursor()
        sql = u"select value from MyInfo where entry='version'"
        res = self.fetchone(sql)
        if res:
            return res
        else:
            return None

    def writeDBVersion(self, version, commit=True):
        sql = u"UPDATE MyInfo SET value=? WHERE entry='version'"
        self.execute_write(sql, [version], commit=commit)

    def show_sql(self, switch):
        # temporary show the sql executed
        self.show_execute = switch

    # --------- generic functions -------------

    def commit(self):
        self.transaction()

    def _execute(self, sql, args=None):
        cur = self.getCursor()

        if SHOW_ALL_EXECUTE or self.show_execute:
            thread_name = threading.currentThread().getName()
            print >> sys.stderr, '===', thread_name, '===\n', sql, '\n-----\n', args, '\n======\n'

        # we should not perform database actions on the GUI (MainThread) thread because that might
        # block the GUI
        if DEBUG_THREAD:
            if threading.currentThread().getName() == "MainThread":
                for sql_line in sql.split(";"):
                    try:
                        # key, rest = sql_line.strip().split(" ", 1)
                        key = sql_line[:50]
                        print >> sys.stderr, "sqlitecachedb.py: should not perform sql", key, "on GUI thread"
                        # print_stack()
                    except:
                        # key = sql.strip()
                        key = sql_line
                        if key:
                            print >> sys.stderr, "sqlitecachedb.py: should not perform sql", key, "on GUI thread"
                            # print_stack()

        try:
            if args is None:
                return cur.execute(sql)
            else:
                return cur.execute(sql, args)

        except Exception, msg:
            if True:
                if str(msg).startswith("BusyError"):
                    print >> sys.stderr, "cachedb: busylock error"

                else:
                    print_exc()
                    print_stack()
                    print >> sys.stderr, "cachedb: execute error:", Exception, msg
                    thread_name = threading.currentThread().getName()
                    print >> sys.stderr, '===', thread_name, '===\nSQL Type:', type(sql), '\n-----\n', sql, '\n-----\n', args, '\n======\n'

                # return None
                # ARNODB: this is incorrect, it should reraise the exception
                # such that _transaction can rollback or recommit.
                # This bug already reported by Johan
            raise msg

#    @debugTime
    def execute_read(self, sql, args=None):
        # this is only called for reading. If you want to write the db, always use execute_write or executemany
        return self._execute(sql, args)

    def execute_write(self, sql, args=None, commit=True):
        self.cache_transaction(sql, args)
        if commit:
            self.commit()

    def executemany(self, sql, args, commit=True):

        thread_name = threading.currentThread().getName()
        if thread_name not in self.cache_transaction_table:
            self.cache_transaction_table[thread_name] = []
        all = [(sql, arg) for arg in args]
        self.cache_transaction_table[thread_name].extend(all)

        if commit:
            self.commit()

    def cache_transaction(self, sql, args=None):
        thread_name = threading.currentThread().getName()
        if thread_name not in self.cache_transaction_table:
            self.cache_transaction_table[thread_name] = []
        self.cache_transaction_table[thread_name].append((sql, args))

    def transaction(self, sql=None, args=None):
        if sql:
            self.cache_transaction(sql, args)

        thread_name = threading.currentThread().getName()

        n = 0
        sql_full = ''
        arg_list = []
        sql_queue = self.cache_transaction_table.get(thread_name, None)
        if sql_queue:
            while True:
                try:
                    _sql, _args = sql_queue.pop(0)
                except IndexError:
                    break

                _sql = _sql.strip()
                if not _sql:
                    continue
                if not _sql.endswith(';'):
                    _sql += ';'
                sql_full += _sql + '\n'
                if _args != None:
                    arg_list += list(_args)
                n += 1

                # if too many sql in cache, split them into batches to prevent processing and locking DB for a long time
                # TODO: optimize the value of MAX_SQL_BATCHED_TO_TRANSACTION
                if n % MAX_SQL_BATCHED_TO_TRANSACTION == 0:
                    self._transaction(sql_full, arg_list)
                    sql_full = ''
                    arg_list = []

            self._transaction(sql_full, arg_list)

    def _transaction(self, sql, args=None):
        if sql:
            sql = 'BEGIN TRANSACTION; \n' + sql + 'COMMIT TRANSACTION;'
            try:
                self._execute(sql, args)
            except Exception, e:
                self.commit_retry_if_busy_or_rollback(e, 0, sql=sql)

    def commit_retry_if_busy_or_rollback(self, e, tries, sql=None):
        """
        Arno:
        SQL_BUSY errors happen at the beginning of the experiment,
        very quickly after startup (e.g. 0.001 s), so the busy timeout
        is not honoured for some reason. After the initial errors,
        they no longer occur.
        """
        print >> sys.stderr, "sqlcachedb: commit_retry: after", str(e), repr(sql)

        if str(e).startswith("BusyError"):
            try:
                self._execute("COMMIT")
            except Exception, e2:
                if tries < 5:  # self.max_commit_retries
                    # Spec is unclear whether next commit will also has
                    # 'busytimeout' seconds to try to get a write lock.
                    sleep(pow(2.0, tries + 2) / 100.0)
                    self.commit_retry_if_busy_or_rollback(e2, tries + 1)
                else:
                    self.rollback(tries)
                    raise Exception, e2
        else:
            self.rollback(tries)
            m = "cachedb: TRANSACTION ERROR " + threading.currentThread().getName() + ' ' + str(e)
            raise Exception, m


    def rollback(self, tries):
        print_exc()
        try:
            self._execute("ROLLBACK")
        except Exception, e:
            # May be harmless, see above. Unfortunately they don't specify
            # what the error is when an attempt is made to roll back
            # an automatically rolled back transaction.
            m = "cachedb: ROLLBACK ERROR " + threading.currentThread().getName() + ' ' + str(e)
            # print >> sys.stderr, 'SQLite Database', m
            raise Exception, m


    # -------- Write Operations --------
    def insert_or_replace(self, table_name, commit=True, **argv):
        if len(argv) == 1:
            sql = 'INSERT OR REPLACE INTO %s (%s) VALUES (?);' % (table_name, argv.keys()[0])
        else:
            questions = '?,' * len(argv)
            sql = 'INSERT OR REPLACE INTO %s %s VALUES (%s);' % (table_name, tuple(argv.keys()), questions[:-1])
        self.execute_write(sql, argv.values(), commit)

    def insert_or_ignore(self, table_name, commit=True, **argv):
        if len(argv) == 1:
            sql = 'INSERT OR IGNORE INTO %s (%s) VALUES (?);' % (table_name, argv.keys()[0])
        else:
            questions = '?,' * len(argv)
            sql = 'INSERT OR IGNORE INTO %s %s VALUES (%s);' % (table_name, tuple(argv.keys()), questions[:-1])
        self.execute_write(sql, argv.values(), commit)

    def insert(self, table_name, commit=True, **argv):
        if len(argv) == 1:
            sql = 'INSERT INTO %s (%s) VALUES (?);' % (table_name, argv.keys()[0])
        else:
            questions = '?,' * len(argv)
            sql = 'INSERT INTO %s %s VALUES (%s);' % (table_name, tuple(argv.keys()), questions[:-1])
        self.execute_write(sql, argv.values(), commit)

    def insertMany(self, table_name, values, keys=None, commit=True):
        """ values must be a list of tuples """

        questions = u'?,' * len(values[0])
        if keys is None:
            sql = u'INSERT INTO %s VALUES (%s);' % (table_name, questions[:-1])
        else:
            sql = u'INSERT INTO %s %s VALUES (%s);' % (table_name, tuple(keys), questions[:-1])
        self.executemany(sql, values, commit=commit)

    def update(self, table_name, where=None, commit=True, **argv):
        assert len(argv) > 0, 'NO VALUES TO UPDATE SPECIFIED'
        if len(argv) > 0:
            sql = u'UPDATE %s SET ' % table_name
            arg = []
            for k, v in argv.iteritems():
                if type(v) is tuple:
                    sql += u'%s %s ?,' % (k, v[0])
                    arg.append(v[1])
                else:
                    sql += u'%s=?,' % k
                    arg.append(v)
            sql = sql[:-1]
            if where != None:
                sql += u' where %s' % where
            self.execute_write(sql, arg, commit)

    def delete(self, table_name, commit=True, **argv):
        sql = u'DELETE FROM %s WHERE ' % table_name
        arg = []
        for k, v in argv.iteritems():
            if type(v) is tuple:
                sql += u'%s %s ? AND ' % (k, v[0])
                arg.append(v[1])
            else:
                sql += u'%s=? AND ' % k
                arg.append(v)
        sql = sql[:-5]
        self.execute_write(sql, argv.values(), commit)

    # -------- Read Operations --------
    def size(self, table_name):
        num_rec_sql = u"SELECT count(*) FROM %s LIMIT 1" % table_name
        result = self.fetchone(num_rec_sql)
        return result

    def fetchone(self, sql, args=None):
        # returns NULL: if the result is null
        # return None: if it doesn't found any match results
        find = self.execute_read(sql, args)
        if not find:
            return NULL
        else:
            find = list(find)
            if len(find) > 0:
                if DEBUG and len(find) > 1:
                    print >> sys.stderr, "FetchONE resulted in many more rows than one, consider putting a LIMIT 1 in the sql statement", sql, len(find)
                find = find[0]
            else:
                return NULL
        if len(find) > 1:
            return find
        else:
            return find[0]

    def fetchall(self, sql, args=None, retry=0):
        res = self.execute_read(sql, args)
        if res != None:
            find = list(res)
            return find
        else:
            return []  # should it return None?

    def getOne(self, table_name, value_name, where=None, conj='and', **kw):
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

        sql = u'select %s from %s' % (value_names, table_names)

        if where or kw:
            sql += u' where '
        if where:
            sql += where
            if kw:
                sql += u' %s ' % conj
        if kw:
            arg = []
            for k, v in kw.iteritems():
                if type(v) is tuple:
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

    def getAll(self, table_name, value_name, where=None, group_by=None, having=None, order_by=None, limit=None, offset=None, conj='and', **kw):
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

        sql = u'select %s from %s' % (value_names, table_names)

        if where or kw:
            sql += u' where '
        if where:
            sql += where
            if kw:
                sql += u' %s ' % conj
        if kw:
            arg = []
            for k, v in kw.iteritems():
                if type(v) is tuple:
                    operator = v[0]
                    arg.append(v[1])
                else:
                    operator = "="
                    arg.append(v)

                sql += u' %s %s ?' % (k, operator)
                sql += conj
            sql = sql[:-len(conj)]
        else:
            arg = None

        if group_by != None:
            sql += u' group by ' + group_by
        if having != None:
            sql += u' having ' + having
        if order_by != None:
            sql += u' order by ' + order_by  # you should add desc after order_by to reversely sort, i.e, 'last_seen desc' as order_by
        if limit != None:
            sql += u' limit %d' % limit
        if offset != None:
            sql += u' offset %d' % offset

        try:
            return self.fetchall(sql, arg) or []
        except Exception, msg:
            print >> sys.stderr, "sqldb: Wrong getAll sql statement:", sql
            raise Exception, msg

    # ----- Tribler DB operations ----

    #------------- useful functions for multiple handlers ----------
    def insertPeer(self, permid, update=True, commit=True, **argv):
        """ Insert a peer. permid is the binary permid.
        If the peer is already in db and update is True, update the peer.
        """
        peer_id = self.getPeerID(permid)
        peer_existed = False
        if 'name' in argv:
            argv['name'] = dunno2unicode(argv['name'])
        if peer_id != None:
            peer_existed = True
            if update:
                where = u'peer_id=%d' % peer_id
                self.update('Peer', where, commit=commit, **argv)
        else:
            self.insert_or_ignore('Peer', permid=bin2str(permid), commit=commit, **argv)
        return peer_existed

    def deletePeer(self, permid=None, peer_id=None, force=True, commit=True):
        if peer_id is None:
            peer_id = self.getPeerID(permid)

        deleted = False
        if peer_id != None:
            if force:
                self.delete('Peer', peer_id=peer_id, commit=commit)
            else:
                self.delete('Peer', peer_id=peer_id, friend=0, superpeer=0, commit=commit)
            deleted = not self.hasPeer(permid, check_db=True)
            if deleted and permid in self.permid_id:
                self.permid_id.pop(permid)

        return deleted

    def getPeerID(self, permid):
        assert isinstance(permid, str), permid
        # permid must be binary
        peer_id = self.permid_id.get(permid, None)
        if peer_id is not None:
            return peer_id

        sql_get_peer_id = "SELECT peer_id FROM Peer WHERE permid==?"
        peer_id = self.fetchone(sql_get_peer_id, (bin2str(permid),))
        if peer_id != None:
            self.permid_id[permid] = peer_id

        return peer_id

    def getPeerIDS(self, permids):
        to_select = []

        for permid in permids:
            assert isinstance(permid, str), permid

            if permid not in self.permid_id:
                to_select.append(bin2str(permid))

        if len(to_select) > 0:
            parameters = ", ".join('?' * len(to_select))
            sql_get_peer_ids = "SELECT peer_id, permid FROM Peer WHERE permid IN (" + parameters + ")"
            peerids = self.fetchall(sql_get_peer_ids, to_select)
            for peer_id, permid in peerids:
                self.permid_id[str2bin(permid)] = peer_id

        to_return = []
        for permid in permids:
            if permid in self.permid_id:
                to_return.append(self.permid_id[permid])
            else:
                to_return.append(None)
        return to_return

    def hasPeer(self, permid, check_db=False):
        if not check_db:
            return bool(self.getPeerID(permid))
        else:
            permid_str = bin2str(permid)
            sql_get_peer_id = "SELECT peer_id FROM Peer WHERE permid==?"
            peer_id = self.fetchone(sql_get_peer_id, (permid_str,))
            if peer_id is None:
                return False
            else:
                return True

    def insertInfohash(self, infohash, check_dup=False, commit=True):
        """ Insert an infohash. infohash is binary """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if infohash in self.infohash_id:
            if check_dup:
                print >> sys.stderr, 'sqldb: infohash to insert already exists', `infohash`
            return

        infohash_str = bin2str(infohash)
        sql_insert_torrent = "INSERT INTO Torrent (infohash) VALUES (?)"
        self.execute_write(sql_insert_torrent, (infohash_str,), commit)

    def deleteInfohash(self, infohash=None, torrent_id=None, commit=True):
        assert infohash is None or isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert infohash is None or len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if torrent_id is None:
            torrent_id = self.getTorrentID(infohash)

        if torrent_id != None:
            self.delete('Torrent', torrent_id=torrent_id, commit=commit)
            if infohash in self.infohash_id:
                self.infohash_id.pop(infohash)

    def getTorrentID(self, infohash):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)

        tid = self.infohash_id.get(infohash, None)
        if tid is not None:
            return tid

        sql_get_torrent_id = "SELECT torrent_id FROM Torrent WHERE infohash==?"
        tid = self.fetchone(sql_get_torrent_id, (bin2str(infohash),))
        if tid != None:
            self.infohash_id[infohash] = tid
        return tid

    def getTorrentIDS(self, infohashes):
        to_select = []

        for infohash in infohashes:
            assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
            assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)

            if not infohash in self.infohash_id:
                to_select.append(bin2str(infohash))

        while len(to_select) > 0:
            nrToQuery = min(len(to_select), 50)
            parameters = '?,' * nrToQuery
            sql_get_torrent_ids = "SELECT torrent_id, infohash FROM Torrent WHERE infohash IN (" + parameters[:-1] + ")"

            torrents = self.fetchall(sql_get_torrent_ids, to_select[:nrToQuery])
            for torrent_id, infohash in torrents:
                self.infohash_id[str2bin(infohash)] = torrent_id

            to_select = to_select[nrToQuery:]

        to_return = []
        for infohash in infohashes:
            if infohash in self.infohash_id:
                to_return.append(self.infohash_id[infohash])
            else:
                to_return.append(None)
        return to_return

    def getTorrentIDRoot(self, roothash):
        assert isinstance(roothash, str), "roothash has invalid type: %s" % type(roothash)
        assert len(roothash) == INFOHASH_LENGTH, "roothash has invalid length: %d" % len(roothash)

        sql_get_torrent_id = "SELECT torrent_id FROM Torrent WHERE swift_hash==?"
        tid = self.fetchone(sql_get_torrent_id, (bin2str(roothash),))
        return tid

    def getInfohash(self, torrent_id):
        sql_get_infohash = "SELECT infohash FROM Torrent WHERE torrent_id==?"
        arg = (torrent_id,)
        ret = self.fetchone(sql_get_infohash, arg)
        if ret:
            ret = str2bin(ret)
        return ret

    def getTorrentStatusTable(self):
        if self.status_table is None:
            st = self.getAll('TorrentStatus', ('lower(name)', 'status_id'))
            self.status_table = dict(st)
        return self.status_table

    def getTorrentCategoryTable(self):
        # The key is in lower case
        if self.category_table is None:
            ct = self.getAll('Category', ('lower(name)', 'category_id'))
            self.category_table = dict(ct)
        return self.category_table

    def getTorrentSourceTable(self):
        # Don't use lower case because some URLs are case sensitive
        if self.src_table is None:
            st = self.getAll('TorrentSource', ('name', 'source_id'))
            self.src_table = dict(st)
        return self.src_table

    def test(self):
        res1 = self.getAll('Category', '*')
        res2 = len(self.getAll('Peer', 'name', 'name is not NULL'))
        return (res1, res2)


class SQLiteCacheDBV5(SQLiteCacheDBBase):
    def updateDB(self, fromver, tover):

        # bring database up to version 2, if necessary
        if fromver < 2:
            sql = """

-- Patch for BuddyCast 4

ALTER TABLE MyPreference ADD COLUMN click_position INTEGER DEFAULT -1;
ALTER TABLE MyPreference ADD COLUMN reranking_strategy INTEGER DEFAULT -1;
ALTER TABLE Preference ADD COLUMN click_position INTEGER DEFAULT -1;
ALTER TABLE Preference ADD COLUMN reranking_strategy INTEGER DEFAULT -1;
CREATE TABLE ClicklogSearch (
                     peer_id INTEGER DEFAULT 0,
                     torrent_id INTEGER DEFAULT 0,
                     term_id INTEGER DEFAULT 0,
                     term_order INTEGER DEFAULT 0
                     );
CREATE INDEX idx_search_term ON ClicklogSearch (term_id);
CREATE INDEX idx_search_torrent ON ClicklogSearch (torrent_id);


CREATE TABLE ClicklogTerm (
                    term_id INTEGER PRIMARY KEY AUTOINCREMENT DEFAULT 0,
                    term VARCHAR(255) NOT NULL,
                    times_seen INTEGER DEFAULT 0 NOT NULL
                    );
CREATE INDEX idx_terms_term ON ClicklogTerm(term);

"""

            self.execute_write(sql, commit=False)


        if fromver < 3:
            sql = """
-- Patch for Local Peer Discovery

ALTER TABLE Peer ADD COLUMN is_local integer DEFAULT 0;
"""
            self.execute_write(sql, commit=False)

        if fromver < 4:
            sql = """
-- V2: Patch for VoteCast

DROP TABLE IF EXISTS ModerationCast;
DROP INDEX IF EXISTS moderationcast_idx;

DROP TABLE IF EXISTS Moderators;
DROP INDEX IF EXISTS moderators_idx;

DROP TABLE IF EXISTS VoteCast;
DROP INDEX IF EXISTS votecast_idx;

CREATE TABLE VoteCast (
mod_id text,
voter_id text,
vote integer,
time_stamp integer
);

CREATE INDEX mod_id_idx
on VoteCast
(mod_id);

CREATE INDEX voter_id_idx
on VoteCast
(voter_id);

CREATE UNIQUE INDEX votecast_idx
ON VoteCast
(mod_id, voter_id);

--- patch for BuddyCast 5 : Creation of Popularity table and relevant stuff

CREATE TABLE Popularity (
                         torrent_id INTEGER,
                         peer_id INTEGER,
                         msg_receive_time NUMERIC,
                         size_calc_age NUMERIC,
                         num_seeders INTEGER DEFAULT 0,
                         num_leechers INTEGER DEFAULT 0,
                         num_of_sources INTEGER DEFAULT 0
                     );

CREATE INDEX Message_receive_time_idx
  ON Popularity
   (msg_receive_time);

CREATE INDEX Size_calc_age_idx
  ON Popularity
   (size_calc_age);

CREATE INDEX Number_of_seeders_idx
  ON Popularity
   (num_seeders);

CREATE INDEX Number_of_leechers_idx
  ON Popularity
   (num_leechers);

CREATE UNIQUE INDEX Popularity_idx
  ON Popularity
   (torrent_id, peer_id, msg_receive_time);

-- v4: Patch for ChannelCast, Search

CREATE TABLE ChannelCast (
publisher_id text,
publisher_name text,
infohash text,
torrenthash text,
torrentname text,
time_stamp integer,
signature text
);

CREATE INDEX pub_id_idx
on ChannelCast
(publisher_id);

CREATE INDEX pub_name_idx
on ChannelCast
(publisher_name);

CREATE INDEX infohash_ch_idx
on ChannelCast
(infohash);

----------------------------------------

CREATE TABLE InvertedIndex (
word               text NOT NULL,
torrent_id         integer
);

CREATE INDEX word_idx
on InvertedIndex
(word);

CREATE UNIQUE INDEX invertedindex_idx
on InvertedIndex
(word,torrent_id);

----------------------------------------

-- Set all similarity to zero because we are using a new similarity
-- function and the old values no longer correspond to the new ones
UPDATE Peer SET similarity = 0;
UPDATE Torrent SET relevance = 0;

"""
            self.execute_write(sql, commit=False)
        if fromver < 5:
            sql = \
"""
--------------------------------------
-- Creating Subtitles (future RichMetadata) DB
----------------------------------
CREATE TABLE Metadata (
  metadata_id integer PRIMARY KEY ASC AUTOINCREMENT NOT NULL,
  publisher_id text NOT NULL,
  infohash text NOT NULL,
  description text,
  timestamp integer NOT NULL,
  signature text NOT NULL,
  UNIQUE (publisher_id, infohash),
  FOREIGN KEY (publisher_id, infohash)
    REFERENCES ChannelCast(publisher_id, infohash)
    ON DELETE CASCADE -- the fk constraint is not enforced by sqlite
);

CREATE INDEX infohash_md_idx
on Metadata(infohash);

CREATE INDEX pub_md_idx
on Metadata(publisher_id);


CREATE TABLE Subtitles (
  metadata_id_fk integer,
  subtitle_lang text NOT NULL,
  subtitle_location text,
  checksum text NOT NULL,
  UNIQUE (metadata_id_fk,subtitle_lang),
  FOREIGN KEY (metadata_id_fk)
    REFERENCES Metadata(metadata_id)
    ON DELETE CASCADE, -- the fk constraint is not enforced by sqlite

  -- ISO639-2 uses 3 characters for lang codes
  CONSTRAINT lang_code_length
    CHECK ( length(subtitle_lang) == 3 )
);


CREATE INDEX metadata_sub_idx
on Subtitles(metadata_id_fk);

-- Stores the subtitles that peers have as an integer bitmask
 CREATE TABLE SubtitlesHave (
    metadata_id_fk integer,
    peer_id text NOT NULL,
    have_mask integer NOT NULL,
    received_ts integer NOT NULL, --timestamp indicating when the mask was received
    UNIQUE (metadata_id_fk, peer_id),
    FOREIGN KEY (metadata_id_fk)
      REFERENCES Metadata(metadata_id)
      ON DELETE CASCADE, -- the fk constraint is not enforced by sqlite

    -- 32 bit unsigned integer
    CONSTRAINT have_mask_length
      CHECK (have_mask >= 0 AND have_mask < 4294967296)
);

CREATE INDEX subtitles_have_idx
on SubtitlesHave(metadata_id_fk);

-- this index can boost queries
-- ordered by timestamp on the SubtitlesHave DB
CREATE INDEX subtitles_have_ts
on SubtitlesHave(received_ts);

"""

            self.execute_write(sql, commit=False)

        # P2P Services (ProxyService)
        if fromver < 6:
            sql = """
-- Patch for P2P Servivces (ProxyService)

ALTER TABLE Peer ADD COLUMN services integer DEFAULT 0;
"""
            self.execute_write(sql, commit=False)

        # Channelcast
        if fromver < 6:
            sql = 'Select * from ChannelCast'
            del_sql = 'Delete from ChannelCast where publisher_id = ? and infohash = ?'
            ins_sql = 'Insert into ChannelCast values (?, ?, ?, ?, ?, ?, ?)'

            seen = {}
            rows = self.fetchall(sql)
            for row in rows:
                if row[0] in seen and row[2] in seen[row[0]]:  # duplicate entry
                    self.execute_write(del_sql, (row[0], row[2]))
                    self.execute_write(ins_sql, (row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
                else:
                    seen.setdefault(row[0], set()).add(row[2])

            sql = 'CREATE UNIQUE INDEX publisher_id_infohash_idx on ChannelCast (publisher_id,infohash);'
            self.execute_write(sql, commit=False)

        if fromver < 7:
            sql = \
            """
            --------------------------------------
            -- Creating TermFrequency DB
            ----------------------------------
            CREATE TABLE TermFrequency (
              term_id        integer PRIMARY KEY AUTOINCREMENT DEFAULT 0,
              term           text NOT NULL,
              freq           integer,
              UNIQUE (term)
            );

            CREATE INDEX termfrequency_freq_idx
              ON TermFrequency
              (freq);

            CREATE TABLE TorrentBiTermPhrase (
              torrent_id     integer PRIMARY KEY NOT NULL,
              term1_id       integer,
              term2_id       integer,
              UNIQUE (torrent_id),
              FOREIGN KEY (torrent_id)
                REFERENCES Torrent(torrent_id),
              FOREIGN KEY (term1_id)
                REFERENCES TermFrequency(term_id),
              FOREIGN KEY (term2_id)
                REFERENCES TermFrequency(term_id)
            );
            CREATE INDEX torrent_biterm_phrase_idx
              ON TorrentBiTermPhrase
              (term1_id, term2_id);


            --------------------------------------
            -- Creating UserEventLog DB
            ----------------------------------
            CREATE TABLE UserEventLog (
              timestamp      numeric,
              type           integer,
              message        text
            );
            """
            self.execute_write(sql, commit=False)

        if fromver < 8:
            sql = \
            """
            --------------------------------------
            -- Creating BundlerPreference DB
            ----------------------------------
            CREATE TABLE BundlerPreference (
              query         text PRIMARY KEY,
              bundle_mode   integer
            );
            """
            self.execute_write(sql, commit=False)

        if fromver < 9:
            sql = \
            """
            CREATE TABLE IF NOT EXISTS _Channels (
              id                        integer         PRIMARY KEY ASC,
              dispersy_cid              text,
              peer_id                   integer,
              name                      text            NOT NULL,
              description               text,
              modified                  integer         DEFAULT (strftime('%s','now')),
              inserted                  integer         DEFAULT (strftime('%s','now')),
              deleted_at                integer,
              nr_torrents               integer         DEFAULT 0,
              nr_spam                   integer         DEFAULT 0,
              nr_favorite               integer         DEFAULT 0
            );
            CREATE VIEW Channels AS SELECT * FROM _Channels WHERE deleted_at IS NULL;

            CREATE TABLE IF NOT EXISTS _ChannelTorrents (
              id                        integer         PRIMARY KEY ASC,
              dispersy_id               integer,
              torrent_id                integer         NOT NULL,
              channel_id                integer         NOT NULL,
              peer_id                   integer,
              name                      text,
              description               text,
              time_stamp                integer,
              modified                  integer         DEFAULT (strftime('%s','now')),
              inserted                  integer         DEFAULT (strftime('%s','now')),
              deleted_at                integer,
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE VIEW ChannelTorrents AS SELECT * FROM _ChannelTorrents WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS TorChannelIndex ON _ChannelTorrents(channel_id);

            CREATE TABLE IF NOT EXISTS _Playlists (
              id                        integer         PRIMARY KEY ASC,
              channel_id                integer         NOT NULL,
              dispersy_id               integer         NOT NULL,
              peer_id                   integer,
              playlist_id               integer,
              name                      text            NOT NULL,
              description               text,
              modified                  integer         DEFAULT (strftime('%s','now')),
              inserted                  integer         DEFAULT (strftime('%s','now')),
              deleted_at                integer,
              UNIQUE (dispersy_id),
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE VIEW Playlists AS SELECT * FROM _Playlists WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS PlayChannelIndex ON _Playlists(channel_id);

            CREATE TABLE IF NOT EXISTS _PlaylistTorrents (
              dispersy_id           integer         NOT NULL,
              peer_id               integer,
              playlist_id           integer,
              channeltorrent_id     integer,
              deleted_at            integer,
              PRIMARY KEY (playlist_id, channeltorrent_id),
              FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE,
              FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
            );
            CREATE VIEW PlaylistTorrents AS SELECT * FROM _PlaylistTorrents WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS PlayTorrentIndex ON _PlaylistTorrents(playlist_id);

            CREATE TABLE IF NOT EXISTS _Comments (
              id                    integer         PRIMARY KEY ASC,
              dispersy_id           integer         NOT NULL,
              peer_id               integer,
              channel_id            integer         NOT NULL,
              comment               text            NOT NULL,
              reply_to_id           integer,
              reply_after_id        integer,
              time_stamp            integer,
              inserted              integer         DEFAULT (strftime('%s','now')),
              deleted_at            integer,
              UNIQUE (dispersy_id),
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE VIEW Comments AS SELECT * FROM _Comments WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS ComChannelIndex ON _Comments(channel_id);

            CREATE TABLE IF NOT EXISTS CommentPlaylist (
              comment_id            integer,
              playlist_id           integer,
              PRIMARY KEY (comment_id,playlist_id),
              FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE
              FOREIGN KEY (comment_id) REFERENCES Comments(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS CoPlaylistIndex ON CommentPlaylist(playlist_id);

            CREATE TABLE IF NOT EXISTS CommentTorrent (
              comment_id            integer,
              channeltorrent_id     integer,
              PRIMARY KEY (comment_id, channeltorrent_id),
              FOREIGN KEY (comment_id) REFERENCES Comments(id) ON DELETE CASCADE
              FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS CoTorrentIndex ON CommentTorrent(channeltorrent_id);

            CREATE TABLE IF NOT EXISTS _Moderations (
              id                    integer         PRIMARY KEY ASC,
              dispersy_id           integer         NOT NULL,
              channel_id            integer         NOT NULL,
              peer_id               integer,
              severity              integer         NOT NULL DEFAULT (0),
              message               text            NOT NULL,
              cause                 integer         NOT NULL,
              by_peer_id            integer,
              time_stamp            integer         NOT NULL,
              inserted              integer         DEFAULT (strftime('%s','now')),
              deleted_at            integer,
              UNIQUE (dispersy_id),
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE VIEW Moderations AS SELECT * FROM _Moderations WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS MoChannelIndex ON _Moderations(channel_id);

            CREATE TABLE IF NOT EXISTS _ChannelMetaData (
              id                    integer         PRIMARY KEY ASC,
              dispersy_id           integer         NOT NULL,
              channel_id            integer         NOT NULL,
              peer_id               integer,
              type_id               integer         NOT NULL,
              value                 text            NOT NULL,
              prev_modification     integer,
              prev_global_time      integer,
              time_stamp            integer         NOT NULL,
              inserted              integer         DEFAULT (strftime('%s','now')),
              deleted_at            integer,
              UNIQUE (dispersy_id),
              FOREIGN KEY (type_id) REFERENCES MetaDataTypes(id) ON DELETE CASCADE
            );
            CREATE VIEW ChannelMetaData AS SELECT * FROM _ChannelMetaData WHERE deleted_at IS NULL;
            CREATE TABLE IF NOT EXISTS MetaDataTypes (
              id                    integer         PRIMARY KEY ASC,
              name                  text            NOT NULL,
              type                  text            NOT NULL DEFAULT('text')
            );

            CREATE TABLE IF NOT EXISTS MetaDataTorrent (
              metadata_id           integer,
              channeltorrent_id     integer,
              PRIMARY KEY (metadata_id, channeltorrent_id),
              FOREIGN KEY (metadata_id) REFERENCES ChannelMetaData(id) ON DELETE CASCADE
              FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS MeTorrentIndex ON MetaDataTorrent(channeltorrent_id);

            CREATE TABLE IF NOT EXISTS MetaDataPlaylist (
              metadata_id           integer,
              playlist_id           integer,
              PRIMARY KEY (metadata_id,playlist_id),
              FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE
              FOREIGN KEY (metadata_id) REFERENCES ChannelMetaData(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS MePlaylistIndex ON MetaDataPlaylist(playlist_id);

            CREATE TABLE IF NOT EXISTS _ChannelVotes (
              channel_id            integer,
              voter_id              integer,
              dispersy_id           integer,
              vote                  integer,
              time_stamp            integer,
              deleted_at            integer,
              PRIMARY KEY (channel_id, voter_id)
            );
            CREATE VIEW ChannelVotes AS SELECT * FROM _ChannelVotes WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS ChaVotIndex ON _ChannelVotes(channel_id);
            CREATE INDEX IF NOT EXISTS VotChaIndex ON _ChannelVotes(voter_id);

            CREATE TABLE IF NOT EXISTS TorrentFiles (
              torrent_id            integer NOT NULL,
              path                  text    NOT NULL,
              length                integer NOT NULL,
              PRIMARY KEY (torrent_id, path)
            );
            CREATE INDEX IF NOT EXISTS TorFileIndex ON TorrentFiles(torrent_id);

            CREATE TABLE IF NOT EXISTS TorrentCollecting (
              torrent_id            integer NOT NULL,
              source                text    NOT NULL,
              PRIMARY KEY (torrent_id, source)
            );
            CREATE INDEX IF NOT EXISTS TorColIndex ON TorrentCollecting(torrent_id);

            CREATE TABLE IF NOT EXISTS _TorrentMarkings (
              dispersy_id           integer NOT NULL,
              channeltorrent_id     integer NOT NULL,
              peer_id               integer,
              global_time           integer,
              type                  text    NOT NULL,
              time_stamp            integer NOT NULL,
              deleted_at            integer,
              UNIQUE (dispersy_id),
              PRIMARY KEY (channeltorrent_id, peer_id)
            );
            CREATE VIEW TorrentMarkings AS SELECT * FROM _TorrentMarkings WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS TorMarkIndex ON _TorrentMarkings(channeltorrent_id);

            CREATE VIRTUAL TABLE FullTextIndex USING fts3(swarmname, filenames, fileextensions);

            INSERT INTO MetaDataTypes ('name') VALUES ('name');
            INSERT INTO MetaDataTypes ('name') VALUES ('description');
            """
            self.execute_write(sql, commit=False)

        # updating version stepwise so if this works, we store it
        # regardless of later, potentially failing updates
        self.writeDBVersion(CURRENT_MAIN_DB_VERSION, commit=False)
        self.commit()

        # now the start the process of parsing the torrents to insert into
        # InvertedIndex table.

        from Tribler.Core.Session import Session
        session = Session.get_instance()
        state_dir = session.get_state_dir()
        torrent_dir = session.get_torrent_collecting_dir()
        my_permid = session.get_permid()
        if my_permid:
            my_permid = bin2str(my_permid)

        tmpfilename = os.path.join(state_dir, "upgradingdb.txt")
        if fromver < 4 or os.path.exists(tmpfilename):
            def upgradeTorrents():
                # fetch some un-inserted torrents to put into the InvertedIndex
                sql = """
                SELECT torrent_id, name, torrent_file_name
                FROM Torrent
                WHERE torrent_id NOT IN (SELECT DISTINCT torrent_id FROM InvertedIndex)
                AND torrent_file_name IS NOT NULL
                LIMIT 20"""
                records = self.fetchall(sql)

                if len(records) == 0:
                    # upgradation is complete and hence delete the temp file
                    os.remove(tmpfilename)
                    if DEBUG: print >> sys.stderr, "DB Upgradation: temp-file deleted", tmpfilename
                    return

                for torrent_id, name, torrent_file_name in records:
                    try:
                        abs_filename = os.path.join(session.get_torrent_collecting_dir(), torrent_file_name)
                        if not os.path.exists(abs_filename):
                            raise RuntimeError(".torrent file not found. Use fallback.")
                        torrentdef = TorrentDef.load(abs_filename)
                        torrent_name = torrentdef.get_name_as_unicode()
                        keywords = Set(split_into_keywords(torrent_name))
                        for filename in torrentdef.get_files_as_unicode():
                            keywords.update(split_into_keywords(filename))

                    except:
                        # failure... most likely the .torrent file
                        # is invalid

                        # use keywords from the torrent name
                        # stored in the database
                        torrent_name = dunno2unicode(name)
                        keywords = Set(split_into_keywords(torrent_name))

                    # store the keywords in the InvertedIndex
                    # table in the database
                    if len(keywords) > 0:
                        values = [(keyword, torrent_id) for keyword in keywords]
                        self.executemany(u"INSERT OR REPLACE INTO InvertedIndex VALUES(?, ?)", values, commit=False)
                        if DEBUG:
                            print >> sys.stderr, "DB Upgradation: Extending the InvertedIndex table with", len(values), "new keywords for", torrent_name

                # now commit, after parsing the batch of torrents
                self.commit()

                # upgradation not yet complete; comeback after 5 sec
                tqueue.add_task(upgradeTorrents, 5)


            # Create an empty file to mark the process of upgradation.
            # In case this process is terminated before completion of upgradation,
            # this file remains even though fromver >= 4 and hence indicating that
            # rest of the torrents need to be inserted into the InvertedIndex!

            # ensure the temp-file is created, if it is not already
            try:
                open(tmpfilename, "w")
                if DEBUG: print >> sys.stderr, "DB Upgradation: temp-file successfully created"
            except:
                if DEBUG: print >> sys.stderr, "DB Upgradation: failed to create temp-file"

            if DEBUG: print >> sys.stderr, "Upgrading DB .. inserting into InvertedIndex"
            from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
            from sets import Set
            from Tribler.Core.Search.SearchManager import split_into_keywords
            from Tribler.Core.TorrentDef import TorrentDef

            # start the upgradation after 10 seconds
            tqueue = TimedTaskQueue("UpgradeDB")
            tqueue.add_task(upgradeTorrents, 10)

        if fromver < 7:
            # for now, fetch all existing torrents and extract terms
            from Tribler.Core.Tag.Extraction import TermExtraction
            extractor = TermExtraction.getInstance()

            sql = """
                SELECT torrent_id, name
                FROM Torrent
                WHERE name IS NOT NULL
                """
            ins_terms_sql = u"INSERT INTO TermFrequency (term, freq) VALUES(?, ?)"
            ins_phrase_sql = u"""INSERT INTO TorrentBiTermPhrase (torrent_id, term1_id, term2_id)
                                    SELECT ? AS torrent_id, TF1.term_id, TF2.term_id
                                    FROM TermFrequency TF1, TermFrequency TF2
                                    WHERE TF1.term = ? AND TF2.term = ?"""

            if DEBUG:
                dbg_ts1 = time()

            records = self.fetchall(sql)
            termcount = {}
            phrases = []  # torrent_id, term1, term2
            for torrent_id, name in records:
                terms = set(extractor.extractTerms(name))
                phrase = extractor.extractBiTermPhrase(name)

                # count terms
                for term in terms:
                    termcount[term] = termcount.get(term, 0) + 1

                # add bi-term phrase if not None
                if phrase is not None:
                    phrases.append((torrent_id,) + phrase)

            # insert terms and phrases
            self.executemany(ins_terms_sql, termcount.items(), commit=False)
            self.executemany(ins_phrase_sql, phrases, commit=False)
            self.commit()

            if DEBUG:
                dbg_ts2 = time()
                print >> sys.stderr, 'DB Upgradation: extracting and inserting terms took %ss' % (dbg_ts2 - dbg_ts1)

        if fromver < 8:
            if DEBUG:
                print >> sys.stderr, "STARTING UPGRADE"
                import time
                t1 = time.time()

            from Tribler.Core.Search.SearchManager import split_into_keywords

            # due to a bug, we have to insert all keywords with a length of 2
            sql = "SELECT torrent_id, name FROM CollectedTorrent"
            records = self.fetchall(sql)

            values = []
            for torrent_id, name in records:
                keywords = set(split_into_keywords(name))


                for keyword in keywords:
                    if len(keyword) == 2:
                        values.append((keyword, torrent_id))

            if DEBUG:
                t2 = time.time()

            self.executemany(u"INSERT OR IGNORE INTO InvertedIndex VALUES(?, ?)", values, commit=True)
            if DEBUG:
                print >> sys.stderr, "INSERTING NEW KEYWORDS TOOK", time.time() - t1, "INSERTING took", time.time() - t2

        tmpfilename = os.path.join(state_dir, "upgradingdb2.txt")
        if fromver < 9 or os.path.exists(tmpfilename):
            from Tribler.Core.Session import Session
            from time import time
            from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
            from Tribler.Core.Search.SearchManager import split_into_keywords
            from Tribler.Core.TorrentDef import TorrentDef

            # Create an empty file to mark the process of upgradation.
            # In case this process is terminated before completion of upgradation,
            # this file remains even though fromver >= 4 and hence indicating that
            # rest of the torrents need to be inserted into the InvertedIndex!

            # ensure the temp-file is created, if it is not already
            try:
                open(tmpfilename, "w")
                print >> sys.stderr, "DB Upgradation: temp-file successfully created"
            except:
                print >> sys.stderr, "DB Upgradation: failed to create temp-file"

            # start converting channelcastdb to new format
            finished_convert = "SELECT name FROM sqlite_master WHERE name='ChannelCast'"
            select_channels = "SELECT publisher_id, min(time_stamp), max(time_stamp) FROM ChannelCast WHERE publisher_name <> '' GROUP BY publisher_id"
            select_channel_name = "SELECT publisher_name FROM ChannelCast WHERE publisher_id = ? AND time_stamp = ? LIMIT 1"

            select_channel_torrent = "SELECT CollectedTorrent.torrent_id, time_stamp FROM ChannelCast, CollectedTorrent WHERE publisher_id = ? AND ChannelCast.infohash = CollectedTorrent.infohash Order By time_stamp DESC"

            select_channel_id = "SELECT id FROM Channels WHERE peer_id = ?"

            insert_channel = "INSERT INTO _Channels (dispersy_cid, peer_id, name, description, inserted, modified) VALUES (?, ?, ?, ?, ?, ?)"
            insert_channel_contents = "INSERT OR IGNORE INTO _ChannelTorrents (dispersy_id, torrent_id, channel_id, time_stamp, inserted) VALUES (?,?,?,?,?)"

            update_channel = "UPDATE _Channels SET nr_torrents = ? WHERE id = ?"

            select_votes = "SELECT mod_id, voter_id, vote, time_stamp FROM VoteCast Order By time_stamp ASC"
            insert_vote = "INSERT OR REPLACE INTO _ChannelVotes (channel_id, voter_id, dispersy_id, vote, time_stamp) VALUES (?,?,?,?,?)"

            if self.fetchone(finished_convert) == 'ChannelCast':

                # placeholders for dispersy channel conversion
                my_channel_name = None

                to_be_inserted = []
                t1 = time()

                # create channels
                permid_peerid = {}
                channel_permid_cid = {}
                channels = self.fetchall(select_channels)
                for publisher_id, mintimestamp, maxtimestamp in channels:
                    channel_name = self.fetchone(select_channel_name, (publisher_id, maxtimestamp))

                    if publisher_id == my_permid:
                        my_channel_name = channel_name
                        continue

                    peer_id = self.getPeerID(str2bin(publisher_id))
                    if peer_id:
                        permid_peerid[publisher_id] = peer_id
                        to_be_inserted.append((-1, peer_id, channel_name, '', mintimestamp, maxtimestamp))

                self.executemany(insert_channel, to_be_inserted)

                to_be_inserted = []

                # insert torrents
                for publisher_id, peer_id in permid_peerid.iteritems():
                    torrents = self.fetchall(select_channel_torrent, (publisher_id,))

                    channel_id = self.fetchone(select_channel_id, (peer_id,))
                    channel_permid_cid[publisher_id] = channel_id

                    for torrent_id, time_stamp in torrents:
                        to_be_inserted.append((-1, torrent_id, channel_id, long(time_stamp), long(time_stamp)))

                    self.execute_write(update_channel, (len(torrents), channel_id), commit=False)
                self.executemany(insert_channel_contents, to_be_inserted)

                # convert votes
                to_be_inserted = []
                votes = self.fetchall(select_votes)
                for mod_id, voter_id, vote, time_stamp in votes:
                    if mod_id != my_permid:  # cannot yet convert votes on my channel

                        channel_id = channel_permid_cid.get(mod_id, None)

                        if channel_id:
                            if voter_id == my_permid:
                                to_be_inserted.append((channel_id, None, -1, vote, time_stamp))
                            else:
                                peer_id = self.getPeerID(str2bin(voter_id))
                                if peer_id:
                                    to_be_inserted.append((channel_id, peer_id, -1, vote, time_stamp))

                self.executemany(insert_vote, to_be_inserted)

                # set cached nr_spam and nr_favorites
                votes = {}
                select_pos_vote = "SELECT channel_id, count(*) FROM ChannelVotes WHERE vote == 2 GROUP BY channel_id"
                select_neg_vote = "SELECT channel_id, count(*) FROM ChannelVotes WHERE vote == -1 GROUP BY channel_id"
                records = self.fetchall(select_pos_vote)
                for channel_id, pos_votes in records:
                    votes[channel_id] = [pos_votes, 0]

                records = self.fetchall(select_neg_vote)
                for channel_id, neg_votes in records:
                    if channel_id not in votes:
                        votes[channel_id] = [0, neg_votes]
                    else:
                        votes[channel_id][1] = neg_votes

                channel_tuples = [(values[1], values[0], channel_id) for channel_id, values in votes.iteritems()]
                update_votes = "UPDATE _Channels SET nr_spam = ?, nr_favorite = ? WHERE id = ?"
                self.executemany(update_votes, channel_tuples)

                print >> sys.stderr, "Converting took", time() - t1
                self.execute_write('DELETE FROM VoteCast WHERE mod_id <> ?', (my_permid,), commit=False)
                self.execute_write('DELETE FROM ChannelCast WHERE publisher_id <> ?', (my_permid,))

                select_mychannel_id = "SELECT id FROM Channels WHERE peer_id ISNULL LIMIT 1"
                select_votes_for_me = "SELECT voter_id, vote, time_stamp FROM VoteCast WHERE mod_id = ? Order By time_stamp ASC"
                select_mychannel_torrent = "SELECT CollectedTorrent.infohash, time_stamp, torrent_file_name FROM ChannelCast, CollectedTorrent WHERE publisher_id = ? AND ChannelCast.infohash = CollectedTorrent.infohash AND CollectedTorrent.torrent_id NOT IN (SELECT torrent_id FROM ChannelTorrents WHERE channel_id = ?) ORDER BY time_stamp DESC LIMIT ?"

                if my_channel_name:
                    def dispersy_started(subject, changeType, objectID):
                        print >> sys.stderr, "Dispersy started"

                        community = None
                        def create_my_channel():
                            global community

                            if my_channel_name:
                                channel_id = self.fetchone('SELECT id FROM Channels WHERE peer_id ISNULL LIMIT 1')

                                if channel_id:
                                    print >> sys.stderr, "Dispersy started, allready got community"
                                    dispersy_cid = self.fetchone("SELECT dispersy_cid FROM Channels WHERE id = ?", (channel_id,))
                                    dispersy_cid = str(dispersy_cid)

                                    community = dispersy.get_community(dispersy_cid)

                                else:
                                    print >> sys.stderr, "Dispersy started, creating community"

                                    community = ChannelCommunity.create_community(session.dispersy_member)
                                    community._disp_create_channel(my_channel_name, u'')

                                    print >> sys.stderr, "Dispersy started, community created"

                                # insert votes
                                insert_votes_for_me()

                                # schedule insert torrents
                                dispersy.callback.register(insert_my_torrents, delay=10.0)

                        def insert_votes_for_me():
                            print >> sys.stderr, "Dispersy started, inserting votes"
                            my_channel_id = self.fetchone(select_mychannel_id)

                            to_be_inserted = []

                            votes = self.fetchall(select_votes_for_me, (my_permid,))
                            for voter_id, vote, time_stamp in votes:
                                peer_id = self.getPeerID(str2bin(voter_id))
                                if peer_id:
                                    to_be_inserted.append((my_channel_id, peer_id, -1, vote, time_stamp))

                            if len(to_be_inserted) > 0:
                                self.executemany(insert_vote, to_be_inserted)

                                from Tribler.Core.CacheDB.SqliteCacheDBHandler import VoteCastDBHandler
                                votecast = VoteCastDBHandler.getInstance()
                                votecast._updateVotes(my_channel_id)

                        def insert_my_torrents():
                            global community

                            print >> sys.stderr, "Dispersy started, inserting torrents"
                            channel_id = self.fetchone(select_mychannel_id)
                            if channel_id:
                                batch_insert = 50

                                to_be_inserted = []
                                to_be_removed = []
                                torrents = self.fetchall(select_mychannel_torrent, (my_permid, channel_id, batch_insert))
                                for infohash, timestamp, torrent_file_name in torrents:
                                    timestamp = long(timestamp)
                                    infohash = str2bin(infohash)

                                    torrent_file_name = os.path.join(torrent_dir, torrent_file_name)
                                    if not os.path.isfile(torrent_file_name):
                                        _, tail = os.path.split(torrent_file_name)
                                        torrent_file_name = os.path.join(torrent_dir, tail)

                                    if os.path.isfile(torrent_file_name):
                                        torrentdef = TorrentDef.load(torrent_file_name)

                                        files = torrentdef.get_files_as_unicode_with_length()
                                        to_be_inserted.append((infohash, timestamp, torrentdef.get_name_as_unicode(), tuple(files), torrentdef.get_trackers_as_single_tuple()))
                                    else:
                                        to_be_removed.append((bin2str(infohash),))

                                if len(torrents) > 0:
                                    if len(to_be_inserted) > 0:
                                        community._disp_create_torrents(to_be_inserted, forward=False)

                                    if len(to_be_removed) > 0:
                                        self.executemany("DELETE FROM ChannelCast WHERE infohash = ?", to_be_removed)
                                    dispersy.callback.register(insert_my_torrents, delay=10.0)

                                else:  # done
                                    drop_channelcast = "DROP TABLE ChannelCast"
                                    self.execute_write(drop_channelcast)

                                    drop_votecast = "DROP TABLE VoteCast"
                                    self.execute_write(drop_votecast)
                            else:
                                dispersy.callback.register(insert_my_torrents, delay=10.0)

                        from Tribler.community.channel.community import ChannelCommunity
                        from Tribler.dispersy.dispersy import Dispersy
                        from Tribler.Core.TorrentDef import TorrentDef

                        global _callback
                        _callback.register(create_my_channel, delay=10.0)
                        session.remove_observer(dispersy_started)

                    session.add_observer(dispersy_started, NTFY_DISPERSY, [NTFY_STARTED])
                else:
                    drop_channelcast = "DROP TABLE ChannelCast"
                    self.execute_write(drop_channelcast)

                    drop_votecast = "DROP TABLE VoteCast"
                    self.execute_write(drop_votecast)

            def upgradeTorrents():
                print >> sys.stderr, "Upgrading DB .. inserting into FullTextIndex"

                # fetch some un-inserted torrents to put into the FullTextIndex
                sql = """
                SELECT torrent_id, name, infohash, num_files, torrent_file_name
                FROM CollectedTorrent
                WHERE torrent_id NOT IN (SELECT rowid FROM FullTextIndex)
                LIMIT 100"""
                records = self.fetchall(sql)

                if len(records) == 0:
                    # self.execute_write("DROP TABLE InvertedIndex")

                    # upgradation is complete and hence delete the temp file
                    os.remove(tmpfilename)
                    print >> sys.stderr, "DB Upgradation: temp-file deleted", tmpfilename
                    return

                values = []
                for torrent_id, name, infohash, num_files, torrent_filename in records:
                    try:
                        torrent_filename = os.path.join(torrent_dir, torrent_filename)

                        # .torrent found, return complete filename
                        if not os.path.isfile(torrent_filename):
                            # .torrent not found, possibly a new torrent_collecting_dir
                            torrent_filename = get_collected_torrent_filename(str2bin(infohash))
                            torrent_filename = os.path.join(torrent_dir, torrent_filename)

                        if not os.path.isfile(torrent_filename):
                            raise RuntimeError(".torrent file not found. Use fallback.")

                        torrentdef = TorrentDef.load(torrent_filename)

                        # Making sure that swarmname does not include extension for single file torrents
                        swarmname = torrentdef.get_name_as_unicode()
                        if not torrentdef.is_multifile_torrent():
                            swarmname, _ = os.path.splitext(swarmname)

                        filedict = {}
                        fileextensions = set()
                        for filename in torrentdef.get_files_as_unicode():
                            filename, extension = os.path.splitext(filename)
                            for keyword in split_into_keywords(filename, filterStopwords=True):
                                filedict[keyword] = filedict.get(keyword, 0) + 1

                            fileextensions.add(extension[1:])

                        filenames = filedict.keys()
                        if len(filenames) > 1000:
                            def popSort(a, b):
                                return filedict[a] - filedict[b]
                            filenames.sort(cmp=popSort, reverse=True)
                            filenames = filenames[:1000]

                    except RuntimeError:
                        swarmname = dunno2unicode(name)
                        fileextensions = set()
                        filenames = []

                        if num_files == 1:
                            swarmname, extension = os.path.splitext(swarmname)
                            fileextensions.add(extension[1:])

                            filenames.extend(split_into_keywords(swarmname, filterStopwords=True))

                    values.append((torrent_id, swarmname, " ".join(filenames), " ".join(fileextensions)))

                if len(values) > 0:
                    self.executemany(u"INSERT INTO FullTextIndex (rowid, swarmname, filenames, fileextensions) VALUES(?,?,?,?)", values, commit=True)

                # upgradation not yet complete; comeback after 5 sec
                tqueue.add_task(upgradeTorrents, 5)

            # start the upgradation after 10 seconds
            tqueue = TimedTaskQueue("UpgradeDB")
            tqueue.add_task(upgradeTorrents, 10)

        if fromver < 10:
            rename_table = "ALTER TABLE _PlaylistTorrents RENAME TO _PlaylistTorrents2"
            self.execute_write(rename_table)

            improved_table = """
            CREATE TABLE IF NOT EXISTS _PlaylistTorrents (
              id                    integer         PRIMARY KEY ASC,
              dispersy_id           integer         NOT NULL,
              peer_id               integer,
              playlist_id           integer,
              channeltorrent_id     integer,
              deleted_at            integer,
              FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE,
              FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
            );"""
            self.execute_write(improved_table)

            copy_data = "INSERT INTO _PlaylistTorrents (dispersy_id, peer_id, playlist_id, channeltorrent_id, deleted_at) SELECT dispersy_id, peer_id, playlist_id, channeltorrent_id, deleted_at FROM _PlaylistTorrents2"
            self.execute_write(copy_data)

            drop_table = "DROP TABLE _PlaylistTorrents2"
            self.execute_write(drop_table)

        if fromver < 11:
            index = "CREATE INDEX IF NOT EXISTS ChannelTorIndex ON _ChannelTorrents(torrent_id)"
            self.execute_write(index)

        if fromver < 12:
            remove_indexes = ["Message_receive_time_idx", "Size_calc_age_idx", "Number_of_seeders_idx", "Number_of_leechers_idx", "Torrent_length_idx", "Torrent_num_seeders_idx", "Torrent_num_leechers_idx"]
            for index in remove_indexes:
                self.execute_write("DROP INDEX %s" % index, commit=False)

            self.execute_write("CREATE INDEX Peer_local_oversion_idx ON Peer(is_local, oversion)", commit=False)
            self.execute_write("CREATE INDEX torrent_tracker_last_idx ON TorrentTracker (tracker, last_check)", commit=False)
            self.execute_write("CREATE INDEX IF NOT EXISTS ChannelTorChanIndex ON _ChannelTorrents(torrent_id, channel_id)")
            self.clean_db(True)

        if fromver < 13:
            self.execute_write("INSERT INTO MetaDataTypes ('name') VALUES ('swift-url');", commit=False)

        tmpfilename = os.path.join(state_dir, "upgradingdb3.txt")
        if fromver < 14 or os.path.exists(tmpfilename):
            if fromver < 14:
                self.execute_write("ALTER TABLE Torrent ADD COLUMN dispersy_id integer;", commit=False)
                self.execute_write("ALTER TABLE Torrent ADD COLUMN swift_hash text;", commit=False)
                self.execute_write("ALTER TABLE Torrent ADD COLUMN swift_torrent_hash text;", commit=False)
                self.execute_write("CREATE INDEX Torrent_insert_idx ON Torrent (insert_time, swift_torrent_hash);", commit=False)
                self.execute_write("CREATE INDEX Torrent_info_roothash_idx ON Torrent (infohash, swift_torrent_hash);")

            # Create an empty file to mark the process of upgradation.
            # In case this process is terminated before completion of upgradation,
            # this file remains even though fromver >= 14 and hence indicating that
            # rest of the collected torrents need to be swiftroothashed!

            from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
            from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler

            # ensure the temp-file is created, if it is not already
            try:
                open(tmpfilename, "w")
                print >> sys.stderr, "DB Upgradation: temp-file successfully created"
            except:
                print >> sys.stderr, "DB Upgradation: failed to create temp-file"

            def upgradeTorrents():
                print >> sys.stderr, "Upgrading DB .. hashing torrents"

                rth = RemoteTorrentHandler.getInstance()
                if rth.registered:

                    sql = "SELECT infohash, torrent_file_name FROM CollectedTorrent WHERE swift_torrent_hash IS NULL or swift_torrent_hash = '' LIMIT 100"
                    records = self.fetchall(sql)

                    found = []
                    not_found = []

                    if len(records) == 0:
                        os.remove(tmpfilename)
                        print >> sys.stderr, "DB Upgradation: temp-file deleted", tmpfilename
                        return

                    for infohash, torrent_filename in records:
                        if not os.path.isfile(torrent_filename):
                            torrent_filename = os.path.join(torrent_dir, torrent_filename)

                        # .torrent found, return complete filename
                        if not os.path.isfile(torrent_filename):
                            # .torrent not found, use default collected_torrent_filename
                            torrent_filename = get_collected_torrent_filename(str2bin(infohash))
                            torrent_filename = os.path.join(torrent_dir, torrent_filename)

                        if not os.path.isfile(torrent_filename):
                            not_found.append((infohash,))
                        else:
                            sdef, swiftpath = rth._write_to_collected(torrent_filename)
                            found.append((bin2str(sdef.get_roothash()), swiftpath, infohash))

                            os.remove(torrent_filename)

                    update = "UPDATE Torrent SET swift_torrent_hash = ?, torrent_file_name = ? WHERE infohash = ?"
                    self.executemany(update, found)

                    remove = "UPDATE Torrent SET torrent_file_name = NULL WHERE infohash = ?"
                    self.executemany(remove, not_found)

                # upgradation not yet complete; comeback after 5 sec
                tqueue.add_task(upgradeTorrents, 5)

            # start the upgradation after 10 seconds
            tqueue = TimedTaskQueue("UpgradeDB")
            tqueue.add_task(upgradeTorrents, 30)

        # Arno, 2012-07-30: Speed up
        if fromver < 15:
            self.execute_write("UPDATE Torrent SET swift_hash = NULL WHERE swift_hash = '' OR swift_hash = 'None'")
            duplicates = [(id_,) for id_, count in self.execute_read("SELECT torrent_id, count(*) FROM Torrent WHERE swift_hash NOT NULL GROUP BY swift_hash") if count > 1]
            if duplicates:
                self.executemany("UPDATE Torrent SET swift_hash = NULL WHERE torrent_id = ?", duplicates)
            self.execute_write("CREATE UNIQUE INDEX IF NOT EXISTS Torrent_swift_hash_idx ON Torrent(swift_hash)")

            self.execute_write("UPDATE Torrent SET swift_torrent_hash = NULL WHERE swift_torrent_hash = '' OR swift_torrent_hash = 'None'")
            duplicates = [(id_,) for id_, count in self.execute_read("SELECT torrent_id, count(*) FROM Torrent WHERE swift_torrent_hash NOT NULL GROUP BY swift_torrent_hash") if count > 1]
            if duplicates:
                self.executemany("UPDATE Torrent SET swift_torrent_hash = NULL WHERE torrent_id = ?", duplicates)
            self.execute_write("CREATE UNIQUE INDEX IF NOT EXISTS Torrent_swift_torrent_hash_idx ON Torrent(swift_torrent_hash)")

        # 02/08/2012 Boudewijn: the code allowed swift_torrent_hash to be an empty string
        if fromver < 16:
            self.execute_write("UPDATE Torrent SET swift_torrent_hash = NULL WHERE swift_torrent_hash = '' OR swift_torrent_hash = 'None'")

        if fromver < 17:
            self.execute_write("DROP TABLE IF EXISTS PREFERENCE")
            self.execute_write("DROP INDEX IF EXISTS Preference_peer_id_idx")
            self.execute_write("DROP INDEX IF EXISTS Preference_torrent_id_idx")
            self.execute_write("DROP INDEX IF EXISTS pref_idx")

            self.execute_write("DROP TABLE IF EXISTS Popularity")
            self.execute_write("DROP INDEX IF EXISTS Popularity_idx")

            self.execute_write("DROP TABLE IF EXISTS Metadata")
            self.execute_write("DROP INDEX IF EXISTS infohash_md_idx")
            self.execute_write("DROP INDEX IF EXISTS pub_md_idx")

            self.execute_write("DROP TABLE IF EXISTS Subtitles")
            self.execute_write("DROP INDEX IF EXISTS metadata_sub_idx")

            self.execute_write("DROP TABLE IF EXISTS SubtitlesHave")
            self.execute_write("DROP INDEX IF EXISTS subtitles_have_idx")
            self.execute_write("DROP INDEX IF EXISTS subtitles_have_ts", commit=True)

            update = list(self.execute_read("SELECT peer_id, torrent_id, term_id, term_order FROM ClicklogSearch"))
            results = self.execute_read("SELECT ClicklogTerm.term_id, TermFrequency.term_id FROM TermFrequency, ClicklogTerm WHERE TermFrequency.term == ClicklogTerm.term")
            updateDict = {}
            for old_termid, new_termid in results:
                updateDict[old_termid] = new_termid

            self.execute_write("DELETE FROM ClicklogSearch")
            for peer_id, torrent_id, term_id, term_order in update:
                if term_id in updateDict:
                    self.execute_write("INSERT INTO ClicklogSearch (peer_id, torrent_id, term_id, term_order) VALUES (?,?,?,?)", (peer_id, torrent_id, updateDict[term_id], term_order))

            self.execute_write("DROP TABLE IF EXISTS ClicklogTerm")
            self.execute_write("DROP INDEX IF EXISTS idx_terms_term")

            self.execute_write("DELETE FROM Peer WHERE superpeer = 1")
            self.execute_write("DROP VIEW IF EXISTS SuperPeer", commit=True)

            self.execute_write("DROP INDEX IF EXISTS Peer_name_idx")
            self.execute_write("DROP INDEX IF EXISTS Peer_ip_idx")
            self.execute_write("DROP INDEX IF EXISTS Peer_similarity_idx")
            self.execute_write("DROP INDEX IF EXISTS Peer_last_seen_idx")
            self.execute_write("DROP INDEX IF EXISTS Peer_last_connected_idx")
            self.execute_write("DROP INDEX IF EXISTS Peer_num_peers_idx")
            self.execute_write("DROP INDEX IF EXISTS Peer_num_torrents_idx")
            self.execute_write("DROP INDEX IF EXISTS Peer_local_oversion_idx")
            self.execute_write("DROP INDEX IF EXISTS Torrent_creation_date_idx")
            self.execute_write("DROP INDEX IF EXISTS Torrent_relevance_idx")
            self.execute_write("DROP INDEX IF EXISTS Torrent_name_idx")

        if fromver < 18:
            self.execute_write("DROP TABLE IF EXISTS BarterCast")
            self.execute_write("DROP INDEX IF EXISTS bartercast_idx")
            self.execute_write("INSERT INTO MetaDataTypes ('name') VALUES ('swift-thumbnails')")
            self.execute_write("INSERT INTO MetaDataTypes ('name') VALUES ('video-info')")


    def clean_db(self, vacuum=False):
        from time import time

        self.execute_write("DELETE FROM TorrentBiTermPhrase WHERE torrent_id NOT IN (SELECT torrent_id FROM CollectedTorrent)", commit=False)
        self.execute_write("DELETE FROM ClicklogSearch WHERE peer_id <> 0", commit=False)
        self.execute_write("DELETE FROM TorrentFiles where torrent_id in (select torrent_id from CollectedTorrent)", commit=False)
        self.execute_write("DELETE FROM Torrent where name is NULL and torrent_id not in (select torrent_id from _ChannelTorrents)")

        if vacuum:
            self.execute_read("VACUUM")

_cacheCommit = False
_shouldCommit = False

_callback = None
_callback_lock = RLock()

def try_register(db, callback=None):
    global _callback, _callback_lock

    if not _callback:
        _callback_lock.acquire()
        try:
            # check again if _callback hasn't been set, but now we are thread safe
            if not _callback:
                if callback and callback.is_running:
                    print >> sys.stderr, "Using actual DB thread", callback
                    _callback = callback

                    if db:
                        if currentThread().getName() == 'Dispersy':
                            db.initialBegin()
                        else:
                            # Niels: 15/05/2012: initalBegin HAS to be on the dispersy thread, as transactions are not shared across threads.
                            _callback.register(db.initialBegin, priority=1024)
        finally:
            _callback_lock.release()

def unregister():
    global _callback
    _callback = None

def register_task(db, *args, **kwargs):
    global _callback
    if not _callback:
        try_register(db)
    if not _callback or not _callback.is_running:
        def fakeDispersy(call, args=(), kwargs={}):
            call(*args, **kwargs)
        return fakeDispersy(*args)
    return _callback.register(*args, **kwargs)

def call_task(db, *args, **kwargs):
    global _callback
    if not _callback:
        try_register(db)

    if not _callback or not _callback.is_running:
        def fakeDispersy(call, args=(), kwargs={}):
            return call(*args, **kwargs)
        return fakeDispersy(*args)
    return _callback.call(*args, **kwargs)

def onDBThread():
    return currentThread().getName() == 'Dispersy'

def forceDBThread(func):
    def invoke_func(*args, **kwargs):
        if not onDBThread():
            if TRHEADING_DEBUG:
                stack = inspect.stack()
                callerstr = ""
                for i in range(1, min(4, len(stack))):
                    caller = stack[i]
                    callerstr += "%s %s:%s " % (caller[3], caller[1], caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO DBTHREAD %s %s:%s called by %s" % (func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)

            register_task(None, func, args, kwargs)
        else:
            func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func

def forcePrioDBThread(func):
    def invoke_func(*args, **kwargs):
        if not onDBThread():
            if TRHEADING_DEBUG:
                stack = inspect.stack()
                callerstr = ""
                for i in range(1, min(4, len(stack))):
                    caller = stack[i]
                    callerstr += "%s %s:%s " % (caller[3], caller[1], caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO DBTHREAD %s %s:%s called by %s" % (func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)

            register_task(None, func, args, kwargs, priority=99)
        else:
            func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func

def forceAndReturnDBThread(func):
    def invoke_func(*args, **kwargs):
        global _callback

        if not onDBThread():
            if TRHEADING_DEBUG:
                stack = inspect.stack()
                callerstr = ""
                for i in range(1, min(4, len(stack))):
                    caller = stack[i]
                    callerstr += "%s %s:%s" % (caller[3], caller[1], caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO DBTHREAD %s %s:%s called by %s" % (func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)

            return call_task(None, func, args, kwargs, timeout=15.0, priority=99)
        else:
            return func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func

class SQLiteNoCacheDB(SQLiteCacheDBV5):
    __single = None
    DEBUG = False
    if __debug__:
        __counter = 0

    @classmethod
    def getInstance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kw)
                    # print >>sys.stderr,"SqliteCacheDB: getInstance: created is",cls,cls.__single
            finally:
                cls.lock.release()
        return cls.__single

    @classmethod
    def delInstance(cls, *args, **kw):
        cls.__single = None

    def __init__(self, *args, **kargs):
        # always use getInstance() to create this object
        if self.__single != None:
            raise RuntimeError, "SQLiteCacheDB is singleton"
        SQLiteCacheDBBase.__init__(self, *args, **kargs)

        if __debug__:
            if self.__counter > 0:
                print_stack()
                raise RuntimeError("please use getInstance instead of the constructor")
            self.__counter += 1

    @forceDBThread
    def initialBegin(self):
        global _cacheCommit, _shouldCommit
        try:
            print >> sys.stderr, "SQLiteNoCacheDB.initialBegin: BEGIN"
            self._execute("BEGIN;")

        except:
            print >> sys.stderr, "INITIAL BEGIN FAILED"
            raise
        _cacheCommit = True
        _shouldCommit = True

    @forceDBThread
    def commitNow(self, vacuum=False, exiting=False):
        global _shouldCommit, _cacheCommit
        if _cacheCommit and _shouldCommit and onDBThread():
            try:
                if DEBUG: print >> sys.stderr, "SQLiteNoCacheDB.commitNow: COMMIT"
                self._execute("COMMIT;")
            except:
                print >> sys.stderr, "COMMIT FAILED"
                print_exc()
                raise
            _shouldCommit = False

            if vacuum:
                self._execute("VACUUM;")


            if not exiting:
                try:
                    print >> sys.stderr, "SQLiteNoCacheDB.commitNow: BEGIN"
                    self._execute("BEGIN;")
                except:
                    print >> sys.stderr, "BEGIN FAILED"
                    raise
            else:
                print >> sys.stderr, "SQLiteNoCacheDB.commitNow: not calling BEGIN exiting"

            # print_stack()

        elif vacuum:
            self._execute("VACUUM;")

    def execute_write(self, sql, args=None, commit=True):
        global _shouldCommit, _cacheCommit
        if _cacheCommit and not _shouldCommit:
            _shouldCommit = True

        self._execute(sql, args)

    def executemany(self, sql, args, commit=True):
        global _shouldCommit, _cacheCommit
        if _cacheCommit and not _shouldCommit:
            _shouldCommit = True

        return self._executemany(sql, args)

    def cache_transaction(self, sql, args=None):
        if DEPRECATION_DEBUG:
            raise DeprecationWarning('Please do not use cache_transaction')

    def transaction(self, sql=None, args=None):
        if DEPRECATION_DEBUG:
            raise DeprecationWarning('Please do not use transaction')

    def _transaction(self, sql, args=None):
        if DEPRECATION_DEBUG:
            raise DeprecationWarning('Please do not use _transaction')

    def commit(self):
        if DEPRECATION_DEBUG:
            raise DeprecationWarning('Please do not use commit')

    def clean_db(self, vacuum=False, exiting=False):
        SQLiteCacheDBV5.clean_db(self, False)

        if vacuum:
            self.commitNow(vacuum, exiting=exiting)

    @forceAndReturnDBThread
    def fetchone(self, sql, args=None):
        return SQLiteCacheDBV5.fetchone(self, sql, args)

    @forceAndReturnDBThread
    def fetchall(self, sql, args=None, retry=0):
        return SQLiteCacheDBV5.fetchall(self, sql, args, retry)

    @forceAndReturnDBThread
    def _execute(self, sql, args=None):
        cur = self.getCursor()

        if SHOW_ALL_EXECUTE or self.show_execute:
            thread_name = threading.currentThread().getName()
            print >> sys.stderr, '===', thread_name, '===\n', sql, '\n-----\n', args, '\n======\n'

        if __DEBUG_QUERIES__:
            f = open(DB_DEBUG_FILE, 'a')

            if args is None:
                f.write('QueryDebug: (%f) %s\n' % (time(), sql))
                for row in cur.execute('EXPLAIN QUERY PLAN ' + sql).fetchall():
                    f.write('%s %s %s\t%s\n' % row)
            else:
                f.write('QueryDebug: (%f) %s %s\n' % (time(), sql, str(args)))
                for row in cur.execute('EXPLAIN QUERY PLAN ' + sql, args).fetchall():
                    f.write('%s %s %s\t%s\n' % row[:4])

        try:
            if args is None:
                result = cur.execute(sql)
            else:
                result = cur.execute(sql, args)

            if __DEBUG_QUERIES__:
                f.write('QueryDebug: (%f) END\n' % time())
                f.close()

            return result

        except Exception, msg:
            if DEBUG:
                print_exc()
                print_stack()
                print >> sys.stderr, "cachedb: execute error:", Exception, msg
                thread_name = threading.currentThread().getName()
                print >> sys.stderr, '===', thread_name, '===\nSQL Type:', type(sql), '\n-----\n', sql, '\n-----\n', args, '\n======\n'
            raise msg

    @forceAndReturnDBThread
    def _executemany(self, sql, args=None):
        cur = self.getCursor()

        if SHOW_ALL_EXECUTE or self.show_execute:
            thread_name = threading.currentThread().getName()
            print >> sys.stderr, '===', thread_name, '===\n', sql, '\n-----\n', args, '\n======\n'

        if __DEBUG_QUERIES__:
            f = open(DB_DEBUG_FILE, 'a')

            if args is None:
                f.write('QueryDebug-executemany: (%f) %s\n' % (time(), sql))
                for row in cur.executemany('EXPLAIN QUERY PLAN ' + sql).fetchall():
                    f.write('%s %s %s\t%s\n' % row)
            else:
                f.write('QueryDebug-executemany: (%f) %s %d times\n' % (time(), sql, len(args)))
                for row in cur.executemany('EXPLAIN QUERY PLAN ' + sql, args).fetchall():
                    f.write('%s %s %s\t%s\n' % row)

        try:
            if args is None:
                result = cur.executemany(sql)
            else:
                result = cur.executemany(sql, args)

            if __DEBUG_QUERIES__:
                f.write('QueryDebug: (%f) END\n' % time())
                f.close()

            return result

        except Exception, msg:
            if DEBUG:
                print_exc()
                print_stack()
                print >> sys.stderr, "cachedb: execute error:", Exception, msg

                thread_name = threading.currentThread().getName()
                print >> sys.stderr, '===', thread_name, '===\nSQL Type:', type(sql), '\n-----\n', sql, '\n-----\n', args, '\n======\n'
            raise msg

# Arno, 2012-08-02: If this becomes multithreaded again, reinstate safe_dict() in caches
class SQLiteCacheDB(SQLiteNoCacheDB):
    __single = None  # used for multithreaded singletons pattern

    @classmethod
    def getInstance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kw)
                    # print >>sys.stderr,"SqliteCacheDB: getInstance: created is",cls,cls.__single
            finally:
                cls.lock.release()
        return cls.__single

    @classmethod
    def delInstance(cls, *args, **kw):
        cls.__single = None

    @classmethod
    def hasInstance(cls, *args, **kw):
        return cls.__single != None

    def __init__(self, *args, **kargs):
        # always use getInstance() to create this object

        # ARNOCOMMENT: why isn't the lock used on this read?!

        if self.__single != None:
            raise RuntimeError, "SQLiteCacheDB is singleton"
        SQLiteNoCacheDB.__init__(self, *args, **kargs)

    def schedule_task(self, task, delay=0.0):
        register_task(None, task, delay=delay)

if __name__ == '__main__':
    configure_dir = sys.argv[1]
    config = {}
    config['state_dir'] = configure_dir
    config['install_dir'] = u'.'
    config['peer_icon_path'] = u'.'
    sqlite_test = init(config)
    sqlite_test.test()
