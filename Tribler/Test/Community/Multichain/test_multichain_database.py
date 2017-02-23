import datetime
import os
from math import pow
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.Multichain.test_multichain_utilities import TestBlock, MultiChainTestCase
from Tribler.community.multichain.database import MultiChainDB
from Tribler.community.multichain.database import DATABASE_DIRECTORY
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestDatabase(MultiChainTestCase):
    """
    Tests the Database for MultiChain community.
    Also tests integration with Dispersy.
    This integration slows down the tests,
    but can probably be removed and a Mock Dispersy could be used.
    """

    def __init__(self, *args, **kwargs):
        super(TestDatabase, self).__init__(*args, **kwargs)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, **kwargs):
        yield super(TestDatabase, self).setUp()
        path = os.path.join(self.getStateDir(), DATABASE_DIRECTORY)
        if not os.path.exists(path):
            os.makedirs(path)
        self.db = MultiChainDB(None, self.getStateDir())
        self.block1 = TestBlock()
        self.block2 = TestBlock()

    @blocking_call_on_reactor_thread
    def test_add_block(self):
        # Act
        self.db.add_block(self.block1)
        # Assert
        result = self.db.get_by_hash_requester(self.block1.hash_requester)
        self.assertEqual_block(self.block1, result)

    @blocking_call_on_reactor_thread
    def test_get_blocks(self):
        """
        Test whether the right blocks are returned when fetching blocks
        """
        self.db.add_block(self.block1)
        self.assertEqual(len(self.db.get_blocks(self.block1.public_key_requester)), 1)
        self.block1.hash_requester = "a" * 40
        self.db.add_block(self.block1)
        self.assertEqual(len(self.db.get_blocks(self.block1.public_key_requester)), 2)
        self.assertEqual(len(self.db.get_blocks(self.block1.public_key_requester, limit=1)), 1)

    @blocking_call_on_reactor_thread
    def test_get_num_interactors(self):
        """
        Test whether the right number of interactors is returned
        """
        crypto = ECCrypto()
        my_key = crypto.key_to_bin(crypto.generate_key(u"curve25519").pub())
        block1 = TestBlock()
        block1.public_key_requester = my_key
        block1.up = 100
        block1.down = 100
        self.db.add_block(block1)

        block2 = TestBlock()
        block2.public_key_responder = my_key
        block2.up = 100
        block2.down = 100
        self.db.add_block(block2)

        self.assertEqual((2, 2), self.db.get_num_unique_interactors(my_key))

    @blocking_call_on_reactor_thread
    def test_get_by_hash(self):
        # Act
        self.db.add_block(self.block1)
        # Assert
        result1 = self.db.get_by_hash_requester(self.block1.hash_requester)
        result2 = self.db.get_by_hash(self.block1.hash_requester)
        result3 = self.db.get_by_hash(self.block1.hash_responder)
        self.assertEqual_block(self.block1, result1)
        self.assertEqual_block(self.block1, result2)
        self.assertEqual_block(self.block1, result3)

    @blocking_call_on_reactor_thread
    def test_add_two_blocks(self):
        # Act
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        # Assert
        result = self.db.get_by_hash_requester(self.block2.hash_requester)
        self.assertEqual_block(self.block2, result)

    @blocking_call_on_reactor_thread
    def test_get_block_non_existing(self):
        # Act
        result = self.db.get_by_hash_requester(self.block1.hash_requester)
        # Assert
        self.assertEqual(None, result)

    @blocking_call_on_reactor_thread
    def test_contains_block_id_positive(self):
        # Act
        self.db.add_block(self.block1)
        # Assert
        self.assertTrue(self.db.contains(self.block1.hash_requester))

    @blocking_call_on_reactor_thread
    def test_contains_block_id_negative(self):
        # Act & Assert
        self.assertFalse(self.db.contains("NON EXISTING ID"))

    @blocking_call_on_reactor_thread
    def test_get_latest_sequence_number_not_existing(self):
        # Act & Assert
        self.assertEquals(self.db.get_latest_sequence_number("NON EXISTING KEY"), -1)

    @blocking_call_on_reactor_thread
    def test_get_latest_sequence_number_public_key_requester(self):
        # Arrange
        # Make sure that there is a responder block with a lower sequence number.
        # To test that it will look for both responder and requester.
        self.db.add_block(self.block1)
        self.block2.public_key_responder = self.block1.public_key_requester
        self.block2.sequence_number_responder = self.block1.sequence_number_requester - 5
        self.db.add_block(self.block2)
        # Act & Assert
        self.assertEquals(self.db.get_latest_sequence_number(self.block1.public_key_requester),
                          self.block1.sequence_number_requester)

    @blocking_call_on_reactor_thread
    def test_get_latest_sequence_number_public_key_responder(self):
        # Arrange
        # Make sure that there is a requester block with a lower sequence number.
        # To test that it will look for both responder and requester.
        self.db.add_block(self.block1)
        self.block2.public_key_requester = self.block1.public_key_responder
        self.block2.sequence_number_requester = self.block1.sequence_number_responder - 5
        self.db.add_block(self.block2)
        # Act & Assert
        self.assertEquals(self.db.get_latest_sequence_number(self.block1.public_key_responder),
                          self.block1.sequence_number_responder)

    @blocking_call_on_reactor_thread
    def test_get_previous_id_not_existing(self):
        # Act & Assert
        self.assertEquals(self.db.get_latest_hash("NON EXISTING KEY"), None)

    @blocking_call_on_reactor_thread
    def test_get_previous_hash_of_requester(self):
        # Arrange
        # Make sure that there is a responder block with a lower sequence number.
        # To test that it will look for both responder and requester.
        self.db.add_block(self.block1)
        self.block2.public_key_responder = self.block1.public_key_requester
        self.block2.sequence_number_responder = self.block1.sequence_number_requester + 1
        self.db.add_block(self.block2)
        # Act & Assert
        self.assertEquals(self.db.get_latest_hash(self.block2.public_key_responder), self.block2.hash_responder)

    @blocking_call_on_reactor_thread
    def test_get_previous_hash_of_responder(self):
        # Arrange
        # Make sure that there is a requester block with a lower sequence number.
        # To test that it will look for both responder and requester.
        self.db.add_block(self.block1)
        self.block2.public_key_requester = self.block1.public_key_responder
        self.block2.sequence_number_requester = self.block1.sequence_number_responder + 1
        self.db.add_block(self.block2)
        # Act & Assert
        self.assertEquals(self.db.get_latest_hash(self.block2.public_key_requester), self.block2.hash_requester)

    @blocking_call_on_reactor_thread
    def test_get_by_sequence_number_by_mid_not_existing(self):
        # Act & Assert
        self.assertEquals(self.db.get_by_public_key_and_sequence_number("NON EXISTING KEY", 0), None)

    @blocking_call_on_reactor_thread
    def test_get_by_public_key_and_sequence_number_requester(self):
        # Arrange
        # Make sure that there is a responder block with a lower sequence number.
        # To test that it will look for both responder and requester.
        self.db.add_block(self.block1)
        # Act & Assert
        self.assertEqual_block(self.block1, self.db.get_by_public_key_and_sequence_number(
            self.block1.public_key_requester, self.block1.sequence_number_requester))

    @blocking_call_on_reactor_thread
    def test_get_by_public_key_and_sequence_number_responder(self):
        # Arrange
        # Make sure that there is a responder block with a lower sequence number.
        # To test that it will look for both responder and requester.
        self.db.add_block(self.block1)

        # Act & Assert
        self.assertEqual_block(self.block1, self.db.get_by_public_key_and_sequence_number(
            self.block1.public_key_responder, self.block1.sequence_number_responder))

    @blocking_call_on_reactor_thread
    def test_get_total(self):
        # Arrange
        self.db.add_block(self.block1)
        self.block2.public_key_requester = self.block1.public_key_responder
        self.block2.sequence_number_requester = self.block1.sequence_number_responder + 1
        self.block2.total_up_requester = self.block1.total_up_responder + self.block2.up
        self.block2.total_down_requester = self.block1.total_down_responder + self.block2.down
        self.db.add_block(self.block2)
        # Act
        (result_up, result_down) = self.db.get_total(self.block2.public_key_requester)
        # Assert
        self.assertEqual(self.block2.total_up_requester, result_up)
        self.assertEqual(self.block2.total_down_requester, result_down)

    @blocking_call_on_reactor_thread
    def test_get_total_not_existing(self):
        # Arrange
        self.db.add_block(self.block1)
        # Act
        (result_up, result_down) = self.db.get_total(self.block2.public_key_requester)
        # Assert
        self.assertEqual(0, result_up)
        self.assertEqual(0, result_down)

    @blocking_call_on_reactor_thread
    def test_save_large_upload_download_block(self):
        """
        Test if the block can save very large numbers.
        """
        # Arrange
        self.block1.total_up_requester = long(pow(2, 62))
        self.block1.total_down_requester = long(pow(2, 62))
        self.block1.total_up_responder = long(pow(2, 61))
        self.block1.total_down_responder = pow(2, 60)
        # Act
        self.db.add_block(self.block1)
        # Assert
        result = self.db.get_by_hash(self.block1.hash_requester)
        self.assertEqual_block(self.block1, result)

    @blocking_call_on_reactor_thread
    def test_get_insert_time(self):
        # Arrange
        # Upon adding the block to the database, the timestamp will get added.
        self.db.add_block(self.block1)

        # Act
        # Retrieving the block from the database will result in a block with a
        # timestamp
        result = self.db.get_by_hash(self.block1.hash_requester)

        insert_time = datetime.datetime.strptime(result.insert_time,
                                                 "%Y-%m-%d %H:%M:%S")

        # We store UTC timestamp
        time_difference = datetime.datetime.utcnow() - insert_time

        # Assert
        self.assertEquals(time_difference.days, 0)
        self.assertLess(time_difference.seconds, 10,
                        "Difference in stored and retrieved time is too large.")

    @blocking_call_on_reactor_thread
    def set_db_version(self, version):
        self.db.executescript(u"UPDATE option SET value = '%d' WHERE key = 'database_version';" % version)
        self.db.close(commit=True)
        self.db = MultiChainDB(None, self.getStateDir())

    @blocking_call_on_reactor_thread
    def test_database_upgrade(self):
        self.set_db_version(1)
        version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        self.assertEqual(version, u"2")

    @blocking_call_on_reactor_thread
    def test_database_create(self):
        self.set_db_version(0)
        version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        self.assertEqual(version, u"2")

    @blocking_call_on_reactor_thread
    def test_database_no_downgrade(self):
        self.set_db_version(200000)
        version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        self.assertEqual(version, u"200000")

    @blocking_call_on_reactor_thread
    def test_block_to_dictionary(self):
        """
        Test whether a block is correctly represented when converted to a dictionary
        """
        block_dict = self.block1.to_dictionary()
        self.assertEqual(block_dict["up"], self.block1.up)
        self.assertEqual(block_dict["down"], self.block1.down)
        self.assertEqual(block_dict["insert_time"], self.block1.insert_time)
