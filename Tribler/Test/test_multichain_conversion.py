import logging
from hashlib import sha1
from struct import unpack
from Tribler.Test.test_multichain_utilities import TestBlock, MultiChainTestCase
from Tribler.community.multichain.conversion import (MultiChainConversion, split_function, signature_format,
                                                     append_format)
from Tribler.community.multichain.community import SIGNATURE, CRAWL_REQUEST, CRAWL_RESPONSE, CRAWL_RESUME
from Tribler.community.multichain.payload import (SignaturePayload, CrawlRequestPayload, CrawlResponsePayload,
                                                  CrawlResumePayload)
from Tribler.community.multichain.conversion import EMPTY_HASH
from Tribler.dispersy.community import Community
from Tribler.dispersy.authentication import NoAuthentication
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.message import Message, DropPacket
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.crypto import ECCrypto


class TestConversion(MultiChainTestCase):
    def __init__(self, *args, **kwargs):
        super(TestConversion, self).__init__(*args, **kwargs)
        self.community = TestCommunity()

    def setUp(self):
        super(TestConversion, self).setUp()
        self.converter = MultiChainConversion(self.community)
        self.block = TestBlock()

    def test_encoding_decoding_signature(self):
        """
        Test if a responder can send a signature message.
        This only contains requester and responder data.
        """
        # Arrange
        meta = self.community.get_meta_message(SIGNATURE)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(self.block.generate_signature_payload()))
        # Act
        encoded_message = self.converter._encode_signature(message)[0]
        result = self.converter._decode_signature(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual_signature_payload(self.block, result)

    def test_encoding_decoding_signature_big_number(self):
        """
        Test if a responder can send a signature message with big total_up and down.
        """
        # Arrange
        meta = self.community.get_meta_message(SIGNATURE)
        self.block.total_up_requester = pow(2, 63)
        self.block.total_down_requester = pow(2, 62)
        self.block.total_up_responder = pow(2, 61)
        self.block.total_down_responder = pow(2, 60)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(self.block.generate_signature_payload()))
        # Act
        encoded_message = self.converter._encode_signature(message)[0]
        result = self.converter._decode_signature(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual_signature_payload(self.block, result)

    def test_encoding_decoding_signature_requester(self):
        """
        Test if a requester can send a signature message.
        This only contains requester data.
        """
        # Arrange
        meta = self.community.get_meta_message(SIGNATURE)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(self.block.generate_requester()))
        # Act
        encoded_message = self.converter._encode_signature(message)[0]
        result = self.converter._decode_signature(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual_signature_request(self.block, result)
        self.assertEqual(0, result.total_up_responder)
        self.assertEqual(0, result.total_down_responder)
        self.assertEqual(-1, result.sequence_number_responder)
        self.assertEqual(EMPTY_HASH, result.previous_hash_responder)

    def test_decoding_signature_wrong_size(self):
        """
        Test decoding a signature message with wrong size
        """
        # Arrange
        meta = self.community.get_meta_message(SIGNATURE)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(self.block.generate_signature_payload()))
        # Act
        encoded_message = self.converter._encode_signature(message)[0]
        # Act & Assert
        with self.assertRaises(DropPacket):
            # Remove a bit of message.
            self.converter._decode_signature(TestPlaceholder(meta), 0, encoded_message[:-10])[1]

    def test_encoding_decoding_crawl_request(self):
        """
        Test if a requester can send a crawl request message.
        """
        # Arrange
        meta = self.community.get_meta_message(CRAWL_REQUEST)
        requested_sequence_number = 500

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(requested_sequence_number,))
        # Act
        encoded_message = self.converter._encode_crawl_request(message)[0]

        result = self.converter._decode_crawl_request(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual(requested_sequence_number, result.requested_sequence_number)

    def test_decoding_crawl_request_wrong_size(self):
        """
        Test if a DropPacket is raised when the crawl request size is wrong.
        """
        # Arrange
        meta = self.community.get_meta_message(CRAWL_REQUEST)
        requested_sequence_number = 500
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(requested_sequence_number,))
        encoded_message = self.converter._encode_crawl_request(message)[0]

        # Act & Assert
        with self.assertRaises(DropPacket):
            # Remove a bit of message.
            result = self.converter._decode_crawl_request(TestPlaceholder(meta), 0, encoded_message[:-10])[1]

    def test_encoding_decoding_crawl_request_empty(self):
        """
        Test if a requester can send a crawl request message without specifying the sequence number.
        """
        # Arrange
        meta = self.community.get_meta_message(CRAWL_REQUEST)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=())
        # Act
        encoded_message = self.converter._encode_crawl_request(message)[0]

        result = self.converter._decode_crawl_request(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual(-1, result.requested_sequence_number)

    def test_encoding_decoding_crawl_response(self):
        """
        Test if a responder can send a crawl_response message.
        This only contains requester and responder data.
        """
        # Arrange
        meta = self.community.get_meta_message(CRAWL_RESPONSE)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(self.block.generate_block_payload()))
        # Act
        encoded_message = self.converter._encode_crawl_response(message)[0]
        result = self.converter._decode_crawl_response(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual(len(self.block.public_key_requester), len(result.public_key_requester))
        self.assertTrue(self.community.crypto.is_valid_public_bin(self.block.public_key_requester))
        self.assertTrue(self.community.crypto.is_valid_public_bin(self.block.public_key_responder))

        self.assertEqual_block(self.block, result)

    def test_decoding_crawl_response_wrong_size(self):
        """
        Test if a DropPacket is raised when the crawl response size is wrong.
        """
        # Arrange
        meta = self.community.get_meta_message(CRAWL_RESPONSE)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(self.block.generate_block_payload()))
        # Act
        encoded_message = self.converter._encode_crawl_response(message)[0]
        with self.assertRaises(DropPacket):
            # Remove a bit of message.
            self.converter._decode_crawl_response(TestPlaceholder(meta), 0, encoded_message[:-10])[1]

    def test_split_function(self):
        """
        Test the MultiChain split function.
        """
        # Arrange
        meta = self.community.get_meta_message(SIGNATURE)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(self.block.generate_signature_payload()))
        # Act
        encoded_message = self.converter._encode_signature(message)[0]
        result = split_function(encoded_message)
        # Assert
        values = unpack(signature_format[:-len(append_format)], result[0])
        self.assertEqual(6, len(values))
        self.assertEqual(self.block.up, values[0])
        self.assertEqual(self.block.down, values[1])
        self.assertEqual(self.block.total_up_requester, values[2])
        self.assertEqual(self.block.total_down_requester, values[3])
        self.assertEqual(self.block.sequence_number_requester, values[4])
        self.assertEqual(self.block.previous_hash_requester, values[5])

        self.assertEqual(encoded_message, result[1])


class TestPlaceholder:
    def __init__(self, meta):
        self.meta = meta


class TestCommunity(Community):
    crypto = ECCrypto()

    def __init__(self):
        self.key = self.crypto.generate_key(u"medium")
        self.pk = self.crypto.key_to_bin(self.key.pub())

        self.meta_message_cache = {}

        self._cid = sha1(self.pk).digest()
        self._meta_messages = {}
        self._initialize_meta_messages()

        self._global_time = 0
        self._do_pruning = False
        self._logger = logging.getLogger(self.__class__.__name__)

        self._conversions = self.initiate_conversions()

    def initiate_meta_messages(self):
        return super(TestCommunity, self).initiate_meta_messages() + [
            Message(self, SIGNATURE,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    SignaturePayload(),
                    lambda: None,
                    lambda: None),
            Message(self, CRAWL_REQUEST,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlRequestPayload(),
                    lambda: None,
                    lambda: None),
            Message(self, CRAWL_RESPONSE,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlResponsePayload(),
                    lambda: None,
                    lambda: None),
            Message(self, CRAWL_RESUME,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlResumePayload(),
                    lambda: None,
                    lambda: None)]

    def initiate_conversions(self):
        return [DefaultConversion(self), MultiChainConversion(self)]
