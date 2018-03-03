import unittest

from Tribler.community.allchannel2.structures import Chunk, ChunkedTable


class TestChunk(unittest.TestCase):

    def setUp(self):
        self.chunk = Chunk()

    def test_empty(self):
        """
        Test if a Chunk is initially empty.
        """
        self.assertDictEqual(self.chunk.data, {})

    def test_add(self):
        """
        Test if we can add a key value pair to the Chunk.
        """
        self.assertTrue(self.chunk.add("key", "value"))
        self.assertDictEqual(self.chunk.data, {"key": "value"})

    def test_remove(self):
        """
        Test if we can remove a key value pair from the Chunk.
        """
        self.assertTrue(self.chunk.add("key", "value"))
        self.chunk.remove("key")
        self.assertDictEqual(self.chunk.data, {})

    def test_add_full(self):
        """
        Test if we cannot add blocks to an already full Chunk.
        """
        self.chunk.max_length = 0
        self.assertFalse(self.chunk.add("key", "value"))

    def test_serialize_empty(self):
        """
        Test if we can serialize and deserialize an empty Chunk.
        """
        data = self.chunk.serialize()
        chunk = Chunk.unserialize(data)
        self.assertDictEqual(self.chunk.data, chunk.data)

    def test_serialize(self):
        """
        Test if we can serialize and deserialize a Chunk.
        """
        self.chunk.data = {"key": "value"}
        data = self.chunk.serialize()
        chunk = Chunk.unserialize(data)
        self.assertDictEqual(self.chunk.data, chunk.data)


class TestChunkedTable(unittest.TestCase):

    def setUp(self):
        self.chunked_table = ChunkedTable()

    def test_empty(self):
        """
        Test if a ChunkedTable is initially empty.
        """
        self.assertDictEqual(self.chunked_table.chunklist, {})

    def test_add(self):
        """
        Test if we can add a key value pair to the ChunkedTable.
        """
        self.chunked_table.add("key", "value")
        self.assertEqual(len(self.chunked_table.chunklist.keys()), 1)
        self.assertDictEqual(self.chunked_table.get_all(), {"key": "value"})

    def test_add_second(self):
        """
        Test if we can add a key value pair to the ChunkedTable in an existing Chunk.
        """
        self.chunked_table.add("key", "value")
        self.chunked_table.add("key2", "value2")
        self.assertEqual(len(self.chunked_table.chunklist.keys()), 1)
        self.assertDictEqual(self.chunked_table.get_all(), {"key": "value", "key2": "value2"})

    def test_add_second_spill(self):
        """
        Test if we can add a key value pair to the ChunkedTable if the existing Chunk is full.
        """
        self.chunked_table.add("key", "value")
        self.chunked_table.chunklist.values()[0].max_length = 0
        self.chunked_table.add("key2", "value2")
        self.assertEqual(len(self.chunked_table.chunklist.keys()), 2)
        self.assertDictEqual(self.chunked_table.get_all(), {"key": "value", "key2": "value2"})

    def test_remove(self):
        """
        Test if we can remove a key value pair from the ChunkedTable.
        """
        self.chunked_table.add("key", "value")
        self.chunked_table.remove("key")
        self.assertEqual(len(self.chunked_table.chunklist.keys()), 0)
        self.assertDictEqual(self.chunked_table.get_all(), {})

    def test_remove_hole(self):
        """
        Test if we do not remove middle Chunks in the ChunkTable.
        """
        fake_chunklist = {0: Chunk(), 1:Chunk(), 2:Chunk()}
        fake_chunklist[0].add("key0", "value0")
        fake_chunklist[1].add("key1", "value1")
        fake_chunklist[2].add("key2", "value2")
        self.chunked_table.chunklist = fake_chunklist
        self.chunked_table.remove("key1")
        self.assertEqual(len(self.chunked_table.chunklist.keys()), 3)
        self.assertDictEqual(self.chunked_table.get_all(), {"key0": "value0", "key2": "value2"})

    def test_remove_hole_recover(self):
        """
        Test if we remove all trailing empty Chunks in the ChunkTable.
        """
        fake_chunklist = {0: Chunk(), 1:Chunk(), 2:Chunk()}
        fake_chunklist[0].add("key0", "value0")
        fake_chunklist[2].add("key2", "value2")
        self.chunked_table.chunklist = fake_chunklist
        self.chunked_table.remove("key2")
        self.assertEqual(len(self.chunked_table.chunklist.keys()), 1)
        self.assertDictEqual(self.chunked_table.get_all(), {"key0": "value0"})

    def test_serialize_empty(self):
        """
        Test if we can serialize and deserialize an empty ChunkedTable.
        """
        data = self.chunked_table.serialize()
        chunked_table = ChunkedTable.unserialize(data)
        self.assertDictEqual(self.chunked_table.get_all(), chunked_table.get_all())

    def test_serialize(self):
        """
        Test if we can serialize and deserialize a ChunkedTable.
        """
        self.chunked_table.add("key", "value")
        data = self.chunked_table.serialize()
        chunked_table = ChunkedTable.unserialize(data)
        self.assertDictEqual(self.chunked_table.get_all(), chunked_table.get_all())
