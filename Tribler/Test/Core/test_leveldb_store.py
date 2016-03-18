# test_torrent_store.py ---
#
# Filename: test_leveldb_store.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Wed Jan 21 12:45:30 2015 (+0100)

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
from nose.tools import raises

from shutil import rmtree
from tempfile import mkdtemp

from twisted.internet.task import Clock

from Tribler.Core.leveldbstore import LevelDbStore, WRITEBACK_PERIOD, get_write_batch_plyvel, get_write_batch_leveldb
from Tribler.Test.test_as_server import BaseTestCase


K = "foo"
V = "bar"


class ClockedAbstractLevelDBStore(LevelDbStore):
    _reactor = Clock()


class ClockedLevelDBStore(ClockedAbstractLevelDBStore):
    from leveldb import LevelDB
    _leveldb = LevelDB
    _writebatch = get_write_batch_leveldb


class ClockedPlyvelStore(ClockedAbstractLevelDBStore):
    from Tribler.Core.plyveladapter import LevelDB
    _leveldb = LevelDB
    _writebatch = get_write_batch_plyvel


class AbstractTestLevelDBStore(BaseTestCase):

    __test__ = False

    def __init__(self, *argv, **kwargs):
        super(AbstractTestLevelDBStore, self).__init__(*argv, **kwargs)

        self.store_dir = None
        self.store = None

    def setUp(self):
        self.openStore(mkdtemp(prefix=__name__))

    def tearDown(self):
        self.closeStore()

    def closeStore(self):
        self.store.close()
        rmtree(self.store_dir)
        self.store = None

    def openStore(self, store_dir):
        self.store_dir = store_dir
        self.store = None

    def test_storeIsPersistent(self):
        self.store.put(K, V)
        self.assertEqual(self.store.get(K), V)
        store_dir = self.store._store_dir
        self.store.close()
        self.openStore(store_dir)
        self.assertEqual(self.store.get(K), V)

    def test_canPutAndDelete(self):
        self.store[K] = V
        self.assertEqual(self.store[K], V)
        del self.store[K]
        self.assertEqual(None, self.store.get(K))
        with self.assertRaises(KeyError) as raises:
            self.store[K]

    def test_PutGet(self):
        self.store._db.Put(K, V)
        self.assertEqual(V, self.store._db.Get(K))

    def test_cacheIsFlushed(self):
        self.store[K] = V
        self.assertEqual(1, len(self.store._pending_torrents))
        self.store._reactor.advance(WRITEBACK_PERIOD)
        self.assertEqual(0, len(self.store._pending_torrents))

    def test_len(self):
        self.assertEqual(0, len(self.store))
        self.store[K] = V
        self.assertEqual(1, len(self.store), 1)
        # test that even after writing the cached data, the lenght is still the same
        self.store.flush()
        self.assertEqual(1, len(self.store), 2)

    def test_contains(self):
        self.assertFalse(K in self.store)
        self.store[K] = V
        self.assertTrue(K in self.store)

    @raises(StopIteration)
    def test_iter_empty(self):
        iteritems = self.store.iteritems()
        self.assertTrue(iteritems.next())

    def test_iter_one_element(self):
        self.store[K] = V
        iteritems = self.store.iteritems()
        self.assertEqual(iteritems.next(), K)

    def test_iter(self):
        self.store[K] = V
        for key in iter(self.store):
            self.assertTrue(key)


class TestLevelDBStore(AbstractTestLevelDBStore):
    __test__ = True

    def openStore(self, store_dir):
        self.store_dir = store_dir
        self.store = ClockedLevelDBStore(self.store_dir)


class TestPlyvelStore(AbstractTestLevelDBStore):
    __test__ = True

    def openStore(self, store_dir):
        self.store_dir = store_dir
        self.store = ClockedPlyvelStore(self.store_dir)

#
# test_leveldb_store.py ends here
