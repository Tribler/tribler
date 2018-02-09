from Tribler.Test.Community.Triblerchain.test_triblerchain_utilities import TriblerTestBlock
from Tribler.Test.Community.Trustchain.test_block import MockDatabase
from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.pyipv8.ipv8.attestation.trustchain.block import GENESIS_SEQ, GENESIS_HASH, ValidationResult


class TestBlocks(AbstractServer):
    """
    This class contains tests for a TriblerChain block.
    """

    @classmethod
    def setup_validate(cls):
        # Assert
        block1 = TriblerTestBlock()
        block1.sequence_number = GENESIS_SEQ
        block1.previous_hash = GENESIS_HASH
        block1.sign(block1.key)
        block2 = TriblerTestBlock(previous=block1)
        block3 = TriblerTestBlock(previous=block2)
        block4 = TriblerTestBlock()
        return block1, block2, block3, block4

    def test_validate_up(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.transaction["up"] += 10
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Total up is lower than expected compared to the preceding block', result[1])

    def test_validate_down(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.transaction["down"] += 10
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Total down is lower than expected compared to the preceding block', result[1])

    def test_validate_existing_up(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = TriblerChainBlock(block2.pack_db_insert())
        block2.transaction["up"] += 10
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Total up is lower than expected compared to the preceding block', result[1])

    def test_validate_existing_down(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = TriblerChainBlock(block2.pack_db_insert())
        block2.transaction["down"] += 10
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Total down is lower than expected compared to the preceding block', result[1])

    def test_validate_existing_total_up(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = TriblerChainBlock(block2.pack_db_insert())
        block2.transaction["total_up"] += 10
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Total up is higher than expected compared to the next block', result[1])

    def test_validate_existing_total_down(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = TriblerChainBlock(block2.pack_db_insert())
        block2.transaction["total_down"] += 10
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Total down is higher than expected compared to the next block', result[1])

    def test_validate_genesis(self):
        # Arrange
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        block1.transaction["up"] += 10
        block1.transaction["down"] += 10
        block1.sign(block1.key)
        result = block1.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Genesis block invalid total_up and/or up', result[1])
        self.assertIn('Genesis block invalid total_down and/or down', result[1])

    def test_validate_total_up(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.transaction["total_up"] += 10
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Total up is higher than expected compared to the next block', result[1])

    def test_validate_total_down(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.transaction["total_down"] += 10
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Total down is higher than expected compared to the next block', result[1])

    def test_validate_linked_up(self):
        db = MockDatabase()
        (block1, block2, _, _) = TestBlocks.setup_validate()
        db.add_block(block2)
        # Act
        db.add_block(TriblerChainBlock.create(block1.transaction, db, block1.link_public_key, block1))
        block1.transaction["up"] += 5
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Up/down mismatch on linked block", result[1])

    def test_validate_linked_down(self):
        db = MockDatabase()
        (block1, block2, _, _) = TestBlocks.setup_validate()
        db.add_block(block2)
        # Act
        db.add_block(TriblerChainBlock.create(block1.transaction, db, block1.link_public_key, block1))
        block1.transaction["down"] -= 5
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Down/up mismatch on linked block", result[1])

    def test_validate_not_sane_negatives(self):
        db = MockDatabase()
        block1 = TriblerChainBlock()
        # Act
        block1.transaction = {'up': -10, 'down': -10, 'total_up': -20, 'total_down': -10}
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Up field is negative", result[1])
        self.assertIn("Down field is negative", result[1])
        self.assertIn("Total up field is negative", result[1])
        self.assertIn("Total down field is negative", result[1])

    def test_validate_not_sane_zeroes(self):
        db = MockDatabase()
        block1 = TriblerChainBlock()
        # Act
        block1.transaction = {'up': 0, 'down': 0, 'total_up': 30, 'total_down': 40}
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Up and down are zero", result[1])
