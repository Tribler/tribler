"""
File containing utilities used in testing the double entry community.
"""
import random
from hashlib import sha256
from Tribler.dispersy.crypto import ECCrypto
from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.multichain.block import MultiChainBlock, EMPTY_PK


class TestBlock(MultiChainBlock):
    """
    Test Block that simulates a block message used in MultiChain.
    Also used in other test files for MultiChain.
    """

    def __init__(self):
        crypto = ECCrypto()
        key = crypto.generate_key(u"curve25519")

        MultiChainBlock.__init__(
            (random.randint(201, 220), random.randint(221, 240), random.randint(241, 260), random.randint(261, 280),
             key.pub(), random.randint(50, 100), EMPTY_PK, 0, sha256(str(random.randint(0, 100000))).digest(), 0, 0))
        self.sign(key)


class MultiChainTestCase(AbstractServer):
    def assertEqual_block(self, expected_block, actual_block):
        """
        Function to assertEqual two blocks
        """
        self.assertTrue(expected_block is not None)
        self.assertTrue(actual_block is not None)
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
