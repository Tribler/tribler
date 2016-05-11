import random

from hashlib import sha256

from Tribler.dispersy.crypto import ECCrypto
from Tribler.community.multichain.block import (MultiChainBlock, GENESIS_ID, EMPTY_SIG, GENESIS_SEQ, EMPTY_PK, VALID,
                                                INVALID, NO_INFO, PARTIAL, PARTIAL_NEXT, PARTIAL_PREV)
from Tribler.Test.Community.Multichain.test_multichain_utilities import MultiChainTestCase, TestBlock


class TestBlocks(MultiChainTestCase):
    def __init__(self, *args, **kwargs):
        super(TestBlocks, self).__init__(*args, **kwargs)

    def test_hash(self):
        block = MultiChainBlock()
        self.assertEqual(block.hash, "\xa1c!\x14\x11\x14\xe4\xb1g\xebB\xae\xc1y-\x0eF\x1d\x94'\x1co\xc5\xe4g\x80\xf1"
                                     "\xc1z\xb0\x12\xd7")

    def test_sign(self):
        crypto = ECCrypto()
        block = TestBlock()
        self.assertTrue(crypto.is_valid_signature(block.key, block.pack(signature=False), block.signature))

    def test_create_genesis(self):
        key = ECCrypto().generate_key(u"curve25519")
        db = self.MockDatabase()
        block = MultiChainBlock.create(db, key.pub().key_to_bin(), link=None)
        self.assertEqual(block.previous_hash, GENESIS_ID)
        self.assertEqual(block.sequence_number, GENESIS_SEQ)
        self.assertEqual(block.public_key, key.pub().key_to_bin())
        self.assertEqual(block.signature, EMPTY_SIG)

    def test_create_next(self):
        db = self.MockDatabase()
        prev = TestBlock()
        prev.sequence_number = GENESIS_SEQ
        db.add_block(prev)
        block = MultiChainBlock.create(db, prev.public_key, link=None)
        self.assertEqual(block.previous_hash, prev.hash)
        self.assertEqual(block.sequence_number, 2)
        self.assertEqual(block.public_key, prev.public_key)

    def test_create_link_genesis(self):
        key = ECCrypto().generate_key(u"curve25519")
        db = self.MockDatabase()
        link = TestBlock()
        db.add_block(link)
        block = MultiChainBlock.create(db, key.pub().key_to_bin(), link=link)
        self.assertEqual(block.previous_hash, GENESIS_ID)
        self.assertEqual(block.sequence_number, GENESIS_SEQ)
        self.assertEqual(block.public_key, key.pub().key_to_bin())
        self.assertEqual(block.link_public_key, link.public_key)
        self.assertEqual(block.link_sequence_number, link.sequence_number)

    def test_create_link_next(self):
        db = self.MockDatabase()
        prev = TestBlock()
        prev.sequence_number = GENESIS_SEQ
        db.add_block(prev)
        link = TestBlock()
        db.add_block(link)
        block = MultiChainBlock.create(db, prev.public_key, link=link)
        self.assertEqual(block.previous_hash, prev.hash)
        self.assertEqual(block.sequence_number, 2)
        self.assertEqual(block.public_key, prev.public_key)
        self.assertEqual(block.link_public_key, link.public_key)
        self.assertEqual(block.link_sequence_number, link.sequence_number)

    def test_pack(self):
        block = MultiChainBlock()
        block.up = 3251690667711950702
        block.down = 7431046511915463784
        block.total_up = 7020667011326177138
        block.total_down = 2333265293611395173
        block.public_key = ' fish, so sad that it should come to this. - We tried to warn you all but '
        block.sequence_number = 1869095012
        block.link_public_key = 'ear! - You may not share our intellect, which might explain your disrespec'
        block.link_sequence_number = 1949048934
        block.previous_hash = 'or all the natural wonders that '
        block.signature = 'grow around you. - So long, so long, and thanks for all the fish'
        self.assertEqual(block.pack(), '- So long and thanks for all the fish, so sad that it should come to this. - We'
                                       ' tried to warn you all but oh dear! - You may not share our intellect, which '
                                       'might explain your disrespect, for all the natural wonders that grow around you'
                                       '. - So long, so long, and thanks for all the fish')

    def test_unpack(self):
        block = MultiChainBlock.unpack('- So long and thanks for all the fish, so sad that it should come to this. - '
                                       'We tried to warn you all but oh dear! - You may not share our intellect, which '
                                       'might explain your disrespect, for all the natural wonders that grow around '
                                       'you. - So long, so long, and thanks for all the fish')
        self.assertEqual(block.up, 3251690667711950702)
        self.assertEqual(block.down, 7431046511915463784)
        self.assertEqual(block.total_up, 7020667011326177138)
        self.assertEqual(block.total_down, 2333265293611395173)
        self.assertEqual(block.public_key, ' fish, so sad that it should come to this. - We tried to warn you all but ')
        self.assertEqual(block.sequence_number, 1869095012)
        self.assertEqual(block.link_public_key,
                         'ear! - You may not share our intellect, which might explain your disrespec')
        self.assertEqual(block.link_sequence_number, 1949048934)
        self.assertEqual(block.previous_hash, 'or all the natural wonders that ')
        self.assertEqual(block.signature, 'grow around you. - So long, so long, and thanks for all the fish')

    def test_validate_existing(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], VALID)

    def test_validate_non_existing(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], VALID)

    def test_validate_no_info(self):
        # Arrange
        db = self.MockDatabase()
        (_, _, _, block4) = self.setup_validate()
        db.add_block(block4)
        # Act
        result = block4.validate(db)
        # Assert
        self.assertEqual(result, (NO_INFO, ['No blocks are known for this member before or after the queried '
                                              'sequence number']))

    def test_validate_partial_prev(self):
        # Arrange
        db = self.MockDatabase()
        (_, block2, block3, _) = self.setup_validate()
        db.add_block(block2)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], PARTIAL_PREV)

    def test_validate_partial_next(self):
        # Arrange
        db = self.MockDatabase()
        (_, block2, block3, _) = self.setup_validate()
        db.add_block(block2)
        db.add_block(block3)
        # Act
        result = block3.validate(db)
        # Assert
        self.assertEqual(result[0], PARTIAL_NEXT)

    def test_validate_partial_prev_with_gap(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
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
        self.assertEqual(result[0], PARTIAL_PREV)

    def test_validate_partial_next_with_gap(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        block3.sequence_number += 1
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], PARTIAL_NEXT)

    def test_validate_partial_left_gap(self):
        # Arrange
        db = self.MockDatabase()
        (block1, _, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block3.validate(db)
        # Assert
        self.assertEqual(result[0], PARTIAL)

    def test_validate_partial_right_gap(self):
        # Arrange
        db = self.MockDatabase()
        (block1, _, block3, _) = self.setup_validate()
        block1.previous_hash = block3.previous_hash
        block1.sequence_number += 1
        block1.sign(block1.key)
        block3.sequence_number += 1
        db.add_block(block3)
        # Act
        result = block1.validate(db)
        # Assert
        self.assertEqual(result[0], PARTIAL)

    def test_validate_partial_with_both_gaps(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        block2.previous_hash = block2.hash
        block2.sequence_number += 1
        block2.sign(block2.key)
        block3.sequence_number += 2
        db.add_block(block1)
        db.add_block(block3)
        # Act
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], PARTIAL)

    def test_validate_existing_up(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = MultiChainBlock(block2.pack_db_insert())
        block2.up += 10
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Total up is lower than expected compared to the preceding block', result[1])

    def test_validate_existing_down(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = MultiChainBlock(block2.pack_db_insert())
        block2.down += 10
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Total down is lower than expected compared to the preceding block', result[1])

    def test_validate_existing_total_up(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = MultiChainBlock(block2.pack_db_insert())
        block2.total_up += 10
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Total up is higher than expected compared to the next block', result[1])

    def test_validate_existing_total_down(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = MultiChainBlock(block2.pack_db_insert())
        block2.total_down += 10
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Total down is higher than expected compared to the next block', result[1])

    def test_validate_existing_link_public_key(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = MultiChainBlock(block2.pack_db_insert())
        block2.link_public_key = EMPTY_PK
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Linked public key is not valid', result[1])

    def test_validate_existing_link_sequence_number(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = MultiChainBlock(block2.pack_db_insert())
        block2.link_sequence_number += 100
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Link sequence number does not match known block', result[1])

    def test_validate_existing_hash(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block2)
        db.add_block(block3)
        # Act
        block2 = MultiChainBlock(block2.pack_db_insert())
        block2.previous_hash = sha256(str(random.randint(0, 100000))).digest()
        block2.sign(db.get(block2.public_key, block2.sequence_number).key)
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Previous hash is not equal to the hash id of the previous block', result[1])

    def test_validate_seq_not_genesis(self):
        # Arrange
        db = self.MockDatabase()
        (block1, _, _, _) = self.setup_validate()
        # Act
        block1.previous_hash = sha256(str(random.randint(0, 100000))).digest()
        block1.sign(block1.key)
        result = block1.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Sequence number implies previous hash should be Genesis ID', result[1])

    def test_validate_seq_genesis(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.previous_hash = GENESIS_ID
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Sequence number implies previous hash should not be Genesis ID', result[1])

    def test_validate_genesis(self):
        # Arrange
        db = self.MockDatabase()
        (block1, _, _, _) = self.setup_validate()
        # Act
        block1.up += 10
        block1.down += 10
        block1.sign(block1.key)
        result = block1.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Genesis block invalid total_up and/or up', result[1])
        self.assertIn('Genesis block invalid total_down and/or down', result[1])

    def test_validate_up(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.up += 10
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Total up is lower than expected compared to the preceding block', result[1])

    def test_validate_down(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.down += 10
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Total down is lower than expected compared to the preceding block', result[1])

    def test_validate_total_up(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.total_up += 10
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Total up is higher than expected compared to the next block', result[1])

    def test_validate_total_down(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.total_down += 10
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Total down is higher than expected compared to the next block', result[1])

    def test_validate_hash(self):
        # Arrange
        db = self.MockDatabase()
        (block1, block2, block3, _) = self.setup_validate()
        db.add_block(block1)
        db.add_block(block3)
        # Act
        block2.previous_hash = sha256(str(random.randint(0, 100000))).digest()
        block2.sign(block2.key)
        block3.previous_hash = block2.hash
        result = block2.validate(db)
        # Assert
        self.assertEqual(result[0], INVALID)
        self.assertIn('Previous hash is not equal to the hash id of the previous block', result[1])

    def test_validate_not_sane_negatives(self):
        db = self.MockDatabase()
        block1 = MultiChainBlock()
        # Act
        block1.up = -10
        block1.down = -20
        block1.total_down = -10
        block1.total_up = -20
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Up field is negative", result[1])
        self.assertIn("Down field is negative", result[1])
        self.assertIn("Total up field is negative", result[1])
        self.assertIn("Total down field is negative", result[1])

    def test_validate_not_sane_sequence_number(self):
        db = self.MockDatabase()
        (block1, _, _, _) = self.setup_validate()
        # Act
        block1.sequence_number = 0
        block1.sign(block1.key)
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Sequence number is prior to genesis", result[1])

    def test_validate_not_sane_link_sequence_number(self):
        db = self.MockDatabase()
        (block1, _, _, _) = self.setup_validate()
        # Act
        block1.link_sequence_number = -1
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Link sequence number not empty and is prior to genesis", result[1])

    def test_validate_not_sane_public_key(self):
        db = self.MockDatabase()
        (block1, _, _, _) = self.setup_validate()
        # Act
        block1.public_key = EMPTY_PK
        block1.sign(block1.key)
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Public key is not valid", result[1])

    def test_validate_not_sane_link_public_key(self):
        db = self.MockDatabase()
        (block1, _, _, _) = self.setup_validate()
        # Act
        block1.link_public_key = EMPTY_PK
        block1.sign(block1.key)
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Linked public key is not valid", result[1])

    def test_validate_not_sane_self_signed(self):
        db = self.MockDatabase()
        (block1, _, _, _) = self.setup_validate()
        # Act
        block1.link_public_key = block1.public_key
        block1.sign(block1.key)
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Self signed block", result[1])

    def test_validate_not_sane_invalid_signature(self):
        db = self.MockDatabase()
        (block1, _, _, _) = self.setup_validate()
        # Act
        block1.signature = EMPTY_SIG
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Invalid signature", result[1])

    def test_validate_linked_valid(self):
        db = self.MockDatabase()
        (block1, block2, _, _) = self.setup_validate()
        db.add_block(block2)
        # Act
        db.add_block(MultiChainBlock.create(db, block1.link_public_key, block1))
        result = block1.validate(db)
        self.assertEqual(result[0], VALID)

    def test_validate_linked_up(self):
        db = self.MockDatabase()
        (block1, block2, _, _) = self.setup_validate()
        db.add_block(block2)
        # Act
        db.add_block(MultiChainBlock.create(db, block1.link_public_key, block1))
        block1.up += 5
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Up/down mismatch on linked block", result[1])

    def test_validate_linked_down(self):
        db = self.MockDatabase()
        (block1, block2, _, _) = self.setup_validate()
        db.add_block(block2)
        # Act
        db.add_block(MultiChainBlock.create(db, block1.link_public_key, block1))
        block1.down -= 5
        result = block1.validate(db)
        self.assertEqual(result[0], INVALID)
        self.assertIn("Down/up mismatch on linked block", result[1])

    def setup_validate(self):
        # Assert
        block1 = TestBlock()
        block1.sequence_number = GENESIS_SEQ
        block1.previous_hash = GENESIS_ID
        block1.total_up = block1.up
        block1.total_down = block1.down
        block1.sign(block1.key)
        block2 = TestBlock(previous=block1)
        block3 = TestBlock(previous=block2)
        block4 = TestBlock()
        return block1, block2, block3, block4

    class MockDatabase(object):
        def __init__(self, *args, **kwargs):
            super(TestBlocks.MockDatabase, self).__init__(*args, **kwargs)
            self.data = dict()

        def add_block(self, block):
            if self.data.get(block.public_key) is None:
                self.data[block.public_key] = []
            self.data[block.public_key].append(block)
            self.data[block.public_key].sort(key=lambda b: b.sequence_number)

        def contains(self, pk, seq):
            return self.get(pk, seq) is not None

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

        def get_blocks_since(self, pk, seq, limit=100):
            if self.data.get(pk) is None:
                return []
            return [i for i in self.data[pk] if i.sequence_number >= seq][:limit]

        def get_blocks_until(self, pk, seq, limit=100):
            if self.data.get(pk) is None:
                return []
            return [i for i in self.data[pk] if i.sequence_number <= seq][::-1][:limit]   # TODO: possible in one slice?
