"""
All conversions for the TrustChain Community.
"""
from struct import pack, unpack_from, calcsize

from Tribler.community.trustchain.block import TrustChainBlock, block_pack_size, PK_LENGTH, EMPTY_PK
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


# The crawl message format permits future extensions by providing space for a public key and response limit
crawl_request_format = "! {0}s l I ".format(PK_LENGTH)
crawl_request_size = calcsize(crawl_request_format)


class TrustChainConversion(BinaryConversion):
    """
    Class that handles all encoding and decoding of TrustChain messages.
    """
    def __init__(self, community):
        super(TrustChainConversion, self).__init__(community, "\x01")
        from Tribler.community.trustchain.community import HALF_BLOCK, CRAWL

        # Define Request Signature.
        self.define_meta_message(chr(1), community.get_meta_message(HALF_BLOCK),
                                 self._encode_half_block, self._decode_half_block)
        self.define_meta_message(chr(2), community.get_meta_message(CRAWL),
                                 self._encode_crawl_request, self._decode_crawl_request)

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

        try:
            block = TrustChainBlock.unpack(data, offset)
        except IndexError:
            raise DropPacket("Invalid block contents")

        return len(data), placeholder.meta.payload.implement(block)

    @staticmethod
    def _encode_crawl_request(message):
        """
        Encode a crawl request message.
        :param message: Message.impl of CrawlRequestPayload.impl
        :return encoding ready to be sent of the network of the message
        """
        return pack(crawl_request_format, EMPTY_PK, message.payload.requested_sequence_number, 10),

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

        who, seq, limit = unpack_from(crawl_request_format, data, offset)

        return offset + crawl_request_size, \
            placeholder.meta.payload.implement(seq)
