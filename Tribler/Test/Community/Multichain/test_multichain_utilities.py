"""
File containing utilities used in testing the MultiChain community.
"""
import random
from hashlib import sha256
from Tribler.dispersy.crypto import ECCrypto
from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.multichain.block import MultiChainBlock, EMPTY_PK


class TestBlock(MultiChainBlock):
    """
    Test Block that simulates a block used in MultiChain.
    Also used in other test files for MultiChain.
    """

    def __init__(self, previous=None):
        crypto = ECCrypto()
        up = random.randint(201, 220)
        down = random.randint(221, 240)
        other = crypto.generate_key(u"curve25519").pub().key_to_bin()

        if previous:
            self.key = previous.key
            MultiChainBlock.__init__(self, (
                up, down, previous.total_up + up, previous.total_down + down,
                previous.public_key, previous.sequence_number + 1, other, 0,
                previous.hash, 0, 0))
        else:
            self.key = crypto.generate_key(u"curve25519")
            MultiChainBlock.__init__(self, (
                up, down, random.randint(241, 260), random.randint(261, 280),
                self.key.pub().key_to_bin(), random.randint(50, 100), other, 0,
                sha256(str(random.randint(0, 100000))).digest(), 0, 0))
        self.sign(self.key)


class MultiChainTestCase(AbstractServer):
    def assertEqual_block(self, expected_block, actual_block):
        """
        Function to assertEqual two blocks
        """
        crypto = ECCrypto()
        self.assertTrue(expected_block is not None)
        self.assertTrue(actual_block is not None)
        self.assertTrue(crypto.is_valid_public_bin(expected_block.public_key))
        self.assertTrue(crypto.is_valid_public_bin(actual_block.public_key))
        self.assertEqual(expected_block.up, actual_block.up)
        self.assertEqual(expected_block.down, actual_block.down)
        self.assertEqual(expected_block.total_up, actual_block.total_up)
        self.assertEqual(expected_block.total_down, actual_block.total_down)
        self.assertEqual(expected_block.public_key, actual_block.public_key)
        self.assertEqual(expected_block.sequence_number, actual_block.sequence_number)
        self.assertEqual(expected_block.link_public_key, actual_block.link_public_key)
        self.assertEqual(expected_block.link_sequence_number, actual_block.link_sequence_number)
        self.assertEqual(expected_block.previous_hash, actual_block.previous_hash)
        self.assertEqual(expected_block.signature, actual_block.signature)
        return True
