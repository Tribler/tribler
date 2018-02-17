"""
LevelDBStore.

Author(s): Elric Milon
"""
import os
from collections import MutableMapping
from itertools import chain

from shutil import rmtree

import logging

import sys


def get_write_batch_leveldb(self, _):
    from leveldb import WriteBatch
    return WriteBatch()


def get_write_batch_plyvel(self, db):
    from plyveladapter import WriteBatch
    return WriteBatch(db)

try:
    from leveldb import LevelDB, LevelDBError

    use_leveldb = True
    get_write_batch = get_write_batch_leveldb

except ImportError:
    from plyveladapter import LevelDB

    use_leveldb = False
    get_write_batch = get_write_batch_plyvel

from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.dispersy.taskmanager import TaskManager


WRITEBACK_PERIOD = 120

# TODO(emilon): Make sure the caching makes an actual difference in IO and kill
# it if it doesn't as it complicates the code.


class LevelDbStore(MutableMapping, TaskManager):
    _reactor = reactor
    _leveldb = LevelDB
    _writebatch = get_write_batch

    def __init__(self, store_dir):
        super(LevelDbStore, self).__init__()

        self._store_dir = store_dir
        self._pending_torrents = {}
        self._logger = logging.getLogger(self.__class__.__name__)
        # This is done to work around LevelDB's inability to deal with non-ascii paths on windows.
        try:
            db_path = store_dir.decode('windows-1252') if sys.platform == "win32" else store_dir
            self._db = self._leveldb(db_path)
        except ValueError:
            # This can happen on Windows when the state dir and Tribler installation are on different disks.
            # In this case, hope for the best by using the full path.
            self._db = self._leveldb(store_dir)
        except Exception as exc:
            # We cannot simply catch LevelDBError since that class might not be available on some systems.
            if use_leveldb and isinstance(exc, LevelDBError):
                # The database might be corrupt, start with a fresh one
                self._logger.error("Corrupt LevelDB store detected; recreating database")
                rmtree(self._store_dir)
                os.makedirs(self._store_dir)
                self._db = self._leveldb(os.path.relpath(store_dir, os.getcwdu()))
            else:  # If something else goes wrong, we throw the exception again
                raise

        self._writeback_lc = self.register_task("flush cache ", LoopingCall(self.flush))
        self._writeback_lc.clock = self._reactor
        self._writeback_lc.start(WRITEBACK_PERIOD)

    def get_db(self):
        return self._db

    def __getitem__(self, key):
        try:
            return self._pending_torrents[key]
        except KeyError:
            return self._db.Get(key)

    def __setitem__(self, key, value):
        self._pending_torrents[key] = value

    def __delitem__(self, key):
        if key in self._pending_torrents:
            self._pending_torrents.pop(key)
        self._db.Delete(key)

    def __iter__(self):
        for k in self._pending_torrents.iterkeys():
            yield k
        for k, _ in self._db.RangeIter():
            yield k

    def __contains__(self, key):
        if key in self._pending_torrents:
            return True
        try:
            self.__getitem__(key)
            return True
        except KeyError:
            pass

        return False

    def __len__(self):
        return len(self._pending_torrents) + len(list(self.keys()))

    def keys(self):
        return [k for k, _ in self._db.RangeIter()]

    def iteritems(self):
        return chain(self._pending_torrents, self._db.RangeIter())

    def put(self, k, v):
        self.__setitem__(k, v)

    def rangescan(self, start=None, end=None):
        if start is None and end is None:
            return self._db.RangeIter()
        elif end is None:
            return self._db.RangeIter(key_from=start)
        else:
            return self._db.RangeIter(key_from=start, key_to=end)

    def flush(self):
        if self._pending_torrents:
            write_batch = self._writebatch(self._db)
            for k, v in self._pending_torrents.iteritems():
                write_batch.Put(k, v)
            self._pending_torrents.clear()
            return self._db.Write(write_batch)

    def close(self):
        self.cancel_all_pending_tasks()
        self.flush()
        self._db = None
