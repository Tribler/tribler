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
        from Tribler.community.trustchain.community import HALF_BLOCK, CRAWL, HALF_BLOCK_BROADCAST,\
            BLOCK_PAIR, BLOCK_PAIR_BROADCAST

        # Define Request Signature.
        self.define_meta_message(chr(1), community.get_meta_message(HALF_BLOCK),
                                 self._encode_half_block, self._decode_half_block)
        self.define_meta_message(chr(2), community.get_meta_message(HALF_BLOCK_BROADCAST),
                                 self._encode_half_block, self._decode_half_block)
        self.define_meta_message(chr(3), community.get_meta_message(BLOCK_PAIR),
                                 self._encode_block_pair, self._decode_block_pair)
        self.define_meta_message(chr(4), community.get_meta_message(BLOCK_PAIR_BROADCAST),
                                 self._encode_block_pair, self._decode_block_pair)
        self.define_meta_message(chr(5), community.get_meta_message(CRAWL),
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
            _, block = TrustChainBlock.unpack(data, offset)
        except (IndexError, ValueError):
            raise DropPacket("Invalid block contents")

        return len(data), placeholder.meta.payload.implement(block)

    @staticmethod
    def _encode_block_pair(message):
        """
        Encode a half block message.
        :param message: Message.impl of HalfBlockPayload.impl
        :return encoding ready to be sent to the network of the message
        """
        return message.payload.block1.pack() + message.payload.block2.pack(),

    @staticmethod
    def _decode_block_pair(placeholder, offset, data):
        """
        Decode an incoming block pair message.
        :param placeholder:
        :param offset: Start of the BlockPair message in the data.
        :param data: ByteStream containing the message.
        :return: (offset, BlockPairPayload.impl)
        """
        if len(data) < offset + block_pack_size * 2:
            raise DropPacket("Unable to decode the payload")

        try:
            new_offset, block1 = TrustChainBlock.unpack(data, offset)
            _, block2 = TrustChainBlock.unpack(data, new_offset)
        except (IndexError, ValueError):
            raise DropPacket("Invalid block contents")

        return len(data), placeholder.meta.payload.implement(block1, block2)

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
