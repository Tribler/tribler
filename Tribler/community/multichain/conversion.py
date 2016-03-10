"""
All conversions for the MultiChain Community.
"""
from struct import pack, unpack_from, calcsize

from Tribler.community.multichain.block import MultiChainBlock, block_pack_size
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket

crawl_request_format = "! i"
crawl_request_size = calcsize(crawl_request_format)


class MultiChainConversion(BinaryConversion):
    """
    Class that handles all encoding and decoding of MultiChain messages.
    """

    def __init__(self, community):
        super(MultiChainConversion, self).__init__(community, "\x01")
        from Tribler.community.multichain.community import SIGNED, HALF_BLOCK, FULL_BLOCK, CRAWL, RESUME

        # Define Request Signature.
        self.define_meta_message(chr(1), community.get_meta_message(SIGNED),
                                 self._encode_half_block, self._decode_half_block)
        self.define_meta_message(chr(2), community.get_meta_message(HALF_BLOCK),
                                 self._encode_half_block, self._decode_half_block)
        self.define_meta_message(chr(3), community.get_meta_message(FULL_BLOCK),
                                 self._encode_full_block, self._decode_full_block)
        self.define_meta_message(chr(4), community.get_meta_message(CRAWL),
                                 self._encode_crawl_request, self._decode_crawl_request)
        self.define_meta_message(chr(5), community.get_meta_message(RESUME),
                                 self._encode_crawl_resume, self._decode_crawl_resume)

    @staticmethod
    def _encode_half_block(message):
        """
        Encode a half block message.
        :param message: Message.impl of HalfBlockPayload.impl
        :return encoding ready to be sent to the network of the message
        """
        return message.payload.block.pack(),

    @staticmethod
    def _decode_half_block(placeholder, offset, data):
        """
        Decode an incoming half block message.
        :param placeholder:
        :param offset: Start of the HalfBlock message in the data.
        :param data: ByteStream containing the message.
        :return: (offset, HalfBlockPayload.impl)
        """
        if len(data) < offset + block_pack_size:
            raise DropPacket("Unable to decode the payload")

        return offset + block_pack_size, placeholder.meta.payload.implement(
            MultiChainBlock.unpack(data, offset))

    @staticmethod
    def _encode_full_block(message):
        """
        Encode a full block response message.
        :param message: Message.impl of FullBlockPayload.impl
        :return encoding ready to be sent to the network of the message
        """
        return message.payload.block_seeder.pack() + message.payload.block_leecher.pack(),

    @staticmethod
    def _decode_full_block(placeholder, offset, data):
        """
        Decode an incoming full block message.
        :param placeholder:
        :param offset: Start of the FullBlock message in the data.
        :param data: ByteStream containing the message.
        :return: (offset, FullBlockPayload.impl)
        """
        if len(data) < offset + block_pack_size*2:
            raise DropPacket("Unable to decode the payload")

        return offset + block_pack_size*2, placeholder.meta.payload.implement(
            MultiChainBlock.unpack(data, offset),
            MultiChainBlock.unpack(data, offset+block_pack_size))

    @staticmethod
    def _encode_crawl_request(message):
        """
        Encode a crawl request message.
        :param message: Message.impl of CrawlRequestPayload.impl
        :return encoding ready to be sent of the network of the message
        """
        return pack(crawl_request_format, message.payload.requested_sequence_number),

    @staticmethod
    def _decode_crawl_request(placeholder, offset, data):
        """
        Decode an incoming crawl request message.
        :param placeholder:
        :param offset: Start of the CrawlRequest message in the data.
        :param data: ByteStream containing the message.
        :return: (offset, CrawlRequest.impl)
        """
        if len(data) < offset + crawl_request_size:
            raise DropPacket("Unable to decode the payload")

        values = unpack_from(crawl_response_format, data, offset)
        offset += crawl_response_size

        return offset + crawl_request_size, \
            placeholder.meta.payload.implement(*unpack_from(crawl_request_format, data, offset))

    @staticmethod
    def _encode_crawl_resume(message):
        """
        Encode a crawl resume message.
        :param message: Message.impl of CrawlResumePayload.impl
        return encoding of the message ready to be sent over the network
        """
        return '',

    @staticmethod
    def _decode_crawl_resume(placeholder, offset, data):
        """
        Decode an incoming crawl resume message.
        :param placeholder:
        :param offset: Start of the CrawlResume message in the data.
        :param data: ByteStream containing the message.
        :return: (offset, CrawlResumePayload.impl)
        """
        return offset, placeholder.meta.payload.implement()
