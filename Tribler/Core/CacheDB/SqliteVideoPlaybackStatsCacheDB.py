# Written by Boudewijn Schoon
# see LICENSE.txt for license information

"""
Database wrapper to add and retrieve Video playback statistics
"""

import sys
import os
import thread
from base64 import b64encode
from time import time

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDBBase
from Tribler.Core.CacheDB.SqliteCacheDBHandler import BasicDBHandler

CREATE_VIDEOPLAYBACK_STATS_SQL_FILE = None
CREATE_VIDEOPLAYBACK_STATS_SQL_FILE_POSTFIX = os.path.join(LIBRARYNAME, 'Core', 'Statistics', "tribler_videoplayback_stats.sql")
DB_FILE_NAME = 'tribler_videoplayback_stats.sdb'
DB_DIR_NAME = 'sqlite'    # db file path = DB_DIR_NAME/DB_FILE_NAME
CURRENT_DB_VERSION = 2

DEBUG = False

def init_videoplayback_stats(config, db_exception_handler = None):
    """ create VideoPlayback statistics database """
    global CREATE_VIDEOPLAYBACK_STATS_SQL_FILE
    config_dir = config['state_dir']
    install_dir = config['install_dir']
    CREATE_VIDEOPLAYBACK_STATS_SQL_FILE = os.path.join(install_dir,CREATE_VIDEOPLAYBACK_STATS_SQL_FILE_POSTFIX)
    sqlitedb = SQLiteVideoPlaybackStatsCacheDB.get_instance(db_exception_handler)   
    sqlite_db_path = os.path.join(config_dir, DB_DIR_NAME, DB_FILE_NAME)
    sqlitedb.initDB(sqlite_db_path, CREATE_VIDEOPLAYBACK_STATS_SQL_FILE,current_db_version=CURRENT_DB_VERSION)  # the first place to create db in Tribler
    return sqlitedb

class SQLiteVideoPlaybackStatsCacheDBV2(SQLiteCacheDBBase):
    def updateDB(self, fromver, tover):
        # convert database version 1 --> 2
        if fromver < 2:
            sql = """
-- Simplify the database. All info is now an event.

DROP TABLE IF EXISTS playback_info;
DROP INDEX IF EXISTS playback_info_idx;

-- Simplify the database. Events are simplified to key/value
-- pairs. Because sqlite is unable to remove a column, we are forced
-- to DROP and re-CREATE the event table.
--
-- Note that this will erase previous statistics... 

DROP TABLE IF EXISTS playback_event;
DROP INDEX IF EXISTS playback_event_idx;

CREATE TABLE playback_event (
  key                   text NOT NULL,
  timestamp             real NOT NULL,
  event                 text NOT NULL
);  

CREATE INDEX playback_event_idx 
  ON playback_event (key, timestamp);
"""

            self.execute_write(sql, commit=False)

        # updating version stepwise so if this works, we store it
        # regardless of later, potentially failing updates
        self.writeDBVersion(CURRENT_DB_VERSION, commit=False)
        self.commit()

class SQLiteVideoPlaybackStatsCacheDB(SQLiteVideoPlaybackStatsCacheDBV2):
    """
    Wrapper around Database engine. Used to perform raw SQL queries
    and ensure that Database schema is correct.
    """

    __single = None    # used for multithreaded singletons pattern
    lock = thread.allocate_lock()

    @classmethod
    def get_instance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()   
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kw)
            finally:
                cls.lock.release()
        return cls.__single
    
    def __init__(self, *args, **kw):
        # always use get_instance() to create this object
        if self.__single != None:
            raise RuntimeError, "SQLiteVideoPlaybackStatsCacheDB is singleton"
        SQLiteCacheDBBase.__init__(self, *args, **kw)
    
class VideoPlaybackDBHandler(BasicDBHandler):
    """
    Interface to add and retrieve events from the database.

    Manages the playback_event table. This table may contain several
    entries for events that occur during playback such as when it was
    started and when it was paused.

    The interface of this class should match that of
    VideoPlaybackReporter in Tribler.Player.Reporter which is used to
    report the same information through HTTP callbacks when there is
    no overlay network
    """

    __single = None    # used for multi-threaded singletons pattern
    lock = thread.allocate_lock()

    @classmethod
    def get_instance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()   
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kw)
            finally:
                cls.lock.release()
        return cls.__single
    
    def __init__(self):
        if VideoPlaybackDBHandler.__single is not None:
            raise RuntimeError, "VideoPlaybackDBHandler is singleton"
        BasicDBHandler.__init__(self, SQLiteVideoPlaybackStatsCacheDB.get_instance(), 'playback_event')
            
    def add_event(self, key, event):
        assert type(key) in (str, unicode)
        assert not "'" in key
        assert type(event) in (str, unicode)
        assert not "'" in event

        # because the key usually an infohash, and because this is
        # usually (and incorrectly) stored in a string instead of a
        # unicode string, this will crash the database wrapper.
        key = b64encode(key)

        if DEBUG: print >>sys.stderr, "VideoPlaybackDBHandler add_event", key, event
        self._db.execute_write("INSERT INTO %s (key, timestamp, event) VALUES ('%s', %s, '%s')" % (self.table_name, key, time(), event))

    def flush(self):
        """
        Flush the statistics. This is not used for database-based logging
        """
        pass
