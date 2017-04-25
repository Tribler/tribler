"""
All conversions for the MultiChain Community.
"""
from struct import pack, unpack_from, calcsize

from Tribler.community.multichain.block import MultiChainBlock, block_pack_size, PK_LENGTH, EMPTY_PK
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


# The crawl message format permits future extensions by providing space for a public key and response limit
crawl_request_format = "! {0}s I I ".format(PK_LENGTH)
crawl_request_size = calcsize(crawl_request_format)


class MultiChainConversion(BinaryConversion):
    """
    Class that handles all encoding and decoding of MultiChain messages.
    """
    def __init__(self, community):
        super(MultiChainConversion, self).__init__(community, "\x01")
        from Tribler.community.multichain.community import HALF_BLOCK, CRAWL

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

        return offset + block_pack_size, placeholder.meta.payload.implement(
            MultiChainBlock.unpack(data, offset))

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
