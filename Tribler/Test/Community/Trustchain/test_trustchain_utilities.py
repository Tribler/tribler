"""
File containing utilities used in testing the TrustChain community.
"""
import random
from hashlib import sha256

from Tribler.Core.Utilities.encoding import encode
from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.crypto import ECCrypto
from Tribler.community.trustchain.block import TrustChainBlock


class TestBlock(TrustChainBlock):
    """
    Test Block that simulates a block used in TrustChain.
    Also used in other test files for TrustChain.
    """

    def __init__(self, transaction=None, previous=None):
        crypto = ECCrypto()
        other = crypto.generate_key(u"curve25519").pub().key_to_bin()

        transaction = transaction or {'id': 42}

        if previous:
            self.key = previous.key
            TrustChainBlock.__init__(self, (encode(transaction), previous.public_key, previous.sequence_number + 1,
                                            other, 0, previous.hash, 0, 0))
        else:
            self.key = crypto.generate_key(u"curve25519")
            TrustChainBlock.__init__(self, (
                encode(transaction), self.key.pub().key_to_bin(), random.randint(50, 100), other, 0,
                sha256(str(random.randint(0, 100000))).digest(), 0, 0))
        self.sign(self.key)


class TrustChainTestCase(AbstractServer):
    def assertEqual_block(self, expected_block, actual_block):
        """
        Function to assertEqual two blocks
        """
        crypto = ECCrypto()
        self.assertTrue(expected_block is not None)
        self.assertTrue(actual_block is not None)
        self.assertTrue(crypto.is_valid_public_bin(expected_block.public_key))
        self.assertTrue(crypto.is_valid_public_bin(actual_block.public_key))
        self.assertDictEqual(expected_block.transaction, actual_block.transaction)
        self.assertEqual(expected_block.public_key, actual_block.public_key)
        self.assertEqual(expected_block.sequence_number, actual_block.sequence_number)
        self.assertEqual(expected_block.link_public_key, actual_block.link_public_key)
        self.assertEqual(expected_block.link_sequence_number, actual_block.link_sequence_number)
        self.assertEqual(expected_block.previous_hash, actual_block.previous_hash)
        self.assertEqual(expected_block.signature, actual_block.signature)
