"""
File containing utilities used in testing the double entry community.
"""

import random

from hashlib import sha256

from Tribler.dispersy.crypto import ECCrypto

from Tribler.Test.test_as_server import AbstractServer

from Tribler.community.multichain.conversion import EMPTY_HASH
from Tribler.community.multichain.database import DatabaseBlock


class TestBlock(DatabaseBlock):
    """
    Test Block that simulates a block message used in MultiChain.
    Also used in other test files for MultiChain.
    """

    def __init__(self):
        crypto = ECCrypto()
        key_requester = crypto.generate_key(u"curve25519")
        key_responder = crypto.generate_key(u"curve25519")

        # Random payload but unique numbers.
        sequence_number_requester = random.randint(50, 100)
        sequence_number_responder = random.randint(101, 200)
        up = random.randint(201, 220)
        down = random.randint(221, 240)
        total_up_requester = random.randint(241, 260)
        total_down_requester = random.randint(261, 280)
        total_up_responder = random.randint(281, 300)
        total_down_responder = random.randint(301, 320)

        # A random hash is generated for the previous hash. It is only used to test if a hash can be persisted.
        previous_hash_requester = sha256(str(random.randint(0, 100000))).digest()
        public_key_requester = crypto.key_to_bin(key_requester.pub())
        signature_requester = crypto.create_signature(key_requester, encode_signing_format(
           [up, down,
            total_up_requester, total_down_requester,
            sequence_number_requester, previous_hash_requester]))
        # A random hash is generated for the  hash.
        # TODO: Use the actual hash
        hash_requester = sha256(str(random.randint(0, 100000))).digest()
        # A random hash is generated for the previous hash. It is only used to test if a hash can be persisted.
        previous_hash_responder = sha256(str(random.randint(100001, 200000))).digest()
        public_key_responder = crypto.key_to_bin(key_responder.pub())
        signature_responder = crypto.create_signature(key_responder, encode_signing_format(
            [up, down,
             total_up_requester, total_down_requester,
             sequence_number_requester, previous_hash_requester,
             total_up_responder, total_down_responder,
             sequence_number_responder, previous_hash_responder]))
        # A random hash is generated for the  hash.
        # TODO: Use the actual hash
        hash_responder = sha256(str(random.randint(0, 100000))).digest()

        DatabaseBlock.__init__(self,
                               (public_key_requester, public_key_responder, up, down,

                                total_up_requester, total_down_requester,
                                sequence_number_requester, previous_hash_requester,
                                signature_requester, hash_requester,

                                total_up_responder, total_down_responder,
                                sequence_number_responder, previous_hash_responder,
                                signature_responder, hash_responder,

                                None))

    def generate_requester(self):
        return [self.up, self.down,
                self.total_up_requester, self.total_down_requester,
                self.sequence_number_requester, self.previous_hash_requester]

    def _generate_responder(self):
        return [self.total_up_responder, self.total_down_responder,
                self.sequence_number_responder, self.previous_hash_responder]

    def generate_signature_payload(self):
        return self.generate_requester() + self._generate_responder()

    def generate_block_payload(self):
        return self.generate_requester() + self._generate_responder() + [self.public_key_requester,
                                                                         self.signature_requester,
                                                                         self.public_key_responder,
                                                                         self.signature_responder]


class MultiChainTestCase(AbstractServer):
    def __init__(self, *args, **kwargs):
        super(MultiChainTestCase, self).__init__(*args, **kwargs)

    def setUp(self):
        super(MultiChainTestCase, self).setUp()

    def assertEqual_block(self, expected_block, actual_block):
        """
        Function to assertEqual two blocks
        """
        self.assertEqual_signature_payload(expected_block, actual_block)
        self._assertEqual_requester_signature(expected_block, actual_block)
        self._assertEqual_responder_signature(expected_block, actual_block)

    def assertEqual_signature_payload(self, expected_payload, actual_payload):
        """
        Checks a signature message payload
        """
        self.assertEqual_signature_request(expected_payload, actual_payload)
        """ Check payload part of responder"""
        self.assertEqual(expected_payload.total_up_responder, actual_payload.total_up_responder)
        self.assertEqual(expected_payload.total_down_responder, actual_payload.total_down_responder)
        self.assertEqual(expected_payload.sequence_number_responder, actual_payload.sequence_number_responder)
        self.assertEqual(expected_payload.previous_hash_responder, actual_payload.previous_hash_responder)

    def assertEqual_signature_request(self, expected_payload, actual_payload):
        """
        Checks a signature message payload
        """
        """ Check interaction part of requester"""
        self.assertEqual(expected_payload.up, actual_payload.up)
        self.assertEqual(expected_payload.down, actual_payload.down)
        """ Check payload part of requester"""
        self.assertEqual(expected_payload.total_up_requester, actual_payload.total_up_requester)
        self.assertEqual(expected_payload.total_down_requester, actual_payload.total_down_requester)
        self.assertEqual(expected_payload.sequence_number_requester, actual_payload.sequence_number_requester)
        self.assertEqual(expected_payload.previous_hash_requester, actual_payload.previous_hash_requester)

    def _assertEqual_requester_signature(self, expected_block, actual_block):
        self.assertEqual(expected_block.signature_requester, actual_block.signature_requester)
        self.assertEqual(expected_block.public_key_requester, actual_block.public_key_requester)

    def _assertEqual_responder_signature(self, expected_block, actual_block):
        self.assertEqual(expected_block.signature_responder, actual_block.signature_responder)
        self.assertEqual(expected_block.public_key_responder, actual_block.public_key_responder)


def encode_signing_format(data):
    """
    Prepare a iterable for singing.
    :param data: Iterable with objects transformable to string
    :return: string to be signed containing the data.
    """
    return ".".join(map(str, data))
