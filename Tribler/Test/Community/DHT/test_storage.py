import time
import unittest

from Tribler.community.dht.storage import Storage


class TestStorage(unittest.TestCase):

    def test_get_and_put(self):
        storage = Storage()

        storage.put('key', 'value1')
        self.assertEqual(storage.get('key'), ['value1'])

        storage.put('key', 'value2')
        self.assertEqual(storage.get('key'), ['value2', 'value1'])

        storage.put('key', 'value1')
        self.assertEqual(storage.get('key'), ['value1', 'value2'])

    def test_items_older_than(self):
        storage = Storage()
        storage.put('key', 'value')
        storage.items['key'][0].last_update = time.time() - 1
        self.assertEqual(storage.items_older_than(0), [('key', 'value')])
        self.assertEqual(storage.items_older_than(10), [])

    def test_clean(self):
        storage = Storage()

        storage.put('key', 'value', max_age=60)
        storage.items['key'][0].last_update = time.time() - 120
        storage.clean()
        self.assertEqual(storage.get('key'), [])

        storage.put('key', 'value', 60)
        storage.items['key'][0].last_update = time.time()
        storage.clean()
        self.assertEqual(storage.get('key'), ['value'])
