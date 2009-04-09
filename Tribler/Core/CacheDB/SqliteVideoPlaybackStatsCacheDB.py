# Written by Boudewijn
# see LICENSE.txt for license information

"""
Database wrapper to add and retrieve Video playback statistics
"""

import sys
import os
import thread
from time import time

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDBBase
from Tribler.Core.CacheDB.SqliteCacheDBHandler import BasicDBHandler

CREATE_VIDEOPLAYBACK_STATS_SQL_FILE = None
CREATE_VIDEOPLAYBACK_STATS_SQL_FILE_POSTFIX = os.path.join(LIBRARYNAME, 'Core', 'Statistics', "tribler_videoplayback_stats.sql")
DB_FILE_NAME = 'tribler_videoplayback_stats.sdb'
DB_DIR_NAME = 'sqlite'    # db file path = DB_DIR_NAME/DB_FILE_NAME
CURRENT_DB_VERSION = 1

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

class SQLiteVideoPlaybackStatsCacheDB(SQLiteCacheDBBase):
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
    
class VideoPlaybackInfoDBHandler(BasicDBHandler):
    """
    Interface to add and retrieve info from database.

    Manages the playback_info table. This table contains one entry
    with info for each playback. This info contains things like:
    piecesize, nat/firewall status, etc.
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
        if VideoPlaybackInfoDBHandler.__single is not None:
            raise RuntimeError, "VideoPlaybackInfoDBHandler is singleton"
        BasicDBHandler.__init__(self, SQLiteVideoPlaybackStatsCacheDB.get_instance(), 'playback_info')

    def create_entry(self, key, piece_size=0, num_pieces=0, bitrate=0, nat="", unique=False):
        """
        Create an entry that can be updated using subsequent
        set_... calls.

        When UNIQUE we assume that KEY does not yet exist in the
        database. Otherwise a check is made.
        """
        assert type(key) is str, type(key)
        assert type(piece_size) is int, type(piece_size)
        assert type(num_pieces) is int, type(num_pieces)
        assert type(bitrate) in (int, float), type(bitrate)
        assert type(nat) is str, type(nat)
        if DEBUG: print >>sys.stderr, "SqliteVideoPlaybackStatsCacheDB create_entry", key
        if unique:
            self._db.execute_write("INSERT INTO %s (key, timestamp, piece_size, num_pieces, bitrate, nat) VALUES ('%s', %s, %d, %d, %d, '%s')" % (self.table_name, key, time(), piece_size, num_pieces, bitrate, nat))
            return True
        else:
            (count,) = self._db.execute_read("SELECT COUNT(*) FROM %s WHERE key = '%s'" % (self.table_name, key)).next()
            if count == 0:
                return self.create_entry(key, piece_size=piece_size, num_pieces=num_pieces, bitrate=bitrate, nat=nat, unique=True)
            else:
                return False
            
    def set_piecesize(self, key, piece_size):
        assert type(key) is str
        assert type(piece_size) is int
        if DEBUG: print >>sys.stderr, "SqliteVideoPlaybackStatsCacheDB set_piecesize", key, piece_size
        self._db.execute_write("UPDATE %s SET piece_size = %d WHERE key = '%s'" % (self.table_name, piece_size, key))

    def set_num_pieces(self, key, num_pieces):
        assert type(key) is str
        assert type(num_pieces) is int
        if DEBUG: print >>sys.stderr, "SqliteVideoPlaybackStatsCacheDB set_num_pieces", key, num_pieces
        self._db.execute_write("UPDATE %s SET num_pieces = %d WHERE key = '%s'" % (self.table_name, num_pieces, key))

    def set_bitrate(self, key, bitrate):
        assert type(key) is str
        assert type(bitrate) in (int, float)
        if DEBUG: print >>sys.stderr, "SqliteVideoPlaybackStatsCacheDB set_bitrate", key, bitrate
        self._db.execute_write("UPDATE %s SET bitrate = %d WHERE key = '%s'" % (self.table_name, bitrate, key))

    def set_nat(self, key, nat):
        assert type(key) is str
        assert type(nat) is str
        if DEBUG: print >>sys.stderr, "SqliteVideoPlaybackStatsCacheDB set_nat", key, nat
        self._db.execute_write("UPDATE %s SET nat = '%s' WHERE key = '%s'" % (self.table_name, nat, key))

class VideoPlaybackEventDBHandler(BasicDBHandler):
    """
    Interface to add and retrieve events from the database.

    Manages the playback_event table. This table may contain several
    entries for events that occur during playback such as when it was
    started and when it was paused.
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
        if VideoPlaybackEventDBHandler.__single is not None:
            raise RuntimeError, "VideoPlaybackEventDBHandler is singleton"
        BasicDBHandler.__init__(self, SQLiteVideoPlaybackStatsCacheDB.get_instance(), 'playback_event')
            
    def add_event(self, key, event, origin):
        assert type(key) is str
        assert type(event) is str
        assert type(origin) is str
        if DEBUG: print >>sys.stderr, "SqliteVideoPlaybackStatsCacheDB add_event", key, event, origin
        self._db.execute_write("INSERT INTO %s (key, timestamp, event, origin) VALUES ('%s', %s, '%s', '%s')" % (self.table_name, key, time(), event, origin))

        
