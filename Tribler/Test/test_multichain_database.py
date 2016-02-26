import unittest
import datetime
import os
from math import pow

from Tribler.Test.test_multichain_utilities import TestBlock, MultiChainTestCase
from Tribler.community.multichain.database import MultiChainDB
from Tribler.community.multichain.database import DATABASE_DIRECTORY


class TestDatabase(MultiChainTestCase):
    """
    Tests the Database for MultiChain community.
    Also tests integration with Dispersy.
    This integration slows down the tests,
    but can probably be removed and a Mock Dispersy could be used.
    """

    def __init__(self, *args, **kwargs):
        super(TestDatabase, self).__init__(*args, **kwargs)

    def setUp(self, **kwargs):
        super(TestDatabase, self).setUp()
        path = os.path.join(self.getStateDir(), DATABASE_DIRECTORY)
        if not os.path.exists(path):
            os.makedirs(path)

    def test_add_block(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        # Act
        db.add_block(block1)
        # Assert
        result = db.get_by_hash_requester(block1.hash_requester)
        self.assertEqual_block(block1, result)

    def test_get_by_hash(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        # Act
        db.add_block(block1)
        # Assert
        result1 = db.get_by_hash_requester(block1.hash_requester)
        result2 = db.get_by_hash(block1.hash_requester)
        result3 = db.get_by_hash(block1.hash_responder)
        self.assertEqual_block(block1, result1)
        self.assertEqual_block(block1, result2)
        self.assertEqual_block(block1, result3)


    def test_add_two_blocks(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        block2 = TestBlock()
        # Act
        db.add_block(block1)
        db.add_block(block2)
        # Assert
        result = db.get_by_hash_requester(block2.hash_requester)
        self.assertEqual_block(block2, result)

    def test_get_block_non_existing(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        # Act
        result = db.get_by_hash_requester(block1.hash_requester)
        # Assert
        self.assertEqual(None, result)

    def test_contains_block_id_positive(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        block = TestBlock()
        # Act
        db.add_block(block)
        # Assert
        self.assertTrue(db.contains(block.hash_requester))

    def test_contains_block_id_negative(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        # Act & Assert
        self.assertFalse(db.contains("NON EXISTING ID"))

    def test_get_latest_sequence_number_not_existing(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        # Act & Assert
        self.assertEquals(db.get_latest_sequence_number("NON EXISTING KEY"), -1)

    def test_get_latest_sequence_number_public_key_requester(self):

        # Arrange
        # Make sure that there is a responder block with a lower sequence number.
        # To test that it will look for both responder and requester.
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)
        block2 = TestBlock()
        block2.public_key_responder = block1.public_key_requester
        block2.sequence_number_responder = block1.sequence_number_requester - 5
        db.add_block(block2)
        # Act & Assert
        self.assertEquals(db.get_latest_sequence_number(block1.public_key_requester),
                          block1.sequence_number_requester)

    def test_get_latest_sequence_number_public_key_responder(self):
        # Arrange
        # Make sure that there is a requester block with a lower sequence number.
        # To test that it will look for both responder and requester.
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)
        block2 = TestBlock()
        block2.public_key_requester = block1.public_key_responder
        block2.sequence_number_requester = block1.sequence_number_responder - 5
        db.add_block(block2)
        # Act & Assert
        self.assertEquals(db.get_latest_sequence_number(block1.public_key_responder),
                          block1.sequence_number_responder)

    def test_get_previous_id_not_existing(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        # Act & Assert
        self.assertEquals(db.get_latest_hash("NON EXISTING KEY"), None)

    def test_get_previous_hash_of_requester(self):
        # Arrange
        # Make sure that there is a responder block with a lower sequence number.
        # To test that it will look for both responder and requester.
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)
        block2 = TestBlock()
        block2.public_key_responder = block1.public_key_requester
        block2.sequence_number_responder = block1.sequence_number_requester + 1
        db.add_block(block2)
        # Act & Assert
        self.assertEquals(db.get_latest_hash(block2.public_key_responder), block2.hash_responder)

    def test_get_previous_hash_of_responder(self):
        # Arrange
        # Make sure that there is a requester block with a lower sequence number.
        # To test that it will look for both responder and requester.
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)
        block2 = TestBlock()
        block2.public_key_requester = block1.public_key_responder
        block2.sequence_number_requester = block1.sequence_number_responder + 1
        db.add_block(block2)
        # Act & Assert
        self.assertEquals(db.get_latest_hash(block2.public_key_requester), block2.hash_requester)

    def test_get_by_sequence_number_by_mid_not_existing(self):

        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        # Act & Assert
        self.assertEquals(db.get_by_public_key_and_sequence_number("NON EXISTING KEY", 0), None)

    def test_get_by_public_key_and_sequence_number_requester(self):
        # Arrange
        # Make sure that there is a responder block with a lower sequence number.
        # To test that it will look for both responder and requester.
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)
        # Act & Assert
        self.assertEqual_block(block1, db.get_by_public_key_and_sequence_number(
            block1.public_key_requester, block1.sequence_number_requester))

    def test_get_by_public_key_and_sequence_number_responder(self):
        # Arrange
        # Make sure that there is a responder block with a lower sequence number.
        # To test that it will look for both responder and requester.
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)
        
        # Act & Assert
        self.assertEqual_block(block1, db.get_by_public_key_and_sequence_number(
            block1.public_key_responder, block1.sequence_number_responder))

    def test_get_total(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)
        block2 = TestBlock()
        block2.public_key_requester = block1.public_key_responder
        block2.sequence_number_requester = block1.sequence_number_responder + 1
        block2.total_up_requester = block1.total_up_responder + block2.up
        block2.total_down_requester = block1.total_down_responder + block2.down
        db.add_block(block2)
        # Act
        (result_up, result_down) = db.get_total(block2.public_key_requester)
        # Assert
        self.assertEqual(block2.total_up_requester, result_up)
        self.assertEqual(block2.total_down_requester, result_down)

    def test_get_total_not_existing(self):
        # Arrange
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)
        block2 = TestBlock()
        # Act
        (result_up, result_down) = db.get_total(block2.public_key_requester)
        # Assert
        self.assertEqual(-1, result_up)
        self.assertEqual(-1, result_down)

    def test_save_large_upload_download_block(self):
        """
        Test if the block can save very large numbers.
        """  # Arrange
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        block1.total_up_requester = long(pow(2, 62))
        block1.total_down_requester = long(pow(2, 62))
        block1.total_up_responder = long(pow(2, 61))
        block1.total_down_responder = pow(2, 60)
        # Act
        db.add_block(block1)
        # Assert
        result = db.get_by_hash(block1.hash_requester)
        self.assertEqual_block(block1, result)

    def test_get_insert_time(self):
        # Arrange
        # Upon adding the block to the database, the timestamp will get added.
        db = MultiChainDB(None, self.getStateDir())
        block1 = TestBlock()
        db.add_block(block1)

        # Act
        # Retrieving the block from the database will result in a block with a
        # timestamp
        result = db.get_by_hash(block1.hash_requester)

        insert_time = datetime.datetime.strptime(result.insert_time,
                                                 "%Y-%m-%d %H:%M:%S")

        # We store UTC timestamp
        time_difference = datetime.datetime.utcnow() - insert_time

        # Assert
        self.assertEquals(time_difference.days, 0)
        self.assertLess(time_difference.seconds, 10,
                        "Difference in stored and retrieved time is too large.")


if __name__ == '__main__':
    unittest.main()
