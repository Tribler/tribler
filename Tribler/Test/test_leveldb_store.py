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
from Tribler.Core.Utilities.twisted_thread import deferred, reactor

from shutil import rmtree
from tempfile import mkdtemp

from twisted.internet.task import Clock

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.leveldbstore import LevelDbStore, WRITEBACK_PERIOD
from Tribler.Test.test_as_server import BaseTestCase


K = "foo"
V = "bar"


class ClockedLevelDbStore(LevelDbStore):
    _reactor = Clock()


class TestLevelDbStore(BaseTestCase):

    def __init__(self, *argv, **kwargs):
        super(TestLevelDbStore, self).__init__(*argv, **kwargs)

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
        self.store = ClockedLevelDbStore(store_dir=self.store_dir)


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

#
# test_leveldb_store.py ends here
