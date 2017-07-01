"""
Tests for the multichain database.
"""
import os

from datetime import datetime

from twisted.internet.defer import inlineCallbacks

from Tribler.community.trustchain.database import TrustChainDB, DATABASE_DIRECTORY
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.Community.Trustchain.test_trustchain_utilities import TestBlock, TrustChainTestCase


class TestDatabase(TrustChainTestCase):
    """
    Tests the Database for TrustChain community.
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
        self.db = TrustChainDB(self.getStateDir(), u'trustchain')

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
    def test_get_upgrade_script(self):
        self.assertIsNone(self.db.get_upgrade_script(42))

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
        self.block2 = TestBlock.create({"id": 42}, self.db, self.block2.public_key, link=self.block1)
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        result = self.db.get_linked(self.block1)

        self.assertEqual_block(self.block2, result)

    @blocking_call_on_reactor_thread
    def test_get_linked_backwards(self):
        """
        Backward linked blocks should be retrievable form the database.
        """
        self.block2 = TestBlock.create({"id": 42}, self.db, self.block2.public_key, link=self.block1)

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
        self.db = TrustChainDB(self.getStateDir(), u'trustchain')

    @blocking_call_on_reactor_thread
    def test_database_upgrade(self):
        """
        Set the database version to a newer version before upgrading.
        """
        self.set_db_version(1)
        version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        self.assertEqual(version, u"1")

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
        self.assertDictEqual(block_dict["transaction"], {"id": 42})
        self.assertEqual(block_dict["insert_time"], self.block1.insert_time)
