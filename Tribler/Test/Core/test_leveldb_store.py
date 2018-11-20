"""
Tests for the LevelDB.

Author(s): Elric Milon
"""
import os

from nose.tools import raises
from shutil import rmtree
from tempfile import mkdtemp
from twisted.internet.task import Clock

from Tribler.Core.leveldbstore import LevelDbStore, WRITEBACK_PERIOD, get_write_batch_leveldb
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import BaseTestCase


K = "foo"
V = "bar"


class ClockedAbstractLevelDBStore(LevelDbStore):
    _reactor = Clock()


class ClockedLevelDBStore(ClockedAbstractLevelDBStore):
    from leveldb import LevelDB
    _leveldb = LevelDB
    _writebatch = get_write_batch_leveldb


class AbstractTestLevelDBStore(BaseTestCase):

    skip = True
    _storetype = None

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
        self.store = self._storetype(self.store_dir)

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
    skip = False
    _storetype = ClockedLevelDBStore

    def test_invalid_handle(self):
        self.store.close()

        open(os.path.join(self.store_dir, 'test.txt'), 'a').close()

        # Make the leveldb files corrupt
        for dir_file in os.listdir(self.store_dir):
            with open(os.path.join(self.store_dir, dir_file), 'a') as file_handler:
                file_handler.write('abcde')

        self.openStore(self.store_dir)
        self.assertFalse(os.path.exists(os.path.join(self.store_dir, 'test.txt')))

    def test_flush(self):
        """ Tests if flush() does multiple retries incase of failure. """
        def mock_db_write(store, _):
            store.write_retry += 1
            raise Exception("SomeLevelDBError")

        self.store._db = MockObject()
        self.store._db.Write = lambda batch: mock_db_write(self.store, batch)

        self.store.write_retry = 0

        # No store operation yet, no write should be called on flush
        self.store.flush()
        self.assertEqual(self.store.write_retry, 0)

        # Store something and check if it is in cache
        self.store[K] = V
        self.assertIsNotNone(self.store._pending_torrents)
        # Now flush; Mock DB write through an exception so flush() should be tried 3 times
        self.store.flush()
        self.assertEqual(self.store.write_retry, 3, "Three retry to flush was expected incase of error")
