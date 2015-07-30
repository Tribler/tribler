"""
File contains all conversions for the MultiChain Community.
"""
from struct import pack, unpack_from, calcsize

from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket

"""
Hash length used in the MultiChain Community
"""
# Calculated with sha1("").digest_size
HASH_LENGTH = 20
SIG_LENGTH = 64
PK_LENGTH = 74
"""
Formatting of the signature packet
"""
# TotalUp TotalDown Sequence_number, previous_hash
append_format = 'Q Q i ' + str(HASH_LENGTH) + 's'
# [Up, Down, TotalUpRequester, TotalDownRequester, sequence_number_requester, previous_hash_requester,
#   TotalUpResponder, TotalDownResponder, sequence_number_responder, previous_hash_responder]
signature_format = ' '.join(['!I I', append_format, append_format])
signature_size = calcsize(signature_format)
append_size = calcsize(append_format)

block_request_format = 'i'
block_request_size = calcsize(block_request_format)

# [signature, pk]
authentication_format = str(PK_LENGTH) + 's ' + str(SIG_LENGTH) + 's '
# [Up, Down, TotalUpRequester, TotalDownRequester, sequence_number_requester, previous_hash_requester,
#   TotalUpResponder, TotalDownResponder, sequence_number_responder, previous_hash_responder,
#   signature_requester, pk_requester, signature_responder, pk_responder]
block_response_format = signature_format + authentication_format + authentication_format
block_response_size = calcsize(block_response_format)


class MultiChainConversion(BinaryConversion):
    """
    Class that handles all encoding and decoding of MultiChain messages.
    """

    def __init__(self, community):
        super(MultiChainConversion, self).__init__(community, "\x01")
        from Tribler.community.multichain.community import SIGNATURE, BLOCK_REQUEST, BLOCK_RESPONSE

        # Define Request Signature.
        self.define_meta_message(chr(1), community.get_meta_message(SIGNATURE),
                                 self._encode_signature, self._decode_signature)
        self.define_meta_message(chr(2), community.get_meta_message(BLOCK_REQUEST),
                                 self._encode_block_request, self._decode_block_request)
        self.define_meta_message(chr(3), community.get_meta_message(BLOCK_RESPONSE),
                                 self._encode_block_response, self._decode_block_response)

    def _encode_signature(self, message):
        """
        Encode the signature message
        :param message: Message.impl of SIGNATURE
        :return: encoding ready to be sent of the network.
        """
        payload = message.payload
        return pack(signature_format, *(payload.up, payload.down,
                                        payload.total_up_requester, payload.total_down_requester,
                                        payload.sequence_number_requester, payload.previous_hash_requester,
                                        payload.total_up_responder, payload.total_down_responder,
                                        payload.sequence_number_responder, payload.previous_hash_responder)),

    def _decode_signature(self, placeholder, offset, data):
        """
        Decode an incoming signature message
        :param placeholder:
        :param offset: Start of the SIGNATURE message in the data.
        :param data: ByteStream containing the message.
        :return: (offset, SIGNATURE.impl)
        """
        if len(data) < offset + signature_size:
            raise DropPacket("Unable to decode the payload")

        values = unpack_from(signature_format, data, offset)
        offset += signature_size

        return \
            offset, placeholder.meta.payload.implement(*values)

    def _encode_block_request(self, message):
        """
        Encode a block request message.
        :param message: Message.impl of BlockRequestPayload.impl
        return encoding ready to be sent of the network of the message
        """
        return pack(block_request_format, message.payload.requested_sequence_number),

    def _decode_block_request(self, placeholder, offset, data):
        """
        Decode an incoming block request message.
        :param placeholder:
        :param offset: Start of the BlockRequest message in the data.
        :param data: ByteStream containing the message.
        :return: (offset, BlockRequest.impl)
        """
        if len(data) < offset + block_request_size:
            raise DropPacket("Unable to decode the payload")

        values = unpack_from(block_request_format, data, offset)
        offset += block_request_size

        return offset, placeholder.meta.payload.implement(*values)

    def _encode_block_response(self, message):
        """
        Encode a block response message.
        :param message: Message.impl of BlockResponsePayload.impl
        :return encoding ready to be sent to the network of the message
        """
        payload = message.payload
        return encode_block(payload),

    def _decode_block_response(self, placeholder, offset, data):
        """
        Decode an incoming block response message.
        :param placeholder:
        :param offset: Start of the BlockResponse message in the data.
        :param data: ByteStream containing the message.
        :return: (offset, BlockResponse.impl)
        """
        if len(data) < offset + block_response_size:
            raise DropPacket("Unable to decode the payload")

        values = unpack_from(block_response_format, data, offset)
        offset += block_response_size

        return \
            offset, placeholder.meta.payload.implement(*values)


def split_function(payload):
    """
    This function splits the SIGNATURE MESSAGE in parts.
    The first to be signed by the requester, and the second the whole message to be signed by the responder
    :param payload: Encoded message to be split
    :return: (first_part, whole)
    """
    return payload[:-append_size], payload


def encode_block(payload):
    """
    This function encodes a block.
    :param payload: Payload containing the data as properties
    :return: encoding
    """
    """ Test code sometimes run a different curve with a different key length resulting in hard to catch bugs."""
    assert len(payload.public_key_requester) == PK_LENGTH
    assert len(payload.public_key_responder) == PK_LENGTH
    return pack(block_response_format, *(payload.up, payload.down,
                                         payload.total_up_requester, payload.total_down_requester,
                                         payload.sequence_number_requester, payload.previous_hash_requester,
                                         payload.total_up_responder, payload.total_down_responder,
                                         payload.sequence_number_responder, payload.previous_hash_responder,
                                         payload.public_key_requester, payload.signature_requester,
                                         payload.public_key_responder, payload.signature_responder,))