# Written by Jie Yang
# see LICENSE.txt for license information

import sys
import os
from os import environ
from time import sleep, time
from base64 import encodestring, decodestring
import threading
from traceback import print_exc, print_stack
import logging

from Tribler.Core.simpledefs import INFOHASH_LENGTH, NTFY_DISPERSY, NTFY_STARTED
from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.Utilities.unicode import dunno2unicode

# ONLY USE APSW >= 3.5.9-r1
import apsw
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from threading import currentThread, Event, RLock, Lock
import inspect
from Tribler.Core.Swift.SwiftDef import SwiftDef

import logging

# support_version = (3,5,9)
# support_version = (3,3,13)
# apsw_version = tuple([int(r) for r in apsw.apswversion().split('-')[0].split('.')])
# print apsw_version
# assert apsw_version >= support_version, "Required APSW Version >= %d.%d.%d."%support_version + " But your version is %d.%d.%d.\n"%apsw_version + \
#                        "Please download and install it from http://code.google.com/p/apsw/"

# Changed from 4 to 5 by andrea for subtitles support
# Changed from 5 to 6 by George Milescu for ProxyService
# Changed from 6 to 7 for Raynor's TermFrequency table
# Changed from 7 to 8 for Raynor's BundlerPreference table
# Changed from 8 to 9 for Niels's Open2Edit tables
# Changed from 9 to 10 for Fix in Open2Edit PlayListTorrent table
# Changed from 10 to 11 add a index on channeltorrent.torrent_id to improve search performance
# Changed from 11 to 12 imposing some limits on the Tribler database
# Changed from 12 to 13 introduced swift-url modification type
# Changed from 13 to 14 introduced swift_hash/swift_torrent_hash torrent columns + upgrade script
# Changed from 14 to 15 added indices on swift_hash/swift_torrent_hash torrent
# Changed from 15 to 16 changed all swift_torrent_hash that was an empty string to NULL
# Changed from 16 to 17 cleaning buddycast, preference, terms, and subtitles tables, removed indices
# Changed from 17 to 18 added swift-thumbnails/video-info metadatatypes
# Changed from 18 to 19 added torrent checking, cleaned Peer table

# Arno, 2012-08-01: WARNING You must also update the version number that is
# written to the DB in the schema_sdb_v*.sql file!!!
CURRENT_MAIN_DB_VERSION = 19

config_dir = None
CREATE_SQL_FILE = None

CREATE_SQL_FILE_POSTFIX = os.path.join(LIBRARYNAME, 'schema_sdb_v' + str(CURRENT_MAIN_DB_VERSION) + '.sql')
DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = 'sqlite'  # db file path = DB_DIR_NAME/DB_FILE_NAME
DEFAULT_BUSY_TIMEOUT = 10000
SHOW_ALL_EXECUTE = False
TEST_OVERRIDE = False

INITIAL_UPGRADE_PAUSE = 10
SUCCESIVE_UPGRADE_PAUSE = 5
UPGRADE_BATCH_SIZE = 100

DEBUG_THREAD = False
DEBUG_TIME = True

TRHEADING_DEBUG = False
DEPRECATION_DEBUG = False

logger = logging.getLogger(__name__)

__DEBUG_QUERIES__ = 'TRIBLER_DEBUG_DATABASE_QUERIES' in environ
if __DEBUG_QUERIES__:
    from random import randint
    from os.path import exists
    from time import time
    DB_DEBUG_FILE = "tribler_database_queries_%d.txt" % randint(1, 9999999)
    while exists(DB_DEBUG_FILE):
        DB_DEBUG_FILE = "tribler_database_queries_%d.txt" % randint(1, 9999999)


class Warning(Exception):
    pass


def init(state_dir, install_dir, db_exception_handler=None):
    """ create sqlite database """
    global CREATE_SQL_FILE
    global config_dir
    config_dir = state_dir
    CREATE_SQL_FILE = os.path.join(install_dir, CREATE_SQL_FILE_POSTFIX)

    sqlite_db_path = os.path.join(config_dir, DB_DIR_NAME, DB_FILE_NAME)
    logger.info("cachedb: init: SQL FILE %s", sqlite_db_path)

    sqlitedb = SQLiteCacheDB.getInstance(db_exception_handler)
    sqlitedb.initDB(sqlite_db_path, CREATE_SQL_FILE)  # the first place to create db in Tribler
    return sqlitedb


def bin2str(bin):
    # Full BASE64-encoded
    return encodestring(bin).replace("\n", "")


def str2bin(str):
    return decodestring(str)


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

    def __init__(self, db_exception_handler=None):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._connection = None

        self.exception_handler = db_exception_handler

        self.cursor_lock = RLock()
        self.cursor_table = {}

        self.database_update = None

    def __del__(self):
        self.close_all()

    def close(self):
        # only close the connection object in this thread, don't close other thread's connection object
        thread_name = threading.currentThread().getName()
        cur = self.getCursor(create=False)
        if cur:
            self._close_cur(thread_name, cur)

        self._connection.close()

    def close_all(self):
        with self.cursor_lock:
            if self.cursor_table:
                for thread_name, cur in self.cursor_table.items():
                    self._close_cur(thread_name, cur)

                self.cursor_table = None

    def _close_cur(self, thread_name, cur):
        cur.close()

        with self.cursor_lock:
            assert self.cursor_table
            del self.cursor_table[thread_name]

    def getCursor(self, create=True):
        thread_name = threading.currentThread().getName()

        with self.cursor_lock:
            assert self.cursor_table != None

            cur = self.cursor_table.get(thread_name, None)
            if cur is None and create:
                cur = self._connection.cursor()
                self.cursor_table[thread_name] = cur
            cur = self.cursor_table.get(thread_name)

        return cur

    def initDB(self, sqlite_filepath,
               create_sql_filename=None,
               busytimeout=DEFAULT_BUSY_TIMEOUT):
        """
        Create and initialize a SQLite database given a sql script.
        Only one db can be opened. If the given dbfile_path is different with the opened DB file, warn and exit
        @configure_dir     The directory containing 'bsddb' directory
        @sql_filename      The path of sql script to create the tables in the database
                           Every statement must end with a ';'.
        @busytimeout       Set the maximum time, in milliseconds, to wait and retry
                           if failed to acquire a lock. Default = 5000 milliseconds
        """
        assert sqlite_filepath is not None

        self._logger.info(u"Initializing SQLite DB.")
        try:
            if create_sql_filename is None:
                create_sql_filename = CREATE_SQL_FILE

            if not self._openDb(sqlite_filepath, create_sql_filename, busytimeout):
                return None

            if create_sql_filename is not None:
                self._checkDB()

            return self.getCursor()

        except Exception as err:
            self._logger.error(u"Cannot initialize SQLite DB.")
            self._logger.debug(u"Error: %s", err)
            return None

    def _openDb(self, dbfile_path, sql_path, busytimeout=DEFAULT_BUSY_TIMEOUT):
        """
        Opens or creates the database.
        """
        assert dbfile_path is not None
        assert busytimeout > 0

        # pre-checks
        if dbfile_path.lower() != u":memory:":
            # create db if it doesn't exist
            if not os.path.exists(dbfile_path):
                to_create_new_db = True

                db_dir, _ = os.path.split(dbfile_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir)

            else:
                # db is not a file
                if not os.path.isfile(dbfile_path):
                    self._logger.error(u"DB path is not a file.")
                    self._logger.debug(u"DB path: %s", dbfile_path)
                    return False

        # create DB connection
        try:
            self._connection = apsw.Connection(dbfile_path)
        except Exception as err:
            self._logger.error(u"Cannot create SQLite connection.")
            self._logger.debug(u"Error: %s", err)
            self._logger.debug(u"DB path: %s", dbfile_path)
            return False
        # some settings
        self._connection.setbusytimeout(busytimeout)

        cursor = self.getCursor()

        # create table
        try:
            sql_file = open(sql_path, 'r')
            sql = sql_file.read()
            sql_file.close()
        except Exception as err:
            self._logger.error(u"Cannot create SQLite connection.")
            self._logger.debug(u"Error: %s", err)
            self._logger.debug(u"SQL file path: %s", sql_path)
            return False

        # create tables
        try:
            cursor.execute(sql)
        except Exception as err:
            self._logger.error(u"Cannot create SQL tables.")
            self._logger.debug(u"Error: %s", err)
            self._logger.debug(u"SQL statement: %s", sql)
            return False

        # set PRAGMA options
        page_size = next(cursor.execute("PRAGMA page_size"))
        if page_size < 8192:
            # journal_mode and page_size only need to be set once.  because of the VACUUM this
            # is very expensive
            self._logger.debug(u"begin page_size upgrade...")
            cursor.execute("PRAGMA journal_mode = DELETE;")
            cursor.execute("PRAGMA page_size = 8192;")
            cursor.execute("VACUUM;")
            self._logger.debug(u"...end page_size upgrade")

        # http://www.sqlite.org/pragma.html
        # When synchronous is NORMAL, the SQLite database engine will still
        # pause at the most critical moments, but less often than in FULL
        # mode. There is a very small (though non-zero) chance that a power
        # failure at just the wrong time could corrupt the database in
        # NORMAL mode. But in practice, you are more likely to suffer a
        # catastrophic disk failure or some other unrecoverable hardware
        # fault.
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA cache_size = 10000;")

        # Niels 19-09-2012: even though my database upgraded to increase
        # the pagesize it did not keep wal mode?
        # Enabling WAL on every starup
        cursor.execute("PRAGMA journal_mode = WAL;")

        return True

    def _checkDB(self):
        db_ver = self.readDBVersion()
        curr_ver = CURRENT_MAIN_DB_VERSION

        if not db_ver or not curr_ver:
            self.updateDB(db_ver, curr_ver)
            return

        db_ver = int(db_ver)
        curr_ver = int(curr_ver)

        self.db_diff = max(0, curr_ver - db_ver)
        if not self.db_diff:
            self.db_diff = sum(os.path.exists(os.path.join(config_dir, filename)) if config_dir else 0 for filename in ["upgradingdb.txt", "upgradingdb2.txt", "upgradingdb3.txt", "upgradingdb4.txt"])

        if self.db_diff:
            self.database_update = threading.Semaphore(self.db_diff)
            self.updateDB(db_ver, curr_ver)

    def readDBVersion(self):
        sql = u"SELECT value FROM MyInfo WHERE entry = 'version'"
        result = self.fetchone(sql)
        return result

    def writeDBVersion(self, version):
        sql = u"UPDATE MyInfo SET value = ? WHERE entry = 'version'"
        self._execute(sql, (version,))

    def updateDB(self, db_ver, curr_ver):
        pass

    def waitForUpdateComplete(self):
        if self.database_update:
            for _ in range(self.db_diff):
                self.database_update.acquire()

            for _ in range(self.db_diff):
                self.database_update.release()

    # --------- generic functions -------------

    def _execute(self, sql, args=None):
        cur = self.getCursor()

        if SHOW_ALL_EXECUTE:
            thread_name = threading.currentThread().getName()
            self._logger.info('===%s===\n%s\n-----\n%s\n======\n', thread_name, sql, args)

        try:
            if args is None:
                return cur.execute(sql)
            else:
                return cur.execute(sql, args)

        except Exception as msg:
            if str(msg).startswith("BusyError"):
                self._logger.error("cachedb: busylock error")

            else:
                print_exc()
                print_stack()
                self._logger.error("cachedb: execute error: %s, %s", Exception, msg)
                thread_name = threading.currentThread().getName()
                self._logger.error('===%s===\nSQL Type: %s\n-----\n%s\n-----\n%s\n======\n', thread_name, type(sql), sql, args)

            raise msg

    def _executemany(self, sql, args=None):
        cur = self.getCursor()

        if SHOW_ALL_EXECUTE:
            thread_name = threading.currentThread().getName()
            self._logger.info('===%s===\n%s\n-----\n%s\n======\n', thread_name, sql, args)

        try:
            if args is None:
                return cur.executemany(sql)
            else:
                return cur.executemany(sql, args)

        except Exception as msg:
            if str(msg).startswith("BusyError"):
                self._logger.error("cachedb: busylock error")
            else:
                print_exc()
                print_stack()
                self._logger.error("cachedb: execute error: %s, %s", Exception, msg)
                thread_name = threading.currentThread().getName()
                self._logger.error('===%s===\nSQL Type: %s\n-----\n%s\n-----\n%s\n======\n', thread_name, type(sql), sql, args)

            raise msg

    def executemany(self, sql, args):
        self._executemany(sql, args)

    # TODO: may remove this, no one uses it.
    def insert_or_replace(self, table_name, **argv):
        if len(argv) == 1:
            sql = 'INSERT OR REPLACE INTO %s (%s) VALUES (?);' % (table_name, argv.keys()[0])
        else:
            questions = '?,' * len(argv)
            sql = 'INSERT OR REPLACE INTO %s %s VALUES (%s);' % (table_name, tuple(argv.keys()), questions[:-1])
        self._execute(sql, argv.values())

    def insert_or_ignore(self, table_name, **argv):
        if len(argv) == 1:
            sql = 'INSERT OR IGNORE INTO %s (%s) VALUES (?);' % (table_name, argv.keys()[0])
        else:
            questions = '?,' * len(argv)
            sql = 'INSERT OR IGNORE INTO %s %s VALUES (%s);' % (table_name, tuple(argv.keys()), questions[:-1])
        self._execute(sql, argv.values())

    def insert(self, table_name, **argv):
        if len(argv) == 1:
            sql = 'INSERT INTO %s (%s) VALUES (?);' % (table_name, argv.keys()[0])
        else:
            questions = '?,' * len(argv)
            sql = 'INSERT INTO %s %s VALUES (%s);' % (table_name, tuple(argv.keys()), questions[:-1])
        self._execute(sql, argv.values())

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
            if where != None:
                sql += u' where %s' % where
            self._execute(sql, arg)

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
        self._execute(sql, argv.values())

    # -------- Read Operations --------
    def size(self, table_name):
        num_rec_sql = u"SELECT count(*) FROM %s LIMIT 1" % table_name
        result = self.fetchone(num_rec_sql)
        return result

    def fetchone(self, sql, args=None):
        find = self._execute(sql, args)
        if not find:
            return None
        else:
            find = list(find)
            if len(find) > 0:
                if len(find) > 1:
                    self._logger.debug("FetchONE resulted in many more rows than one, consider putting a LIMIT 1 in the sql statement %s, %s", sql, len(find))
                find = find[0]
            else:
                return None
        if len(find) > 1:
            return find
        else:
            return find[0]

    def fetchall(self, sql, args=None):
        res = self._execute(sql, args)
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
                if isinstance(v, tuple):
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
        except Exception as msg:
            self._logger.error("sqldb: Wrong getAll sql statement: %s", sql)
            print_exc()
            raise Exception(msg)


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

            self._execute(sql)

        if fromver < 3:
            sql = """
-- Patch for Local Peer Discovery

ALTER TABLE Peer ADD COLUMN is_local integer DEFAULT 0;
"""
            self._execute(sql)

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
            self._execute(sql)
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

            self._execute(sql)

        # P2P Services (ProxyService)
        if fromver < 6:
            sql = """
-- Patch for P2P Servivces (ProxyService)

ALTER TABLE Peer ADD COLUMN services integer DEFAULT 0;
"""
            self._execute(sql)

        # Channelcast
        if fromver < 6:
            sql = 'Select * from ChannelCast'
            del_sql = 'Delete from ChannelCast where publisher_id = ? and infohash = ?'
            ins_sql = 'Insert into ChannelCast values (?, ?, ?, ?, ?, ?, ?)'

            seen = {}
            rows = self.fetchall(sql)
            for row in rows:
                if row[0] in seen and row[2] in seen[row[0]]:  # duplicate entry
                    self._execute(del_sql, (row[0], row[2]))
                    self._execute(ins_sql, (row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
                else:
                    seen.setdefault(row[0], set()).add(row[2])

            sql = 'CREATE UNIQUE INDEX publisher_id_infohash_idx on ChannelCast (publisher_id,infohash);'
            self._execute(sql)

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
            self._execute(sql)

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
            self._execute(sql)

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
            self._execute(sql)

        # updating version stepwise so if this works, we store it
        # regardless of later, potentially failing updates
        self.writeDBVersion(CURRENT_MAIN_DB_VERSION)

        tqueue = None

        def kill_threadqueue_if_empty():
            if tqueue.get_nr_tasks() == 0:
                tqueue.shutdown(True)
            else:
                tqueue.add_task(kill_threadqueue_if_empty, SUCCESIVE_UPGRADE_PAUSE, "kill_if_empty")

        from Tribler.Core.Session import Session
        session = Session.get_instance()
        state_dir = session.get_state_dir()
        torrent_dir = session.get_torrent_collecting_dir()
        my_permid = session.get_permid()
        if my_permid:
            my_permid = bin2str(my_permid)

        tmpfilename = os.path.join(state_dir, "upgradingdb.txt")
        if fromver < 4 or os.path.exists(tmpfilename):
            self.database_update.acquire()

            def upgradeTorrents():
                self._logger.info("Upgrading DB .. inserting into InvertedIndex")

                # fetch some un-inserted torrents to put into the InvertedIndex
                sql = """
                SELECT torrent_id, name, torrent_file_name
                FROM Torrent
                WHERE torrent_id NOT IN (SELECT DISTINCT torrent_id FROM InvertedIndex)
                AND torrent_file_name IS NOT NULL
                LIMIT %d""" % UPGRADE_BATCH_SIZE
                records = self.fetchall(sql)

                if len(records) == 0:
                    # upgradation is complete and hence delete the temp file
                    if os.path.exists(tmpfilename):
                        os.remove(tmpfilename)
                        self._logger.info("DB Upgradation: temp-file deleted %s", tmpfilename)

                    self.database_update.release()
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
                        self.executemany(u"INSERT OR REPLACE INTO InvertedIndex VALUES(?, ?)", values)
                        self._logger.debug("DB Upgradation: Extending the InvertedIndex table with %d new keywords for %s", len(values), torrent_name)

                # upgradation not yet complete; comeback after 5 sec
                tqueue.add_task(upgradeTorrents, SUCCESIVE_UPGRADE_PAUSE)

            # Create an empty file to mark the process of upgradation.
            # In case this process is terminated before completion of upgradation,
            # this file remains even though fromver >= 4 and hence indicating that
            # rest of the torrents need to be inserted into the InvertedIndex!
            # ensure the temp-file is created, if it is not already
            try:
                open(tmpfilename, "w")
                self._logger.info("DB Upgradation: temp-file successfully created %s", tmpfilename)
            except:
                self._logger.error("DB Upgradation: failed to create temp-file %s", tmpfilename)

            self._logger.debug("Upgrading DB .. inserting into InvertedIndex")
            from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
            from sets import Set
            from Tribler.Core.Search.SearchManager import split_into_keywords
            from Tribler.Core.TorrentDef import TorrentDef

            # start the upgradation after 10 seconds
            if not tqueue:
                tqueue = TimedTaskQueue("UpgradeDB")
                tqueue.add_task(kill_threadqueue_if_empty, INITIAL_UPGRADE_PAUSE + 1, "kill_if_empty")
            tqueue.add_task(upgradeTorrents, INITIAL_UPGRADE_PAUSE)

        if fromver < 7:
            self.database_update.acquire()

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
            import time
            dbg_ts1 = time.time()

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
            self.executemany(ins_terms_sql, termcount.items())
            self.executemany(ins_phrase_sql, phrases)

            dbg_ts2 = time.time()
            self._logger.debug('DB Upgradation: extracting and inserting terms took %s s', dbg_ts2 - dbg_ts1)

            self.database_update.release()

        if fromver < 8:
            self.database_update.acquire()

            self._logger.debug("STARTING UPGRADE")
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

            t2 = time.time()

            self.executemany(u"INSERT OR IGNORE INTO InvertedIndex VALUES(?, ?)", values)
            self._logger.debug("INSERTING NEW KEYWORDS TOOK %s INSERTING took %s", time.time() - t1, time.time() - t2)

            self.database_update.release()

        tmpfilename2 = os.path.join(state_dir, "upgradingdb2.txt")
        if fromver < 9 or os.path.exists(tmpfilename2):
            self.database_update.acquire()

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
                open(tmpfilename2, "w")
                self._logger.info("DB Upgradation: temp-file successfully created %s", tmpfilename2)
            except:
                self._logger.error("DB Upgradation: failed to create temp-file %s", tmpfilename2)

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

                    self._execute(update_channel, (len(torrents), channel_id))
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

                self._execute('DELETE FROM VoteCast WHERE mod_id <> ?', (my_permid,))
                self._execute('DELETE FROM ChannelCast WHERE publisher_id <> ?', (my_permid,))

                select_mychannel_id = "SELECT id FROM Channels WHERE peer_id ISNULL LIMIT 1"
                select_votes_for_me = "SELECT voter_id, vote, time_stamp FROM VoteCast WHERE mod_id = ? Order By time_stamp ASC"
                select_mychannel_torrent = "SELECT CollectedTorrent.infohash, time_stamp, torrent_file_name FROM ChannelCast, CollectedTorrent WHERE publisher_id = ? AND ChannelCast.infohash = CollectedTorrent.infohash AND CollectedTorrent.torrent_id NOT IN (SELECT torrent_id FROM ChannelTorrents WHERE channel_id = ?) ORDER BY time_stamp DESC LIMIT ?"

                if my_channel_name:
                    def dispersy_started(subject, changeType, objectID):
                        self._logger.info("Dispersy started")
                        dispersy = session.lm.dispersy
                        callback = dispersy.callback

                        community = None

                        def create_my_channel():
                            global community

                            if my_channel_name:
                                channel_id = self.fetchone('SELECT id FROM Channels WHERE peer_id ISNULL LIMIT 1')

                                if channel_id:
                                    self._logger.info("Dispersy started, allready got community")
                                    dispersy_cid = self.fetchone("SELECT dispersy_cid FROM Channels WHERE id = ?", (channel_id,))
                                    dispersy_cid = str(dispersy_cid)

                                    community = dispersy.get_community(dispersy_cid)

                                else:
                                    self._logger.info("Dispersy started, creating community")

                                    community = ChannelCommunity.create_community(session.dispersy_member)
                                    community._disp_create_channel(my_channel_name, u'')

                                    self._logger.info("Dispersy started, community created")

                                # insert votes
                                insert_votes_for_me()

                                # schedule insert torrents
                                dispersy.callback.register(insert_my_torrents, delay=10.0)

                        def insert_votes_for_me():
                            self._logger.info("Dispersy started, inserting votes")
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

                            self._logger.info("Dispersy started, inserting torrents")
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
                                    self._execute(drop_channelcast)

                                    drop_votecast = "DROP TABLE VoteCast"
                                    self._execute(drop_votecast)
                            else:
                                dispersy.callback.register(insert_my_torrents, delay=float(SUCCESIVE_UPGRADE_PAUSE))

                        from Tribler.community.channel.community import ChannelCommunity
                        from Tribler.Core.TorrentDef import TorrentDef

                        callback.register(create_my_channel, delay=float(INITIAL_UPGRADE_PAUSE))
                        session.remove_observer(dispersy_started)

                    session.add_observer(dispersy_started, NTFY_DISPERSY, [NTFY_STARTED])
                else:
                    drop_channelcast = "DROP TABLE ChannelCast"
                    self._execute(drop_channelcast)

                    drop_votecast = "DROP TABLE VoteCast"
                    self._execute(drop_votecast)

            def upgradeTorrents2():
                if not os.path.exists(tmpfilename):
                    self._logger.info("Upgrading DB .. inserting into FullTextIndex")

                    # fetch some un-inserted torrents to put into the FullTextIndex
                    sql = """
                    SELECT torrent_id, name, infohash, num_files, torrent_file_name
                    FROM CollectedTorrent
                    WHERE torrent_id NOT IN (SELECT rowid FROM FullTextIndex)
                    LIMIT %d""" % UPGRADE_BATCH_SIZE
                    records = self.fetchall(sql)

                    if len(records) == 0:
                        self._execute("DROP TABLE InvertedIndex")

                        if os.path.exists(tmpfilename2):
                            # upgradation is complete and hence delete the temp file
                            os.remove(tmpfilename2)
                            self._logger.info("DB Upgradation: temp-file deleted %s", tmpfilename2)

                        self.database_update.release()
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
                        self.executemany(u"INSERT INTO FullTextIndex (rowid, swarmname, filenames, fileextensions) VALUES(?,?,?,?)", values)

                # upgradation not yet complete; comeback after 5 sec
                tqueue.add_task(upgradeTorrents2, SUCCESIVE_UPGRADE_PAUSE)

            # start the upgradation after 10 seconds
            if not tqueue:
                tqueue = TimedTaskQueue("UpgradeDB")
                tqueue.add_task(kill_threadqueue_if_empty, INITIAL_UPGRADE_PAUSE + 1, "kill_if_empty")
            tqueue.add_task(upgradeTorrents2, INITIAL_UPGRADE_PAUSE)

        if fromver < 10:
            self.database_update.acquire()

            rename_table = "ALTER TABLE _PlaylistTorrents RENAME TO _PlaylistTorrents2"
            self._execute(rename_table)

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
            self._execute(improved_table)

            copy_data = "INSERT INTO _PlaylistTorrents (dispersy_id, peer_id, playlist_id, channeltorrent_id, deleted_at) SELECT dispersy_id, peer_id, playlist_id, channeltorrent_id, deleted_at FROM _PlaylistTorrents2"
            self._execute(copy_data)

            drop_table = "DROP TABLE _PlaylistTorrents2"
            self._execute(drop_table)

            self.database_update.release()

        if fromver < 11:
            self.database_update.acquire()

            index = "CREATE INDEX IF NOT EXISTS ChannelTorIndex ON _ChannelTorrents(torrent_id)"
            self._execute(index)

            self.database_update.release()

        if fromver < 12:
            self.database_update.acquire()

            remove_indexes = ["Message_receive_time_idx", "Size_calc_age_idx", "Number_of_seeders_idx", "Number_of_leechers_idx", "Torrent_length_idx", "Torrent_num_seeders_idx", "Torrent_num_leechers_idx"]
            for index in remove_indexes:
                self._execute("DROP INDEX %s" % index)

            self._execute("CREATE INDEX Peer_local_oversion_idx ON Peer(is_local, oversion)")
            self._execute("CREATE INDEX torrent_tracker_last_idx ON TorrentTracker (tracker, last_check)")
            self._execute("CREATE INDEX IF NOT EXISTS ChannelTorChanIndex ON _ChannelTorrents(torrent_id, channel_id)")
            self.clean_db(True)

            self.database_update.release()

        if fromver < 13:
            self.database_update.acquire()
            self._execute("INSERT INTO MetaDataTypes ('name') VALUES ('swift-url');")
            self.database_update.release()

        tmpfilename3 = os.path.join(state_dir, "upgradingdb3.txt")
        if fromver < 14 or os.path.exists(tmpfilename3):
            self.database_update.acquire()

            if fromver < 14:
                self._execute("ALTER TABLE Torrent ADD COLUMN dispersy_id integer;")
                self._execute("ALTER TABLE Torrent ADD COLUMN swift_hash text;")
                self._execute("ALTER TABLE Torrent ADD COLUMN swift_torrent_hash text;")
                self._execute("CREATE INDEX Torrent_insert_idx ON Torrent (insert_time, swift_torrent_hash);")
                self._execute("CREATE INDEX Torrent_info_roothash_idx ON Torrent (infohash, swift_torrent_hash);")

            # Create an empty file to mark the process of upgradation.
            # In case this process is terminated before completion of upgradation,
            # this file remains even though fromver >= 14 and hence indicating that
            # rest of the collected torrents need to be swiftroothashed!

            from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
            from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler

            # ensure the temp-file is created, if it is not already
            try:
                open(tmpfilename3, "w")
                self._logger.info("DB Upgradation: temp-file successfully created %s", tmpfilename3)
            except:
                self._logger.error("DB Upgradation: failed to create temp-file %s", tmpfilename3)

            def upgradeTorrents3():
                if not (os.path.exists(tmpfilename2) or os.path.exists(tmpfilename)):
                    self._logger.info("Upgrading DB .. hashing torrents")

                    rth = RemoteTorrentHandler.getInstance()
                    if rth.registered or TEST_OVERRIDE:
                        if not TEST_OVERRIDE:
                            sql = "SELECT infohash, torrent_file_name FROM CollectedTorrent WHERE swift_torrent_hash IS NULL or swift_torrent_hash = '' LIMIT %d" % UPGRADE_BATCH_SIZE
                            records = self.fetchall(sql)
                        else:
                            records = []

                        found = []
                        not_found = []

                        if len(records) == 0:
                            if os.path.exists(tmpfilename3):
                                os.remove(tmpfilename3)
                                self._logger.info("DB Upgradation: temp-file deleted %s", tmpfilename3)

                            self.database_update.release()
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
                tqueue.add_task(upgradeTorrents3, SUCCESIVE_UPGRADE_PAUSE)

            # start the upgradation after 10 seconds
            if not tqueue:
                tqueue = TimedTaskQueue("UpgradeDB")
                tqueue.add_task(kill_threadqueue_if_empty, INITIAL_UPGRADE_PAUSE + 1, "kill_if_empty")
            tqueue.add_task(upgradeTorrents3, INITIAL_UPGRADE_PAUSE)

        # Arno, 2012-07-30: Speed up
        if fromver < 15:
            self.database_update.acquire()

            self._execute("UPDATE Torrent SET swift_hash = NULL WHERE swift_hash = '' OR swift_hash = 'None'")
            duplicates = [(id_,) for id_, count in self._execute("SELECT torrent_id, count(*) FROM Torrent WHERE swift_hash NOT NULL GROUP BY swift_hash") if count > 1]
            if duplicates:
                self.executemany("UPDATE Torrent SET swift_hash = NULL WHERE torrent_id = ?", duplicates)
            self._execute("CREATE UNIQUE INDEX IF NOT EXISTS Torrent_swift_hash_idx ON Torrent(swift_hash)")

            self._execute("UPDATE Torrent SET swift_torrent_hash = NULL WHERE swift_torrent_hash = '' OR swift_torrent_hash = 'None'")
            duplicates = [(id_,) for id_, count in self._execute("SELECT torrent_id, count(*) FROM Torrent WHERE swift_torrent_hash NOT NULL GROUP BY swift_torrent_hash") if count > 1]
            if duplicates:
                self.executemany("UPDATE Torrent SET swift_torrent_hash = NULL WHERE torrent_id = ?", duplicates)
            self._execute("CREATE UNIQUE INDEX IF NOT EXISTS Torrent_swift_torrent_hash_idx ON Torrent(swift_torrent_hash)")

            self.database_update.release()

        # 02/08/2012 Boudewijn: the code allowed swift_torrent_hash to be an empty string
        if fromver < 16:
            self.database_update.acquire()

            self._execute("UPDATE Torrent SET swift_torrent_hash = NULL WHERE swift_torrent_hash = '' OR swift_torrent_hash = 'None'")

            self.database_update.release()

        if fromver < 17:
            self.database_update.acquire()

            self._execute("DROP TABLE IF EXISTS PREFERENCE")
            self._execute("DROP INDEX IF EXISTS Preference_peer_id_idx")
            self._execute("DROP INDEX IF EXISTS Preference_torrent_id_idx")
            self._execute("DROP INDEX IF EXISTS pref_idx")

            self._execute("DROP TABLE IF EXISTS Popularity")
            self._execute("DROP INDEX IF EXISTS Popularity_idx")

            self._execute("DROP TABLE IF EXISTS Metadata")
            self._execute("DROP INDEX IF EXISTS infohash_md_idx")
            self._execute("DROP INDEX IF EXISTS pub_md_idx")

            self._execute("DROP TABLE IF EXISTS Subtitles")
            self._execute("DROP INDEX IF EXISTS metadata_sub_idx")

            self._execute("DROP TABLE IF EXISTS SubtitlesHave")
            self._execute("DROP INDEX IF EXISTS subtitles_have_idx")
            self._execute("DROP INDEX IF EXISTS subtitles_have_ts")

            update = list(self._execute("SELECT peer_id, torrent_id, term_id, term_order FROM ClicklogSearch"))
            results = self._execute("SELECT ClicklogTerm.term_id, TermFrequency.term_id FROM TermFrequency, ClicklogTerm WHERE TermFrequency.term == ClicklogTerm.term")
            updateDict = {}
            for old_termid, new_termid in results:
                updateDict[old_termid] = new_termid

            self._execute("DELETE FROM ClicklogSearch")
            for peer_id, torrent_id, term_id, term_order in update:
                if term_id in updateDict:
                    self._execute("INSERT INTO ClicklogSearch (peer_id, torrent_id, term_id, term_order) VALUES (?,?,?,?)", (peer_id, torrent_id, updateDict[term_id], term_order))

            self._execute("DROP TABLE IF EXISTS ClicklogTerm")
            self._execute("DROP INDEX IF EXISTS idx_terms_term")

            self._execute("DELETE FROM Peer WHERE superpeer = 1")
            self._execute("DROP VIEW IF EXISTS SuperPeer")

            self._execute("DROP INDEX IF EXISTS Peer_name_idx")
            self._execute("DROP INDEX IF EXISTS Peer_ip_idx")
            self._execute("DROP INDEX IF EXISTS Peer_similarity_idx")
            self._execute("DROP INDEX IF EXISTS Peer_last_seen_idx")
            self._execute("DROP INDEX IF EXISTS Peer_last_connected_idx")
            self._execute("DROP INDEX IF EXISTS Peer_num_peers_idx")
            self._execute("DROP INDEX IF EXISTS Peer_num_torrents_idx")
            self._execute("DROP INDEX IF EXISTS Peer_local_oversion_idx")
            self._execute("DROP INDEX IF EXISTS Torrent_creation_date_idx")
            self._execute("DROP INDEX IF EXISTS Torrent_relevance_idx")
            self._execute("DROP INDEX IF EXISTS Torrent_name_idx")

            self.database_update.release()

        if fromver < 18:
            self.database_update.acquire()

            self._execute("DROP TABLE IF EXISTS BarterCast")
            self._execute("DROP INDEX IF EXISTS bartercast_idx")
            self._execute("INSERT INTO MetaDataTypes ('name') VALUES ('swift-thumbnails')")
            self._execute("INSERT INTO MetaDataTypes ('name') VALUES ('video-info')")

            self.database_update.release()

        tmpfilename4 = os.path.join(state_dir, "upgradingdb4.txt")
        if fromver < 19 or os.path.exists(tmpfilename4):
            self.database_update.acquire()

            all_found_tracker_dict = dict()
            def getTrackerID(tracker):
                sql = 'SELECT tracker_id FROM TrackerInfo WHERE tracker = ?'
                return self.fetchone(sql, [tracker, ])

            # only perform these changes once
            if fromver < 19:
                self.database_update.acquire()

                from Tribler.TrackerChecking.TrackerUtility import getUniformedURL

                # drop Peer columns
                drop_table = "DROP VIEW Friend"
                self._execute(drop_table)

                rename_table = "ALTER TABLE Peer RENAME TO __Peer_tmp"
                self._execute(rename_table)

                improved_peer_table = """
                CREATE TABLE Peer (
                    peer_id    integer PRIMARY KEY AUTOINCREMENT NOT NULL,
                    permid     text NOT NULL,
                    name       text,
                    thumbnail  text
                );"""
                self._execute(improved_peer_table)

                copy_data = """
                INSERT INTO Peer (peer_id, permid, name, thumbnail)
                SELECT peer_id, permid, name, thumbnail FROM __Peer_tmp
                """
                self._execute(copy_data)

                drop_table = "DROP TABLE __Peer_tmp"
                self._execute(drop_table)

                # new columns in Torrent table
                self._execute(
                    "ALTER TABLE Torrent ADD COLUMN last_tracker_check integer DEFAULT 0")
                self._execute(
                    "ALTER TABLE Torrent ADD COLUMN tracker_check_retries integer DEFAULT 0")
                self._execute(
                    "ALTER TABLE Torrent ADD COLUMN next_tracker_check integer DEFAULT 0")

                create_new_table = """
                    CREATE TABLE TrackerInfo (
                      tracker_id  integer PRIMARY KEY AUTOINCREMENT,
                      tracker     text    UNIQUE NOT NULL,
                      last_check  numeric DEFAULT 0,
                      failures    integer DEFAULT 0,
                      is_alive    integer DEFAULT 1
                    );"""
                self._execute(create_new_table)

                create_new_table = """
                    CREATE TABLE TorrentTrackerMapping (
                      torrent_id  integer NOT NULL,
                      tracker_id  integer NOT NULL,
                      FOREIGN KEY (torrent_id) REFERENCES Torrent(torrent_id),
                      FOREIGN KEY (tracker_id) REFERENCES TrackerInfo(tracker_id),
                      PRIMARY KEY (torrent_id, tracker_id)
                    );"""
                self._execute(create_new_table)

                insert_dht_tracker = 'INSERT INTO TrackerInfo(tracker) VALUES(?)'
                default_tracker_list = [ ('no-DHT',), ('DHT',) ]
                self.executemany(insert_dht_tracker, default_tracker_list)

                self._logger.info('Importing information from TorrentTracker ...')
                sql = 'SELECT torrent_id, tracker FROM TorrentTracker'\
                    + ' WHERE torrent_id NOT IN (SELECT torrent_id FROM CollectedTorrent)'

                insert_tracker_set = set()
                insert_mapping_set = set()
                try:
                    raw_mapping_cur = self._execute(sql)
                    for torrent_id, tracker in raw_mapping_cur:
                        tracker_url = getUniformedURL(tracker)
                        if tracker_url:
                            insert_tracker_set.add((tracker_url,))
                            insert_mapping_set.add((torrent_id, tracker_url))

                except Exception as e:
                    self._logger.error('fetching tracker from TorrentTracker %s', e)

                insert = 'INSERT INTO TrackerInfo(tracker) VALUES(?)'
                self.executemany(insert, list(insert_tracker_set))

                # get tracker IDs
                for tracker, in insert_tracker_set:
                    all_found_tracker_dict[tracker] = getTrackerID(tracker)

                # insert mapping
                mapping_set = set()
                for torrent_id, tracker in insert_mapping_set:
                    mapping_set.add((torrent_id, all_found_tracker_dict[tracker]))

                insert = 'INSERT OR IGNORE INTO TorrentTrackerMapping(torrent_id, tracker_id) VALUES(?, ?)'
                self.executemany(insert, list(mapping_set))

                self._execute('DROP TABLE IF EXISTS TorrentTracker')

                self.database_update.release()

            all_found_tracker_dict['no-DHT'] = getTrackerID('no-DHT')
            all_found_tracker_dict['DHT'] = getTrackerID('DHT')

            # ensure the temp-file is created, if it is not already
            try:
                open(tmpfilename4, "w")
                self._logger.info("DB v19 Upgradation: temp-file successfully created %s", tmpfilename4)
            except:
                self._logger.error("DB v19 Upgradation: failed to create temp-file %s", tmpfilename4)

            from Tribler.TrackerChecking.TrackerUtility import getUniformedURL
            from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
            from Tribler.Core.TorrentDef import TorrentDef

            def upgradeDBV19():
                if not (os.path.exists(tmpfilename3) or os.path.exists(tmpfilename2) or os.path.exists(tmpfilename)):
                    self._logger.info('Upgrading DB to v19 ...')

                    if not TEST_OVERRIDE:
                        self._logger.info('Importing information from CollectedTorrent ...')
                        sql = 'SELECT torrent_id, infohash, torrent_file_name FROM CollectedTorrent'\
                            + ' WHERE torrent_id NOT IN (SELECT torrent_id FROM TorrentTrackerMapping)'\
                            + ' AND torrent_file_name IS NOT NULL'\
                            + ' LIMIT %d' % UPGRADE_BATCH_SIZE

                        records = self.fetchall(sql)
                    else:
                        records = None

                    if not records:
                        self._execute('DROP TABLE IF EXISTS TorrentTracker')
                        self._execute('DROP INDEX IF EXISTS torrent_tracker_idx')
                        self._execute('DROP INDEX IF EXISTS torrent_tracker_last_idx')

                        if os.path.exists(tmpfilename4):
                            os.remove(tmpfilename4)
                            self._logger.info('DB v19 Upgrade: temp-file deleted %s', tmpfilename4)

                        self._logger.info('DB v19 upgrade complete.')
                        self.database_update.release()
                        return

                    found_torrent_tracker_map_set = set()
                    newly_found_tracker_set = set()
                    not_found_torrent_file_set = set()
                    update_secret_set = set()

                    for torrent_id, infohash, torrent_filename in records:
                        if not os.path.isfile(torrent_filename):
                            torrent_filename = os.path.join(torrent_dir, torrent_filename)

                        # .torrent found, return complete filename
                        if not os.path.isfile(torrent_filename):
                            # .torrent not found, use default collected_torrent_filename
                            torrent_filename = get_collected_torrent_filename(str2bin(infohash))
                            torrent_filename = os.path.join(torrent_dir, torrent_filename)

                        if os.path.isfile(torrent_filename):
                            try:
                                torrent = TorrentDef.load(torrent_filename)

                                # check DHT
                                if torrent.is_private():
                                    found_torrent_tracker_map_set.add((torrent_id, 'no-DHT'))
                                    update_secret_set.add((1, torrent_id))
                                else:
                                    found_torrent_tracker_map_set.add((torrent_id, 'DHT'))
                                    update_secret_set.add((0, torrent_id))

                                # check trackers
                                tracker_tuple = torrent.get_trackers_as_single_tuple()
                                for tracker in tracker_tuple:
                                    tracker_url = getUniformedURL(tracker)
                                    if tracker_url:
                                        if tracker_url not in all_found_tracker_dict:
                                            newly_found_tracker_set.add((tracker_url,))
                                        found_torrent_tracker_map_set.add((torrent_id, tracker_url))

                                else:
                                    not_found_torrent_file_set.add((torrent_id,))

                            except Exception as e:
                                # some torrent files may not be loaded correctly
                                pass

                        else:
                            not_found_torrent_file_set.add((torrent_id,))

                    if not_found_torrent_file_set:
                        remove = 'UPDATE Torrent SET torrent_file_name = NULL WHERE torrent_id = ?'
                        self.executemany(remove, list(not_found_torrent_file_set))

                    if update_secret_set:
                        update_secret = 'UPDATE Torrent SET secret = ? WHERE torrent_id = ?'
                        self.executemany(update_secret, list(update_secret_set))

                    if newly_found_tracker_set:
                        insert = 'INSERT OR IGNORE INTO TrackerInfo(tracker) VALUES(?)'
                        self.executemany(insert, list(newly_found_tracker_set))

                        from Tribler.Core.CacheDB.Notifier import Notifier, NTFY_TRACKERINFO, NTFY_INSERT
                        notifier = Notifier.getInstance()
                        notifier.notify(NTFY_TRACKERINFO, NTFY_INSERT, list(newly_found_tracker_set))

                    # load tracker dictionary
                    for tracker, in newly_found_tracker_set:
                        all_found_tracker_dict[tracker] = getTrackerID(tracker)

                    if found_torrent_tracker_map_set:
                        insert_list = list()
                        for torrent_id, tracker in found_torrent_tracker_map_set:
                            insert_list.append((torrent_id, all_found_tracker_dict[tracker]))
                        insert = 'INSERT OR IGNORE INTO TorrentTrackerMapping(torrent_id, tracker_id)'\
                            + ' VALUES(?, ?)'
                        self.executemany(insert, insert_list)

                # upgradation not yet complete; comeback after 5 sec
                tqueue.add_task(upgradeDBV19, SUCCESIVE_UPGRADE_PAUSE)

            # start the upgradation after 10 seconds
            if not tqueue:
                tqueue = TimedTaskQueue('UpgradeDB')
                tqueue.add_task(kill_threadqueue_if_empty, INITIAL_UPGRADE_PAUSE + 1, 'kill_if_empty')
            tqueue.add_task(upgradeDBV19, INITIAL_UPGRADE_PAUSE)

    def clean_db(self, vacuum=False):
        from time import time

        self._execute("DELETE FROM TorrentBiTermPhrase WHERE torrent_id NOT IN (SELECT torrent_id FROM CollectedTorrent)")
        self._execute("DELETE FROM ClicklogSearch WHERE peer_id <> 0")
        self._execute("DELETE FROM TorrentFiles where torrent_id in (select torrent_id from CollectedTorrent)")
        self._execute("DELETE FROM Torrent where name is NULL and torrent_id not in (select torrent_id from _ChannelTorrents)")

        if vacuum:
            self._execute("VACUUM")

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
                    logger.info("Using actual DB thread %s", callback)
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
                for i in range(1, min(10, len(stack))):
                    caller = stack[i]
                    callerstr += "%s %s:%s " % (caller[3], caller[1], caller[2])
                logger.debug("%d SWITCHING TO DBTHREAD %s %s:%s called by %s", long(time()), func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)

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
                for i in range(1, min(10, len(stack))):
                    caller = stack[i]
                    callerstr += "%s %s:%s " % (caller[3], caller[1], caller[2])
                logger.debug("%d SWITCHING TO DBTHREAD %s %s:%s called by %s", long(time()), func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)

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
                for i in range(1, min(10, len(stack))):
                    caller = stack[i]
                    callerstr += "%s %s:%s" % (caller[3], caller[1], caller[2])
                logger.debug("%d SWITCHING TO DBTHREAD %s %s:%s called by %s", long(time()), func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)

            return call_task(None, func, args, kwargs, timeout=15.0, priority=99)
        else:
            return func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func


class SQLiteNoCacheDB(SQLiteCacheDBV5):
    if __debug__:
        __counter = 0

    def __init__(self, *args, **kargs):
        SQLiteCacheDBBase.__init__(self, *args, **kargs)

        if __debug__:
            if self.__counter > 0:
                print_stack()
                raise RuntimeError("please use getInstance instead of the constructor")
            self.__counter += 1

    @forceDBThread
    def initialBegin(self):
        global _shouldCommit
        try:
            self._logger.info("SQLiteNoCacheDB.initialBegin: BEGIN")
            self._execute("BEGIN;")

        except:
            self._logger.error("INITIAL BEGIN FAILED")
            raise
        _shouldCommit = True

    @forceDBThread
    def commitNow(self, vacuum=False, exiting=False):
        global _shouldCommit
        if _shouldCommit and onDBThread():
            try:
                self._logger.info("SQLiteNoCacheDB.commitNow: COMMIT")
                self._execute("COMMIT;")
            except:
                self._logger.error("COMMIT FAILED")
                print_exc()
                raise
            _shouldCommit = False

            if vacuum:
                self._execute("VACUUM;")

            if not exiting:
                try:
                    self._logger.info("SQLiteNoCacheDB.commitNow: BEGIN")
                    self._execute("BEGIN;")
                except:
                    self._logger.error("BEGIN FAILED")
                    raise
            else:
                self._logger.info("SQLiteNoCacheDB.commitNow: not calling BEGIN exiting")

            # print_stack()

        elif vacuum:
            self._execute("VACUUM;")

    def _execute(self, sql, args=None):
        global _shouldCommit
        if not _shouldCommit:
            _shouldCommit = True

        self.__execute(sql, args)

    def executemany(self, sql, args):
        global _shouldCommit
        if not _shouldCommit:
            _shouldCommit = True

        return self._executemany(sql, args)

    def clean_db(self, vacuum=False, exiting=False):
        SQLiteCacheDBV5.clean_db(self, False)

        if vacuum:
            self.commitNow(vacuum, exiting=exiting)

    @forceAndReturnDBThread
    def fetchone(self, sql, args=None):
        return SQLiteCacheDBV5.fetchone(self, sql, args)

    @forceAndReturnDBThread
    def fetchall(self, sql, args=None):
        return SQLiteCacheDBV5.fetchall(self, sql, args)

    @forceAndReturnDBThread
    def __execute(self, sql, args=None):
        cur = self.getCursor()

        if SHOW_ALL_EXECUTE:
            thread_name = threading.currentThread().getName()
            self._logger.info('===%s===\n%s\n-----\n%s\n======\n', thread_name, sql, args)

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

        except Exception as msg:
            print_exc()
            print_stack()
            self._logger.error("cachedb: execute error: %s, %s", Exception, msg)
            thread_name = threading.currentThread().getName()
            self._logger.error('===%s===\nSQL Type: %s\n-----\n%s\n-----\n%s\n======\n', thread_name, type(sql), sql, args)
            raise msg

    @forceAndReturnDBThread
    def _executemany(self, sql, args=None):
        cur = self.getCursor()

        if SHOW_ALL_EXECUTE:
            thread_name = threading.currentThread().getName()
            self._logger.info('===%s===\n%s\n-----\n%s\n======\n', thread_name, sql, args)

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

        except Exception as msg:
            self._logger.debug("cachedb: execute error: %s %s", Exception, msg)
            print_exc()
            print_stack()

            thread_name = threading.currentThread().getName()
            self._logger.debug('===%s===\nSQL Type: %s\n-----\n%s\n-----\n%s\n======\n', thread_name, type(sql), sql, args)
            raise msg

# Arno, 2012-08-02: If this becomes multithreaded again, reinstate safe_dict() in caches


class SQLiteCacheDB(SQLiteNoCacheDB):
    __single = None  # used for multithreaded singletons pattern

    def __init__(self, *args, **kargs):
        # always use getInstance() to create this object
        if self.__single != None:
            raise RuntimeError("SQLiteCacheDB is singleton")
        SQLiteNoCacheDB.__init__(self, *args, **kargs)

    @classmethod
    def getInstance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            if cls.__single is None:
                cls.__single = cls(*args, **kw)
                # print >>sys.stderr,"SqliteCacheDB: getInstance: created is",cls,cls.__single
        return cls.__single

    @classmethod
    def delInstance(cls, *args, **kw):
        cls.__single = None

    @classmethod
    def hasInstance(cls, *args, **kw):
        return cls.__single != None

    def schedule_task(self, task, delay=0.0):
        register_task(None, task, delay=delay)
