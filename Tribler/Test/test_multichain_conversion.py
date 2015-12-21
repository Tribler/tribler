import logging
from hashlib import sha1
from struct import unpack

from Tribler.Test.test_multichain_utilities import TestBlock, MultiChainTestCase
from Tribler.community.multichain.conversion import MultiChainConversion, split_function, signature_format, \
    append_format

from Tribler.community.multichain.community import SIGNATURE, CRAWL_REQUEST, CRAWL_RESPONSE, CRAWL_RESUME
from Tribler.community.multichain.payload import SignaturePayload, CrawlRequestPayload, CrawlResponsePayload, CrawlResumePayload, EMPTY_HASH

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

    def test_encoding_decoding_signature(self):
        """
        Test if a responder can send a signature message.
        This only contains requester and responder data.
        """
        # Arrange
        converter = MultiChainConversion(self.community)

        meta = self.community.get_meta_message(SIGNATURE)
        block = TestBlock()

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(block.generate_signature_payload()))
        # Act
        encoded_message = converter._encode_signature(message)[0]

        result = converter._decode_signature(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual_signature_payload(block, result)

    def test_encoding_decoding_signature_big_number(self):
        """
        Test if a responder can send a signature message with big total_up and down.
        """
        # Arrange
        converter = MultiChainConversion(self.community)

        meta = self.community.get_meta_message(SIGNATURE)
        block = TestBlock()
        block.total_up_requester = pow(2, 63)
        block.total_down_requester = pow(2, 62)
        block.total_up_responder = pow(2, 61)
        block.total_down_responder = pow(2, 60)

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(block.generate_signature_payload()))
        # Act
        encoded_message = converter._encode_signature(message)[0]

        result = converter._decode_signature(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual_signature_payload(block, result)

    def test_encoding_decoding_signature_requester(self):
        """
        Test if a requester can send a signature message.
        This only contains requester data.
        """
        # Arrange
        converter = MultiChainConversion(self.community)

        meta = self.community.get_meta_message(SIGNATURE)
        block = TestBlock()

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(block.generate_requester()))
        # Act
        encoded_message = converter._encode_signature(message)[0]

        result = converter._decode_signature(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual_signature_request(block, result)
        self.assertEqual(0, result.total_up_responder)
        self.assertEqual(0, result.total_down_responder)
        self.assertEqual(-1, result.sequence_number_responder)
        self.assertEqual(EMPTY_HASH, result.previous_hash_responder)

    def test_decoding_signature_wrong_size(self):
        """
        Test decoding a signature message with wrong size
        """
        # Arrange
        converter = MultiChainConversion(self.community)
        meta = self.community.get_meta_message(SIGNATURE)
        block = TestBlock()
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(block.generate_signature_payload()))
        # Act
        encoded_message = converter._encode_signature(message)[0]
        # Act & Assert
        with self.assertRaises(DropPacket):
            # Remove a bit of message.
            converter._decode_signature(TestPlaceholder(meta), 0, encoded_message[:-10])[1]

    def test_encoding_decoding_crawl_request(self):
        """
        Test if a requester can send a crawl request message.
        """
        # Arrange
        converter = MultiChainConversion(self.community)
        meta = self.community.get_meta_message(CRAWL_REQUEST)

        requested_sequence_number = 500

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(requested_sequence_number,))
        # Act
        encoded_message = converter._encode_crawl_request(message)[0]

        result = converter._decode_crawl_request(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual(requested_sequence_number, result.requested_sequence_number)

    def test_decoding_crawl_request_wrong_size(self):
        """
        Test if a DropPacket is raised when the crawl request size is wrong.
        """
        # Arrange
        converter = MultiChainConversion(self.community)
        meta = self.community.get_meta_message(CRAWL_REQUEST)

        requested_sequence_number = 500

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(requested_sequence_number,))
        encoded_message = converter._encode_crawl_request(message)[0]

        # Act & Assert
        with self.assertRaises(DropPacket):
            # Remove a bit of message.
            result = converter._decode_crawl_request(TestPlaceholder(meta), 0, encoded_message[:-10])[1]

    def test_encoding_decoding_crawl_request_empty(self):
        """
        Test if a requester can send a crawl request message without specifying the sequence number.
        """
        # Arrange
        converter = MultiChainConversion(self.community)
        meta = self.community.get_meta_message(CRAWL_REQUEST)

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=())
        # Act
        encoded_message = converter._encode_crawl_request(message)[0]

        result = converter._decode_crawl_request(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual(-1, result.requested_sequence_number)

    def test_encoding_decoding_crawl_response(self):
        """
        Test if a responder can send a crawl_response message.
        This only contains requester and responder data.
        """
        # Arrange
        converter = MultiChainConversion(self.community)

        meta = self.community.get_meta_message(CRAWL_RESPONSE)
        block = TestBlock()

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(block.generate_block_payload()))
        # Act
        encoded_message = converter._encode_crawl_response(message)[0]
        result = converter._decode_crawl_response(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual(len(block.public_key_requester), len(result.public_key_requester))
        self.assertTrue(self.community.crypto.is_valid_public_bin(block.public_key_requester))
        self.assertTrue(self.community.crypto.is_valid_public_bin(block.public_key_responder))

        self.assertEqual_block(block, result)

    def test_decoding_crawl_response_wrong_size(self):
        """
        Test if a DropPacket is raised when the crawl response size is wrong.
        """
        # Arrange
        converter = MultiChainConversion(self.community)

        meta = self.community.get_meta_message(CRAWL_RESPONSE)
        block = TestBlock()

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(block.generate_block_payload()))
        # Act
        encoded_message = converter._encode_crawl_response(message)[0]
        with self.assertRaises(DropPacket):
            # Remove a bit of message.
            converter._decode_crawl_response(TestPlaceholder(meta), 0, encoded_message[:-10])[1]

    def test_split_function(self):
        """
        Test the MultiChain split function.
        """
        # Arrange
        converter = MultiChainConversion(self.community)

        meta = self.community.get_meta_message(SIGNATURE)
        block = TestBlock()

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=tuple(block.generate_signature_payload()))
        # Act
        encoded_message = converter._encode_signature(message)[0]
        result = split_function(encoded_message)
        # Assert
        values = unpack(signature_format[:-len(append_format)], result[0])
        self.assertEqual(6, len(values))
        self.assertEqual(block.up, values[0])
        self.assertEqual(block.down, values[1])
        self.assertEqual(block.total_up_requester, values[2])
        self.assertEqual(block.total_down_requester, values[3])
        self.assertEqual(block.sequence_number_requester, values[4])
        self.assertEqual(block.previous_hash_requester, values[5])

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
                    self._community_do_nothing,
                    self._community_do_nothing),
            Message(self, CRAWL_REQUEST,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlRequestPayload(),
                    self._community_do_nothing,
                    self._community_do_nothing),
            Message(self, CRAWL_RESPONSE,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlResponsePayload(),
                    self._community_do_nothing,
                    self._community_do_nothing),
            Message(self, CRAWL_RESUME,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlResumePayload(),
                    self._community_do_nothing,
                    self._community_do_nothing)]

    def _community_do_nothing(self):
        """
        Function that does nothing to implement for a community
        """
        return

    def initiate_conversions(self):
        return [DefaultConversion(self), MultiChainConversion(self)]
