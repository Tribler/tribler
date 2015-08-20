# torrentstore.py ---
#
# Filename: torrentstore.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Wed Jan 21 14:22:08 2015 (+0100)

# Commentary:
#
#
#
#

# Change Log:
#
#
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
#
#

# Code:
from collections import MutableMapping
from itertools import chain
import sys

try:
    from leveldb import LevelDB, WriteBatch

    def get_write_batch(_):
        return WriteBatch()

except ImportError:
    from plyveladapter import LevelDB, WriteBatch

    def get_write_batch(db):
        return WriteBatch(db)

from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.dispersy.taskmanager import TaskManager


WRITEBACK_PERIOD = 120

# TODO(emilon): Make sure the caching makes an actual difference in IO and kill
# it if it doesn't as it complicates the code.


class LevelDbStore(MutableMapping, TaskManager):
    _reactor = reactor
    _leveldb = LevelDB

    def __init__(self, store_dir):
        super(LevelDbStore, self).__init__()

        self._store_dir = store_dir
        self._pending_torrents = {}
        self._db = self._leveldb(store_dir.encode(sys.getfilesystemencoding()))

        self._writeback_lc = self.register_task("flush cache ", LoopingCall(self.flush))
        self._writeback_lc.clock = self._reactor
        self._writeback_lc.start(WRITEBACK_PERIOD)

    def __getitem__(self, key):
        try:
            return self._pending_torrents[key]
        except KeyError:
            return self._db.Get(key)

    def __setitem__(self, key, value):
        self._pending_torrents[key] = value
        # self._db.Put(key, value)

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
            write_batch = get_write_batch(self._db)
            for k, v in self._pending_torrents.iteritems():
                write_batch.Put(k, v)
            self._pending_torrents.clear()
            return self._db.Write(write_batch)

    def close(self):
        self.cancel_all_pending_tasks()
        self.flush()
        self._db = None


#
# torrentstore.py ends here
