from hashlib import sha256
import random

from Tribler.Core.Modules.wallet.bandwidth_block import TriblerBandwidthBlock
from Tribler.Core.Utilities.encoding import encode
from Tribler.Test.test_as_server import AbstractServer
from Tribler.pyipv8.ipv8.attestation.trustchain.block import GENESIS_SEQ, GENESIS_HASH, ValidationResult
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto


class TriblerBandwidthTestBlock(TriblerBandwidthBlock):
    """
    Test Block that simulates a block used in TrustChain.
    """

    def __init__(self, previous=None):
        super(TriblerBandwidthTestBlock, self).__init__()
        crypto = ECCrypto()
        other = crypto.generate_key(u"curve25519").pub().key_to_bin()

        transaction = {'up': random.randint(201, 220), 'down': random.randint(221, 240), 'total_up': 0,
                       'total_down': 0, 'type': 'tribler_bandwidth'}

        if previous:
            self.key = previous.key
            transaction['total_up'] = previous.transaction['total_up'] + transaction['up']
            transaction['total_down'] = previous.transaction['total_down'] + transaction['down']
            TriblerBandwidthBlock.__init__(self, ('tribler_bandwidth', encode(transaction), previous.public_key,
                                                  previous.sequence_number + 1, other, 0, previous.hash, 0, 0, 0))
        else:
            transaction['total_up'] = random.randint(241, 260)
            transaction['total_down'] = random.randint(261, 280)
            self.key = crypto.generate_key(u"curve25519")
            TriblerBandwidthBlock.__init__(self, (
                'tribler_bandwidth', encode(transaction), self.key.pub().key_to_bin(), random.randint(50, 100), other,
                0, sha256(str(random.randint(0, 100000))).digest(), 0, 0, 0))
        self.sign(self.key)


class MockDatabase(object):
    """
    This mocked database is only used during the tests.
    """

    def __init__(self):
        super(MockDatabase, self).__init__()
        self.data = dict()

    def add_block(self, block):
        if self.data.get(block.public_key) is None:
            self.data[block.public_key] = []
        self.data[block.public_key].append(block)
        self.data[block.public_key].sort(key=lambda b: b.sequence_number)

    def get(self, pk, seq):
        if self.data.get(pk) is None:
            return None
        item = [i for i in self.data[pk] if i.sequence_number == seq]
        return item[0] if item else None

    def get_linked(self, blk):
        if self.data.get(blk.link_public_key) is None:
            return None
        item = [i for i in self.data[blk.link_public_key] if
                i.sequence_number == blk.link_sequence_number or i.link_sequence_number == blk.sequence_number]
        return item[0] if item else None

    def get_latest(self, pk, block_type=None):
        return self.data[pk][-1] if self.data.get(pk) else None

    def get_block_after(self, blk, block_type=None):
        if self.data.get(blk.public_key) is None:
            return None
        item = [i for i in self.data[blk.public_key] if i.sequence_number > blk.sequence_number]
        return item[0] if item else None

    def get_block_before(self, blk, block_type=None):
        if self.data.get(blk.public_key) is None:
            return None
        item = [i for i in self.data[blk.public_key] if i.sequence_number < blk.sequence_number]
        return item[-1] if item else None


class TestBlocks(AbstractServer):
    """
    This class contains tests for a TrustChain block that captures a bandwidth transaction.
    """

    @classmethod
    def setup_validate(cls):
        # Assert
        block1 = TriblerBandwidthTestBlock()
        block1.sequence_number = GENESIS_SEQ
        block1.previous_hash = GENESIS_HASH
        block1.sign(block1.key)
        block2 = TriblerBandwidthTestBlock(previous=block1)
        block3 = TriblerBandwidthTestBlock(previous=block2)
        block4 = TriblerBandwidthTestBlock()
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
        block2 = TriblerBandwidthBlock(block2.pack_db_insert())
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
        block2 = TriblerBandwidthBlock(block2.pack_db_insert())
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
        block2 = TriblerBandwidthBlock(block2.pack_db_insert())
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
        block2 = TriblerBandwidthBlock(block2.pack_db_insert())
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
        db.add_block(TriblerBandwidthBlock.create('tribler_bandwidth', block1.transaction, db,
                                                  block1.link_public_key, block1))
        block1.transaction["up"] += 5
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Up/down mismatch on linked block", result[1])

    def test_validate_linked_down(self):
        db = MockDatabase()
        (block1, block2, _, _) = TestBlocks.setup_validate()
        db.add_block(block2)
        # Act
        db.add_block(TriblerBandwidthBlock.create('tribler_bandwidth', block1.transaction, db,
                                                  block1.link_public_key, block1))
        block1.transaction["down"] -= 5
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Down/up mismatch on linked block", result[1])

    def test_validate_not_sane_negatives(self):
        db = MockDatabase()
        block1 = TriblerBandwidthBlock()
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
        block1 = TriblerBandwidthBlock()
        # Act
        block1.transaction = {'up': 0, 'down': 0, 'total_up': 30, 'total_down': 40}
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Up and down are zero", result[1])
