"""
Tests for the multichain database.
"""
import os
from datetime import datetime

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.Multichain.test_multichain_utilities import TestBlock, MultiChainTestCase
from Tribler.community.multichain.database import MultiChainDB, DATABASE_DIRECTORY
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestDatabase(MultiChainTestCase):
    """
    Tests the Database for MultiChain community.
    """
    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        """
        Create a state directory, the database and some test blocks.
        """
        yield super(TestDatabase, self).setUp(annotate=annotate)
        path = os.path.join(self.getStateDir(), DATABASE_DIRECTORY)
        if not os.path.exists(path):
            os.makedirs(path)

        self.db = MultiChainDB(self.getStateDir())
        self.block1 = TestBlock()
        self.block2 = TestBlock()
        self.block3 = TestBlock()

    @blocking_call_on_reactor_thread
    def test_add_block(self):
        """
        When adding a block the last block added should be this block.
        """
        self.db.add_block(self.block1)
        result = self.db.get_latest(self.block1.public_key)

        self.assertEqual_block(self.block1, result)

    @blocking_call_on_reactor_thread
    def test_get_num_interactors(self):
        """
        The right number of interactors should be returned.
        """
        self.block2 = TestBlock(previous=self.block1)
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)

        self.assertEqual((2, 2), self.db.get_num_unique_interactors(self.block1.public_key))

    @blocking_call_on_reactor_thread
    def test_add_two_blocks(self):
        """
        Add multiple blocks consecutively.
        """
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        result = self.db.get_latest(self.block2.public_key)

        self.assertEqual_block(self.block2, result)

    @blocking_call_on_reactor_thread
    def test_get_block_non_existing(self):
        """
        Attempt to retrieve a nonexistent block.
        """
        result = self.db.get_latest(self.block1.public_key)

        self.assertEqual(None, result)

    @blocking_call_on_reactor_thread
    def test_contains_block_id_positive(self):
        """
        An added block should be contained in the database.
        """
        self.db.add_block(self.block1)

        self.assertTrue(self.db.contains(self.block1))

    @blocking_call_on_reactor_thread
    def test_contains_block_id_negative(self):
        """
        A block not added to the database should not be contained in the database.
        """
        self.assertFalse(self.db.contains(self.block1))

    @blocking_call_on_reactor_thread
    def test_get_linked_forward(self):
        """
        Forwardly linked blocks should be retrievable from the database.
        """
        self.block2 = TestBlock.create(self.db, self.block2.public_key, link=self.block1)
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        result = self.db.get_linked(self.block1)

        self.assertEqual_block(self.block2, result)

    @blocking_call_on_reactor_thread
    def test_get_linked_backwards(self):
        """
        Backward linked blocks should be retrievable form the database.
        """
        self.block2 = TestBlock.create(self.db, self.block2.public_key, link=self.block1)
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        result = self.db.get_linked(self.block2)

        self.assertEqual_block(self.block1, result)

    @blocking_call_on_reactor_thread
    def test_get_block_after(self):
        """
        Retrieve the block created after another block.
        """
        self.block2.public_key = self.block1.public_key
        self.block2.sequence_number = self.block1.sequence_number + 1

        block3 = TestBlock()
        block3.public_key = self.block2.public_key
        block3.sequence_number = self.block2.sequence_number + 10

        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        self.db.add_block(block3)

        result = self.db.get_block_after(self.block2)

        self.assertEqual_block(block3, result)

    @blocking_call_on_reactor_thread
    def test_get_block_before(self):
        """
        Retrieve the block which is created before another block.
        """
        self.block2.public_key = self.block1.public_key
        self.block2.sequence_number = self.block1.sequence_number + 1

        block3 = TestBlock()
        block3.public_key = self.block2.public_key
        block3.sequence_number = self.block2.sequence_number + 10

        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        self.db.add_block(block3)

        result = self.db.get_block_before(self.block2)

        self.assertEqual_block(self.block1, result)

    @blocking_call_on_reactor_thread
    def test_save_large_upload_download_block(self):
        """
        A block can save very large numbers.
        """
        self.block1.total_up = pow(2, 62)
        self.block1.total_down = pow(2, 62)
        self.db.add_block(self.block1)
        result = self.db.get_latest(self.block1.public_key)

        self.assertEqual_block(self.block1, result)

    @blocking_call_on_reactor_thread
    def test_get_insert_time(self):
        """
        When a block is inserted into the database, a timestamp of the current time will get added.
        """
        self.db.add_block(self.block1)

        result = self.db.get_latest(self.block1.public_key)

        insert_time = datetime.strptime(result.insert_time, "%Y-%m-%d %H:%M:%S")

        time_difference = datetime.utcnow() - insert_time

        self.assertEqual(time_difference.days, 0)
        self.assertLess(time_difference.seconds, 10,
                        "Difference in stored and retrieved time is too large.")

    @blocking_call_on_reactor_thread
    def set_db_version(self, version):
        """
        Update the version of the database.

        :param version: the new version
        """
        self.db.executescript(u"UPDATE option SET value = '%d' WHERE key = 'database_version';" % version)
        self.db.close(commit=True)
        self.db = MultiChainDB(self.getStateDir())

    @blocking_call_on_reactor_thread
    def test_database_upgrade(self):
        """
        Set the database version to a newer version before upgrading.
        """
        self.set_db_version(1)
        version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        self.assertEqual(version, u"3")

    @blocking_call_on_reactor_thread
    def test_database_create(self):
        """
        Set the database version to a nonexistent version before upgrading.
        """
        self.set_db_version(0)
        version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        self.assertEqual(version, u"3")

    @blocking_call_on_reactor_thread
    def test_database_no_downgrade(self):
        """
        Set the database version to a high version to prevent upgrading.
        """
        self.set_db_version(200000)
        version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        self.assertEqual(version, u"200000")

    @blocking_call_on_reactor_thread
    def test_block_to_dictionary(self):
        """
        Test whether a block is correctly represented when converted to a dictionary.
        """
        block_dict = dict(self.block1)
        self.assertEqual(block_dict["up"], self.block1.up)
        self.assertEqual(block_dict["down"], self.block1.down)
        self.assertEqual(block_dict["insert_time"], self.block1.insert_time)

    @blocking_call_on_reactor_thread
    def test_total_up(self):
        """
        The database should return the correct amount of uploaded data.
        """
        self.block2.total_up = 0

        self.db.add_block(self.block1)
        self.db.add_block(self.block2)

        self.assertEqual(self.block1.total_up, self.db.total_up(self.block1.public_key))
        self.assertEqual(0, self.db.total_up(self.block2.public_key))
        self.assertEqual(0, self.db.total_up(self.block3.public_key))

    @blocking_call_on_reactor_thread
    def test_total_down(self):
        """
        The database should return the correct amount of downloaded data.
        """
        self.block2.total_down = 0

        self.db.add_block(self.block1)
        self.db.add_block(self.block2)

        self.assertEqual(self.block2.total_down, self.db.total_down(self.block2.public_key))
        self.assertEqual(0, self.db.total_down(self.block2.public_key))
        self.assertEqual(0, self.db.total_down(self.block3.public_key))

    @blocking_call_on_reactor_thread
    def test_neighbors(self):
        """
        The database should return the correct list of neighbors and the traffic to and from them.
        """
        focus_block1 = TestBlock()
        focus_block2 = TestBlock()

        # All blocks have the same public key
        self.block2.public_key = self.block1.public_key
        self.block3.public_key = self.block1.public_key

        self.block1.link_public_key = focus_block1.public_key
        self.block2.link_public_key = focus_block1.public_key
        self.block3.link_public_key = focus_block2.public_key

        # Add all blocks + one redundant block
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        self.db.add_block(self.block3)
        self.db.add_block(focus_block1)

        expected_result = {focus_block1.public_key:
                           {"up": self.block1.up + self.block2.up, "down": self.block1.down + self.block2.down},
                           focus_block2.public_key: {"up": self.block3.up, "down": self.block3.down}}

        self.assertDictEqual(expected_result, self.db.neighbor_list(self.block1.public_key))

    @blocking_call_on_reactor_thread
    def test_random_dummy_data(self):
        """
        The database should contain 104 rows when random dummy data is used.
        """
        self.db.use_dummy_data(use_random=True)

        num_rows = self.db.execute(u"SELECT count (*) FROM multi_chain").fetchone()[0]
        self.assertEqual(num_rows, 104)
        self.assertTrue(self.db.dummy_setup)

    @blocking_call_on_reactor_thread
    def test_static_dummy_data(self):
        """
        The database should contain the fixed data set when non-random dummy data is used.
        """
        self.db.use_dummy_data(use_random=False)

        num_rows = self.db.execute(u"SELECT count (*) FROM multi_chain").fetchone()[0]
        self.assertEqual(num_rows, 56)
        self.assertTrue(self.db.dummy_setup)

    @blocking_call_on_reactor_thread
    def test_no_dummy_overwrite(self):
        """
        The database should not overwrite the dataset once it has changed to dummy data.
        """
        self.db.use_dummy_data(use_random=True)

        focus_neighbors = self.db.neighbor_list("0")
        num_rows = self.db.execute(u"SELECT count (*) FROM multi_chain").fetchone()[0]
        self.assertEqual(num_rows, 104)
        self.assertTrue(self.db.dummy_setup)

        # Database stays the same when trying to setup static data
        self.db.use_dummy_data(use_random=False)
        self.assertEqual(num_rows, 104)
        self.assertTrue(self.db.dummy_setup)

        # Database does not overwrite random data on second call
        self.db.use_dummy_data(use_random=True)
        self.assertEqual(num_rows, 104)
        self.assertTrue(self.db.dummy_setup)
        self.assertDictEqual(focus_neighbors, self.db.neighbor_list("0"))
