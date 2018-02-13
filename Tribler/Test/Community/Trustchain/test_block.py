import random

from hashlib import sha256

from Tribler.dispersy.crypto import ECCrypto
from Tribler.community.trustchain.block import (TrustChainBlock, GENESIS_HASH, EMPTY_SIG, GENESIS_SEQ, EMPTY_PK,
                                                ValidationResult)
from Tribler.Test.Community.Trustchain.test_trustchain_utilities import TrustChainTestCase, TestBlock


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

    def get_latest(self, pk):
        return self.data[pk][-1] if self.data.get(pk) else None

    def get_block_after(self, blk):
        if self.data.get(blk.public_key) is None:
            return None
        item = [i for i in self.data[blk.public_key] if i.sequence_number > blk.sequence_number]
        return item[0] if item else None

    def get_block_before(self, blk):
        if self.data.get(blk.public_key) is None:
            return None
        item = [i for i in self.data[blk.public_key] if i.sequence_number < blk.sequence_number]
        return item[-1] if item else None


class TestBlocks(TrustChainTestCase):
    """
    This class contains tests for a TrustChain block.
    """

    def test_hash(self):
        block = TrustChainBlock()
        self.assertEqual(block.hash, 'f\xfb\xd2ZQQ]:<5\xaf\xf0_\xcb<\x14\x80S\x8e\x9b\x93h\xb1\x0c!(2\xe8FJ\x98z')

    def test_sign(self):
        crypto = ECCrypto()
        block = TestBlock()
        self.assertTrue(crypto.is_valid_signature(block.key, block.pack(signature=False), block.signature))

    def test_create_genesis(self):
        key = ECCrypto().generate_key(u"curve25519")
        db = MockDatabase()
        block = TrustChainBlock.create([42], db, key.pub().key_to_bin(), link=None)
        self.assertEqual(block.previous_hash, GENESIS_HASH)
        self.assertEqual(block.sequence_number, GENESIS_SEQ)
        self.assertEqual(block.public_key, key.pub().key_to_bin())
        self.assertEqual(block.signature, EMPTY_SIG)

    def test_create_next(self):
        db = MockDatabase()
        prev = TestBlock()
        prev.sequence_number = GENESIS_SEQ
        db.add_block(prev)
        block = TrustChainBlock.create([42], db, prev.public_key, link=None)
        self.assertEqual(block.previous_hash, prev.hash)
        self.assertEqual(block.sequence_number, 2)
        self.assertEqual(block.public_key, prev.public_key)

    def test_create_link_genesis(self):
        key = ECCrypto().generate_key(u"curve25519")
        db = MockDatabase()
        link = TestBlock()
        db.add_block(link)
        block = TrustChainBlock.create([42], db, key.pub().key_to_bin(), link=link)
        self.assertEqual(block.previous_hash, GENESIS_HASH)
        self.assertEqual(block.sequence_number, GENESIS_SEQ)
        self.assertEqual(block.public_key, key.pub().key_to_bin())
        self.assertEqual(block.link_public_key, link.public_key)
        self.assertEqual(block.link_sequence_number, link.sequence_number)

    def test_create_link_next(self):
        db = MockDatabase()
        prev = TestBlock()
        prev.sequence_number = GENESIS_SEQ
        db.add_block(prev)
        link = TestBlock()
        db.add_block(link)
        block = TrustChainBlock.create([42], db, prev.public_key, link=link)
        self.assertEqual(block.previous_hash, prev.hash)
        self.assertEqual(block.sequence_number, 2)
        self.assertEqual(block.public_key, prev.public_key)
        self.assertEqual(block.link_public_key, link.public_key)
        self.assertEqual(block.link_sequence_number, link.sequence_number)

    def test_pack(self):
        block = TrustChainBlock()
        block.transaction = {'id': 3}
        block.public_key = ' fish, so sad that it should come to this. - We tried to warn you all but '
        block.sequence_number = 1869095012
        block.link_public_key = 'ear! - You may not share our intellect, which might explain your disrespec'
        block.link_sequence_number = 1949048934
        block.previous_hash = 'or all the natural wonders that '
        block.signature = 'grow around you. - So long, so long, and thanks for all the fish'
        self.assertEqual(block.pack(), ' fish, so sad that it should come to this. - We tried to warn you '
                                       'all but oh dear! - You may not share our intellect, which might explain your '
                                       'disrespect, for all the natural wonders that grow around you. - So long, '
                                       'so long, and thanks for all the fish\x00\x00\x00\na1d2bid1i3')

    def test_unpack(self):
        block = TrustChainBlock.unpack(' fish, so sad that it should come to this. - We tried to warn you '
                                       'all but oh dear! - You may not share our intellect, which might explain your '
                                       'disrespect, for all the natural wonders that grow around you. - So long, '
                                       'so long, and thanks for all the fish\x00\x00\x00\na1d2bid1i3')[1]
        self.assertEqual(block.transaction, {'id': 3})
        self.assertEqual(block.public_key, ' fish, so sad that it should come to this. - We tried to warn you all but ')
        self.assertEqual(block.sequence_number, 1869095012)
        self.assertEqual(block.link_public_key,
                         'ear! - You may not share our intellect, which might explain your disrespec')
        self.assertEqual(block.link_sequence_number, 1949048934)
        self.assertEqual(block.previous_hash, 'or all the natural wonders that ')
        self.assertEqual(block.signature, 'grow around you. - So long, so long, and thanks for all the fish')

    def test_validate_existing(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.valid)

    def test_validate_non_existing(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.valid)

    def test_validate_no_info(self):
        # Arrange
        db = MockDatabase()
        (_, _, _, block4) = TestBlocks.setup_validate()
        db.add_block(block4)
        # Act
        result = block4.validate(db)
        # Assert
        self.assertEqual(result, (ValidationResult.no_info, []))

    def test_validate_partial_prev(self):
        # Arrange
        db = MockDatabase()
        (_, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block2)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.partial_previous)

    def test_validate_partial_next(self):
        # Arrange
        db = MockDatabase()
        (_, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block2)
        db.add_block(block3)
        # Act
        result = block3.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.partial_next)

    def test_validate_partial_prev_with_gap(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        block2.previous_hash = block2.hash
        block2.sequence_number += 1
        block2.sign(block2.key)
        block3.sequence_number += 1
        block3.previous_hash = block2.hash
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.partial_previous)

    def test_validate_partial_next_with_gap(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        block3.sequence_number += 1
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.partial_next)

    def test_validate_partial_left_gap(self):
        # Arrange
        db = MockDatabase()
        (block1, _, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block3.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.partial)

    def test_validate_partial_right_gap_from_genesis(self):
        # Arrange
        db = MockDatabase()
        (block1, _, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block1.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.partial_next)

    def test_validate_partial_right_gap(self):
        # Arrange
        db = MockDatabase()
        (block1, _, block3, _) = TestBlocks.setup_validate()
        block1.previous_hash = block3.previous_hash
        block1.sequence_number += 1
        block1.sign(block1.key)
        block3.sequence_number += 1
        db.add_block(block3)
        # Act
        result = block1.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.partial)

    def test_validate_partial_with_both_gaps(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        block2.previous_hash = block2.hash
        block2.sequence_number += 1
        block2.sign(block2.key)
        block3.sequence_number += 2
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.partial)

    def test_validate_existing_link_public_key(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = TrustChainBlock(block2.pack_db_insert())
        block2.link_public_key = EMPTY_PK
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Linked public key is not valid', result[1])

    def test_validate_existing_link_sequence_number(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = TrustChainBlock(block2.pack_db_insert())
        block2.link_sequence_number += 100
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Link sequence number does not match known block', result[1])

    def test_validate_existing_hash(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = TrustChainBlock(block2.pack_db_insert())
        block2.previous_hash = sha256(str(random.randint(0, 100000))).digest()
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Previous hash is not equal to the hash id of the previous block', result[1])

    def test_validate_existing_fraud(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, _, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        # Act
        block3 = TrustChainBlock(block2.pack_db_insert())
        block3.previous_hash = sha256(str(random.randint(0, 100000))).digest()
        block3.sign(block2.key)
        result = block3.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Double sign fraud", result[1])

    def test_validate_seq_not_genesis(self):
        # Arrange
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        block1.previous_hash = sha256(str(random.randint(0, 100000))).digest()
        block1.sign(block1.key)
        result = block1.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Sequence number implies previous hash should be Genesis ID', result[1])

    def test_validate_seq_genesis(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.previous_hash = GENESIS_HASH
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Sequence number implies previous hash should not be Genesis ID', result[1])

    def test_validate_hash(self):
        # Arrange
        db = MockDatabase()
        (block1, block2, block3, _) = TestBlocks.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.previous_hash = sha256(str(random.randint(0, 100000))).digest()
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn('Previous hash is not equal to the hash id of the previous block', result[1])

    def test_validate_not_sane_sequence_number(self):
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        block1.sequence_number = 0
        block1.sign(block1.key)
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Sequence number is prior to genesis", result[1])

    def test_validate_not_sane_link_sequence_number(self):
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        block1.link_sequence_number = -1
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Link sequence number not empty and is prior to genesis", result[1])

    def test_validate_not_sane_public_key(self):
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        block1.public_key = EMPTY_PK
        block1.sign(block1.key)
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Public key is not valid", result[1])

    def test_validate_not_sane_link_public_key(self):
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        block1.link_public_key = EMPTY_PK
        block1.sign(block1.key)
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Linked public key is not valid", result[1])

    def test_validate_not_sane_self_signed(self):
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        block1.link_public_key = block1.public_key
        block1.sign(block1.key)
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Self signed block", result[1])

    def test_validate_not_sane_invalid_signature(self):
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        block1.signature = EMPTY_SIG
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Invalid signature", result[1])

    def test_validate_linked_valid(self):
        db = MockDatabase()
        (block1, block2, _, _) = TestBlocks.setup_validate()
        db.add_block(block2)
        # Act
        db.add_block(TrustChainBlock.create(block1.transaction, db, block1.link_public_key, block1))
        result = block1.validate(db)
        self.assertEqual(result[0], ValidationResult.valid)

    def test_validate_linked_mismatch(self):
        db = MockDatabase()
        (block1, block2, _, _) = TestBlocks.setup_validate()
        # Act
        db.add_block(block1)
        block3 = TrustChainBlock.create(block2.transaction, db, block2.link_public_key, block1)
        result = block3.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Public key mismatch on linked block", result[1])

    def test_validate_linked_double_pay_fraud(self):
        db = MockDatabase()
        (block1, _, _, _) = TestBlocks.setup_validate()
        # Act
        db.add_block(block1)
        db.add_block(TrustChainBlock.create(block1.transaction, db, block1.link_public_key, block1))
        block2 = TrustChainBlock.create(block1.transaction, db, block1.link_public_key, block1)
        result = block2.validate(db)
        self.assertEqual(result[0], ValidationResult.invalid)
        self.assertIn("Double countersign fraud", result[1])

    @classmethod
    def setup_validate(cls):
        # Assert
        block1 = TestBlock()
        block1.sequence_number = GENESIS_SEQ
        block1.previous_hash = GENESIS_HASH
        block1.sign(block1.key)
        block2 = TestBlock(previous=block1)
        block3 = TestBlock(previous=block2)
        block4 = TestBlock()
        return block1, block2, block3, block4

    def test_validation_results(self):
        self.assertIsNone(ValidationResult.invalid())
        self.assertIsNone(ValidationResult.no_info())
        self.assertIsNone(ValidationResult.partial())
        self.assertIsNone(ValidationResult.partial_next())
        self.assertIsNone(ValidationResult.partial_previous())
        self.assertIsNone(ValidationResult.valid())
