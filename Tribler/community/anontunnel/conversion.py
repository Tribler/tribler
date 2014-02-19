from M2Crypto import __m2crypto
import logging
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.community.anontunnel.payload import *
from Tribler.community.anontunnel.globals import *
from Crypto.Util.number import long_to_bytes, bytes_to_long
import struct

logger = logging.getLogger(__name__)

#-----------------------------------------------------------------------------
#: enable verbose print statements.
DEBUG = True


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
            MESSAGE_PING: self.__encode_ping,
            MESSAGE_PONG: self.__encode_pong
        }

        self.decode_functions = {
            MESSAGE_CREATE: self.__decode_create,
            MESSAGE_CREATED: self.__decode_created,
            MESSAGE_EXTEND: self.__decode_extend,
            MESSAGE_EXTENDED: self.__decode_extended,
            MESSAGE_DATA: self.__decode_data,
            MESSAGE_PING: self.__decode_ping,
            MESSAGE_PONG: self.__decode_pong,
        }

    def encode(self, message_type, message):
        return message_type + self.encode_functions[message_type](message)

    def decode(self, data, offset=0):
        message_type = data[offset]
        assert message_type > 0
        return message_type, self.decode_functions[message_type](data,
                                                                 offset + 1)

    @staticmethod
    def get_circuit_and_data(message_buffer, offset=0):
        """
        @rtype (int, str)
        """
        circuit_id, = struct.unpack_from("!L", message_buffer, offset)
        offset += 4

        return circuit_id, message_buffer[offset:]

    @staticmethod
    def get_type(data):
        """
        @rtype: str
        """
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
            raise ValueError(
                "Cannot unpack HostLength/Port, insufficient packet size")
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

        return struct.pack("!LLLLL", len(host), port, len(origin[0]),
                           origin[1],
                           len(data_message.data)) \
               + host \
               + origin[0] \
               + data_message.data

    @staticmethod
    def __decode_data(message_buffer, offset=0):
        host_length, port, origin_host_length, origin_port, payload_length = \
            struct.unpack_from("!LLLLL", message_buffer, offset)
        offset += 20

        if len(message_buffer) < offset + host_length:
            raise ValueError("Cannot unpack Host, insufficient packet size")
        host = message_buffer[offset:offset + host_length]
        offset += host_length

        destination = (host, port)

        if len(message_buffer) < offset + origin_host_length:
            raise ValueError(
                "Cannot unpack Origin Host, insufficient packet size")
        origin_host = message_buffer[offset:offset + origin_host_length]
        offset += origin_host_length

        origin = (origin_host, origin_port)

        if origin == ("0.0.0.0", 0):
            origin = None

        if destination == ("0.0.0.0", 0):
            destination = None

        if payload_length == 0:
            payload = None
        else:
            if len(message_buffer) < offset + payload_length:
                raise ValueError(
                    "Cannot unpack Data, insufficient packet size")
            payload = message_buffer[offset:offset + payload_length]
            offset += payload_length

        return DataMessage(destination, payload, origin)

    @staticmethod
    def __encode_ping(message):
        return ''

    @staticmethod
    def __encode_pong(message):
        return ''

    @staticmethod
    def __decode_ping(message_buffer, offset=0):
        return PingMessage()

    @staticmethod
    def __decode_pong(message_buffer, offset=0):
        return PongMessage()

    @staticmethod
    def __encode_created(created_message):
        # assert len(created_message.key) == DIFFIE_HELLMAN_MODULUS_SIZE / 8, \
        #     "Key should be {} bytes long, is {} bytes ".format(
        #         DIFFIE_HELLMAN_MODULUS_SIZE / 8, len(created_message.key))

        key = long_to_bytes(created_message.key, DIFFIE_HELLMAN_MODULUS_SIZE / 8)
        return key + encode(created_message.candidate_list)

    @staticmethod
    def __decode_created(message_buffer, offset=0):

        key = bytes_to_long(
            message_buffer[offset:offset + (DIFFIE_HELLMAN_MODULUS_SIZE / 8)])
        offset += (DIFFIE_HELLMAN_MODULUS_SIZE / 8)

        offset, candidate_dict = decode(message_buffer[offset:])

        return CreatedMessage(key, candidate_dict)

    @staticmethod
    def __encode_extended(extended_message):
        # assert len(extended_message.key) == DIFFIE_HELLMAN_MODULUS_SIZE, \
        #     "Key should be {} bytes long, is {} bytes ".format(
        #         DIFFIE_HELLMAN_MODULUS_SIZE, len(extended_message.key))

        key = long_to_bytes(extended_message.key, DIFFIE_HELLMAN_MODULUS_SIZE / 8)
        return key + encode(extended_message.candidate_list)

    @staticmethod
    def __decode_extended(message_buffer, offset=0):

        key = bytes_to_long(
            message_buffer[offset:offset + (DIFFIE_HELLMAN_MODULUS_SIZE / 8)])
        offset += (DIFFIE_HELLMAN_MODULUS_SIZE / 8)

        offset, candidate_dict = decode(message_buffer[offset:])

        return ExtendedMessage(key, candidate_dict)

    @staticmethod
    def __encode_create(create_message):
        """
        :type create_message : CreateMessage
        """
        return create_message.key

    @staticmethod
    def __decode_create(message_buffer, offset=0):

        key = message_buffer[offset:]

        return CreateMessage(key)



#: struct format lookup for specific word sizes.
STRUCT_FMT = {
    8: 'B',  # unsigned char
    16: 'H',  # unsigned short
    32: 'I',  # unsigned int
}
