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

try:
    raise ImportError("Fake import error")
    from leveldb import LevelDB, WriteBatch
    LEVELDBPROVIDER = "leveldb"
except:
    import plyvel
    LEVELDBPROVIDER = "plyvel"
from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.dispersy.taskmanager import TaskManager


WRITEBACK_PERIOD = 120

# TODO(emilon): This could be easily abstracted into a generic cached store
# TODO(emilon): Make sure the caching makes an actual difference in IO and kill
# it if it doesn't as it complicates the code.


class TorrentStore(MutableMapping, TaskManager):
    _reactor = reactor

    def __init__(self, store_dir):
        super(TorrentStore, self).__init__()

        self._store_dir = store_dir
        self._pending_torrents = {}

        if LEVELDBPROVIDER == "leveldb":
            self._db = LevelDB(store_dir)
        elif LEVELDBPROVIDER == "plyvel":
            self._db = plyvel.DB(store_dir, create_if_missing = True)

        self._writeback_lc = self.register_task("flush cache ", LoopingCall(self.flush))
        self._writeback_lc.clock = self._reactor
        self._writeback_lc.start(WRITEBACK_PERIOD)


    if LEVELDBPROVIDER == "leveldb":
        def __getitem__(self, key):
            try:
                return self._pending_torrents[key]
            except KeyError:
                return self._db.Get(key)
    elif LEVELDBPROVIDER == "plyvel":
        def __getitem__(self, key):
            try:
                return self._pending_torrents[key]
            except KeyError:
                res = self._db.get(key)
                if res == None:
                    raise KeyError("Key not found")
                return res

    def __setitem__(self, key, value):
        self._pending_torrents[key] = value

    if LEVELDBPROVIDER == "leveldb":
        def __delitem__(self, key):
            if key in self._pending_torrents:
                self._pending_torrents.pop(key)
            self._db.Delete(key)
    elif LEVELDBPROVIDER == "plyvel":
        def __delitem__(self, key):
            if key in self._pending_torrents:
                self._pending_torrents.pop(key)
            self._db.delete(key)

    def __iter__(self):
        for k in self._pending_torrents.iterkeys():
            yield k
        for k, _ in rangescan():
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
        return [k for k, _ in rangescan()]

    def iteritems(self):
        return chain(self._pending_torrents, rangescan())

    def put(self, k, v):
        self.__setitem__(k, v)

    if LEVELDBPROVIDER == "leveldb":
        def rangescan(self, start=None, end=None):
            if start is None and end is None:
                return self._db.RangeIter()
            elif end is None:
                return self._db.RangeIter(start)
            else:
                return self._db.RangeIter(start, end)
    elif LEVELDBPROVIDER == "plyvel":
        def rangescan(self, start=None, end=None):
            return self._db.iterator(start=start, end=end)

    if LEVELDBPROVIDER == "leveldb":
        def flush(self):
            if self._pending_torrents:
                write_batch = WriteBatch()
                for k, v in self._pending_torrents.iteritems():
                    write_batch.Put(k, v)
                self._pending_torrents.clear()
                return self._db.Write(write_batch)
    elif LEVELDBPROVIDER == "plyvel":
        def flush(self):
            with self._db.write_batch() as wb:
                for k, v in self._pending_torrents.iteritems():
                    wb.put(k, v)

    def close(self):
        self.cancel_all_pending_tasks()
        self.flush()
        if LEVELDBPROVIDER == "plyvel":
            self._db.close()
        self._db = None


#
# torrentstore.py ends here
