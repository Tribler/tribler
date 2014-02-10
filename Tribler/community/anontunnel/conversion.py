import logging
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.community.anontunnel.payload import *
from Tribler.community.anontunnel.globals import *
import struct

logger = logging.getLogger(__name__)

#-----------------------------------------------------------------------------
#: enable verbose print statements.
DEBUG = True

#: struct format lookup for specific word sizes.
STRUCT_FMT = {
    8  : 'B',   # unsigned char
    16 : 'H',   # unsigned short
    32 : 'I',   # unsigned int
}

#-----------------------------------------------------------------------------
def int_to_words(int_val, num_words=4, word_size=32):
    """
    @param int_val: an arbitrary length Python integer to be split up.
        Network byte order is assumed. Raises an IndexError if width of
        integer (in bits) exceeds word_size * num_words.

    @param num_words: number of words expected in return value tuple.

    @param word_size: size/width of individual words (in bits).

    @return: a list of fixed width words based on provided parameters.
    """
    max_int = 2 ** (word_size*num_words) - 1
    max_word_size = 2 ** word_size - 1

    if not 0 <= int_val <= max_int:
        raise IndexError('integer %r is out of bounds!' % hex(int_val))

    words = []
    for _ in range(num_words):
        word = int_val & max_word_size
        words.append(int(word))
        int_val >>= word_size
    words.reverse()

    return words

#-----------------------------------------------------------------------------
def int_to_packed(int_val, width=128, word_size=32):
    """
    @param int_val: an arbitrary sized Python integer to be packed.

    @param width: expected maximum with of an integer. Can be any size but
        should be divide by word_size without a remainder.

    @param word_size: size/width of individual words (in bits).
        Valid sizes are 8, 16 and 32 bits.

    @return: a (network byte order) packed string equivalent to integer value.
    """
    num_words = width / word_size
    words = int_to_words(int_val, num_words, word_size)

    try:
        fmt = '>%d%s' % (num_words, STRUCT_FMT[word_size])
        #DEBUG: print 'format:', fmt
    except KeyError:
        raise ValueError('unsupported word size: %d!' % word_size)

    return struct.pack(fmt, *words)

#-----------------------------------------------------------------------------
def packed_to_int(packed_int, width=128, word_size=32):
    """
    @param packed_int: a packed string to be converted to an abritrary size
        Python integer. Network byte order is assumed.

    @param width: expected maximum width of return value integer. Can be any
        size but should divide by word_size equally without remainder.

    @param word_size: size/width of individual words (in bits).
        Valid sizes are 8, 16 and 32 bits.

    @return: an arbitrary sized Python integer.
    """
    num_words = width / word_size

    try:
        fmt = '>%d%s' % (num_words, STRUCT_FMT[word_size])
        #DEBUG: print 'format:', fmt
    except KeyError:
        raise ValueError('unsupported word size: %d!' % word_size)

    words = list(struct.unpack(fmt, packed_int))
    words.reverse()

    int_val = 0
    for i, num in enumerate(words):
        word = num
        word = word << word_size * i
        int_val = int_val | word

    return int_val

class ProxyConversion(BinaryConversion):
    def __init__(self, community):
        super(ProxyConversion, self).__init__(community, "\x01")

        self.define_meta_message(
            chr(1),
            community.get_meta_message(u"stats")
            , self._encode_stats
            , self._decode_stats
        )

    @staticmethod
    def _encode_stats(message):
        return encode(message.payload.stats),

    @staticmethod
    def _decode_stats(placeholder, offset, data):
        offset, stats = decode(data, offset)

        return offset, placeholder.meta.payload.implement(stats)

class CustomProxyConversion():

    def __init__(self):
        self.encode_functions = {
            MESSAGE_CREATE: self.__encode_create,
            MESSAGE_CREATED: self.__encode_created,
            MESSAGE_EXTEND: self.__encode_extend,
            MESSAGE_EXTENDED: self.__encode_extended,
            MESSAGE_DATA: self.__encode_data,
            MESSAGE_PING: lambda message: ''
        }

        self.decode_functions = {
            MESSAGE_CREATE: self.__decode_create,
            MESSAGE_CREATED: self.__decode_created,
            MESSAGE_EXTEND: self.__decode_extend,
            MESSAGE_EXTENDED: self.__decode_extended,
            MESSAGE_DATA: self.__decode_data,
            MESSAGE_PING: lambda socket_buffer, offset: PingMessage()
        }

    def encode(self, message_type, message):
        return message_type + self.encode_functions[message_type](message)

    def decode(self, data, offset=0):
        message_type = data[offset]
        assert message_type > 0
        return message_type, self.decode_functions[message_type](data, offset + 1)

    @staticmethod
    def get_circuit_and_data(message_buffer, offset=0):
        circuit_id, = struct.unpack_from("!L", message_buffer, offset)
        offset += 4

        return circuit_id, message_buffer[offset:]

    @staticmethod
    def get_type(data):
        return data[0]

    @staticmethod
    def add_circuit(data, new_id):
        return struct.pack("!L", new_id) + data

    @staticmethod
    def __encode_extend(extend_message):
        host = extend_message.host if extend_message.host else ''
        port = extend_message.port if extend_message.port else 0

        key = extend_message.key

        data = struct.pack("!LL", len(host), port) + host + key
        return data

    @staticmethod
    def __decode_extend(message_buffer, offset=0):
        if len(message_buffer) < offset + 8:
            raise ValueError("Cannot unpack HostLength/Port, insufficient packet size")
        host_length, port = struct.unpack_from("!LL", message_buffer, offset)
        offset += 8

        if len(message_buffer) < offset + host_length:
            raise ValueError("Cannot unpack Host, insufficient packet size")
        host = message_buffer[offset:offset + host_length]
        offset += host_length

        key = message_buffer[offset:]

        extend_with = (host, port) if host and port else None
        return ExtendMessage(extend_with, key)

    @staticmethod
    def __encode_data(data_message):
        if data_message.destination is None:
            (host, port) = ("0.0.0.0", 0)
        else:
            (host, port) = data_message.destination

        if data_message.origin is None:
            origin = ("0.0.0.0", 0)
        else:
            origin = data_message.origin

        return struct.pack("!LLLLL", len(host), port, len(origin[0]), origin[1],
                        len(data_message.data)) \
            + host                              \
            + origin[0]                         \
            + data_message.data

    @staticmethod
    def __decode_data(message_buffer, offset=0):
        host_length, port, origin_host_length, origin_port, payload_length = struct.unpack_from("!LLLLL", message_buffer, offset)
        offset += 20

        if len(message_buffer) < offset + host_length:
                raise ValueError("Cannot unpack Host, insufficient packet size")
        host = message_buffer[offset:offset + host_length]
        offset += host_length

        destination = (host, port)

        if len(message_buffer) < offset + origin_host_length:
            raise ValueError("Cannot unpack Origin Host, insufficient packet size")
        origin_host = message_buffer[offset:offset + origin_host_length]
        offset += origin_host_length

        origin = (origin_host, origin_port)

        if origin == ("0.0.0.0", 0):
            origin = None

        if payload_length == 0:
            payload = None
        else:
            if len(message_buffer) < offset + payload_length:
                raise ValueError("Cannot unpack Data, insufficient packet size")
            payload = message_buffer[offset:offset + payload_length]
            offset += payload_length

        return DataMessage(destination, payload, origin)


    @staticmethod
    def __encode_created(created_message):
        #assert len(created_message.key) == DIFFIE_HELLMAN_MODULUS_SIZE / 8, "Key should be {} bytes long, is {} bytes ".format(DIFFIE_HELLMAN_MODULUS_SIZE / 8, len(created_message.key))
        key = int_to_packed(created_message.key, 2048)
        return key + encode(created_message.candidate_list)


    @staticmethod
    def __decode_created(message_buffer, offset=0):

        key = packed_to_int(message_buffer[offset:offset + (DIFFIE_HELLMAN_MODULUS_SIZE / 8)], 2048)
        offset += (DIFFIE_HELLMAN_MODULUS_SIZE / 8)

        offset, candidate_dict = decode(message_buffer[offset:])

        return CreatedMessage(key, candidate_dict)

    @staticmethod
    def __encode_extended(extended_message):
        #assert len(extended_message.key) == DIFFIE_HELLMAN_MODULUS_SIZE, "Key should be {} bytes long, is {} bytes ".format(DIFFIE_HELLMAN_MODULUS_SIZE, len(extended_message.key))
        key = int_to_packed(extended_message.key, 2048)
        return key + encode(extended_message.candidate_list)

    @staticmethod
    def __decode_extended(message_buffer, offset=0):

        key = packed_to_int(message_buffer[offset:offset + (DIFFIE_HELLMAN_MODULUS_SIZE / 8)], 2048)
        offset += (DIFFIE_HELLMAN_MODULUS_SIZE / 8)

        offset, candidate_dict = decode(message_buffer[offset:])

        return ExtendedMessage(key, candidate_dict)

    @staticmethod
    def __encode_create(create_message):
        """
        :type create_message : Tribler.community.anontunnel.payload.CreateMessage
        """
        return create_message.key

    @staticmethod
    def __decode_create(message_buffer, offset=0):

        key = message_buffer[offset:]

        return CreateMessage(key)


def bits2string(b):
    b = bin(b)[2:]
    return ''.join(chr(int(''.join(x), 2)) for x in zip(*[iter(b)]*8))