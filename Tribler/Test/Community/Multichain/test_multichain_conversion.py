import logging
from hashlib import sha1
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.Multichain.test_multichain_utilities import TestBlock, MultiChainTestCase

from Tribler.community.multichain.conversion import MultiChainConversion
from Tribler.community.multichain.community import SIGNED, HALF_BLOCK, FULL_BLOCK, CRAWL, RESUME
from Tribler.community.multichain.payload import (HalfBlockPayload, FullBlockPayload, CrawlRequestPayload,
                                                  CrawlResumePayload)

from Tribler.dispersy.community import Community
from Tribler.dispersy.authentication import NoAuthentication
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.message import Message, DropPacket
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestConversion(MultiChainTestCase):
    def __init__(self, *args, **kwargs):
        super(TestConversion, self).__init__(*args, **kwargs)
        self.community = TestCommunity()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(TestConversion, self).setUp()
        self.converter = MultiChainConversion(self.community)
        self.block = TestBlock()

    def test_encoding_decoding_half_block(self):
        """
        Test encoding of a signed message
        """
        # Arrange
        meta = self.community.get_meta_message(SIGNED)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(self.block,))
        # Act
        encoded_message = self.converter._encode_half_block(message)[0]
        result = self.converter._decode_half_block(TestPlaceholder(meta), 0, encoded_message)[1]

        # Assert
        self.assertEqual_block(block, result.block)

    def test_encoding_decoding_half_block_big_number(self):
        """
        Test if a responder can send a signature message with big total_up and down.
        """
        # Arrange
        meta = self.community.get_meta_message(SIGNED)
        block = TestBlock()
        block.total_up_requester = pow(2, 63)
        block.total_down_requester = pow(2, 62)
        block.total_up_responder = pow(2, 61)
        block.total_down_responder = pow(2, 60)

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(self.block,))
        # Act
        encoded_message = self.converter._encode_half_block(message)[0]
        result = self.converter._decode_half_block(TestPlaceholder(meta), 0, encoded_message)[1]

        # Assert
        self.assertEqual_block(self.block, result.block)

    def test_decoding_half_block_wrong_size(self):
        """
        Test decoding a signature message with wrong size
        """
        # Arrange
        meta = self.community.get_meta_message(SIGNED)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(self.block,))
        # Act
        encoded_message = self.converter._encode_half_block(message)[0]
        # Act & Assert
        with self.assertRaises(DropPacket):
            # Remove a bit of message.
            self.converter._decode_half_block(TestPlaceholder(meta), 0, encoded_message[:-10])[1]

    def test_encoding_decoding_full_block(self):
        """
        Test encoding of a signed message
        """
        # Arrange
        meta = self.community.get_meta_message(FULL_BLOCK)
        block_l = TestBlock()
        block_r = TestBlock()

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(block_l, block_r))
        # Act
        encoded_message = self.converter._encode_full_block(message)[0]
        result = self.converter._decode_full_block(TestPlaceholder(meta), 0, encoded_message)[1]

        # Assert
        self.assertEqual_block(block_l, result.block_this)
        self.assertEqual_block(block_r, result.block_that)

    def test_decoding_full_block_wrong_size(self):
        """
        Test encoding of a signed message
        """
        # Arrange
        meta = self.community.get_meta_message(FULL_BLOCK)
        block_l = TestBlock()
        block_r = TestBlock()

        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=(block_l, block_r))
        # Act
        encoded_message = self.converter._encode_full_block(message)[0]
        # Act & Assert
        with self.assertRaises(DropPacket):
            # Remove a bit of message.
            self.converter._decode_full_block(TestPlaceholder(meta), 0, encoded_message[:-10])[1]

    def test_encoding_decoding_crawl_request(self):
        """
        Test if a requester can send a crawl request message.
        """
        # Arrange
        meta = self.community.get_meta_message(CRAWL)
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
        meta = self.community.get_meta_message(CRAWL)
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
        meta = self.community.get_meta_message(CRAWL)
        message = meta.impl(distribution=(self.community.claim_global_time(),),
                            payload=())
        # Act
        encoded_message = self.converter._encode_crawl_request(message)[0]

        result = self.converter._decode_crawl_request(TestPlaceholder(meta), 0, encoded_message)[1]
        # Assert
        self.assertEqual(-1, result.requested_sequence_number)


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
            Message(self, SIGNED,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    HalfBlockPayload(),
                    lambda: None,
                    lambda: None),
            Message(self, HALF_BLOCK,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    HalfBlockPayload(),
                    lambda: None,
                    lambda: None),
            Message(self, FULL_BLOCK,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    FullBlockPayload(),
                    lambda: None,
                    lambda: None),
            Message(self, CRAWL,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlRequestPayload(),
                    lambda: None,
                    lambda: None),
            Message(self, RESUME,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlResumePayload(),
                    lambda: None,
                    lambda: None)]

    def initiate_conversions(self):
        return [DefaultConversion(self), MultiChainConversion(self)]
