import time
import unittest

from Tribler.community.dht.storage import Storage


class TestStorage(unittest.TestCase):

    def test_get_and_put(self):
        storage = Storage()

        storage.put('key', 'value1', 60)
        self.assertEqual(storage.get('key'), ['value1'])

        storage.put('key', 'value2', 60)
        self.assertEqual(storage.get('key'), ['value1', 'value2'])

        storage.put('key', 'value1', 60)
        self.assertEqual(storage.get('key'), ['value2', 'value1'])

    def test_items_older_than(self):
        storage = Storage()

        storage.data['key'].append((time.time() - 1, 60, 'value1'))
        self.assertEqual(storage.items_older_than(0), [('key', 'value1')])
        self.assertEqual(storage.items_older_than(10), [])

    def test_clean(self):
        storage = Storage()

        storage.data['key'] = [(time.time() - 120, 60, 'value1')]
        storage.clean()
        self.assertEqual(storage.get('key'), [])

        storage.data['key'] = [(time.time(), 60, 'value1')]
        storage.clean()
        self.assertEqual(storage.get('key'), ['value1'])
