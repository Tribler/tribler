import logging
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.community.anontunnel.globals import MESSAGE_CREATE, \
    MESSAGE_CREATED, MESSAGE_EXTEND, MESSAGE_EXTENDED, MESSAGE_DATA, \
    MESSAGE_PING, MESSAGE_PONG, DIFFIE_HELLMAN_MODULUS_SIZE
from Tribler.community.anontunnel.payload import ExtendMessage, DataMessage, \
    PingMessage, PongMessage, CreatedMessage, ExtendedMessage, CreateMessage
from Tribler.dispersy.conversion import BinaryConversion
from Crypto.Util.number import long_to_bytes, bytes_to_long
import struct


class ProxyConversion(BinaryConversion):
    """
    The dispersy conversion used for the STATS message in the ProxyCommunity
    @param ProxyCommunity community: the instance of the ProxyCommunity
    """

    def __init__(self, community):
        super(ProxyConversion, self).__init__(community, "\x01")

        self._logger = logging.getLogger(__name__)

        self.define_meta_message(
            chr(1),
            community.get_meta_message(u"stats"),
            self._encode_stats,
            self._decode_stats
        )

    @staticmethod
    def _encode_stats(message):
        return encode(message.payload.stats),

    @staticmethod
    def _decode_stats(placeholder, offset, data):
        offset, stats = decode(data, offset)

        return offset, placeholder.meta.payload.implement(stats)


class CustomProxyConversion():
    """
    Custom conversion for Proxy messages. This conversion encodes objects
    to bytes and vice versa
    """
    def __init__(self):
        self._logger = logging.getLogger(__name__)

        self.encode_functions = {
            MESSAGE_CREATE: self.__encode_create,
            MESSAGE_CREATED: self.__encode_created,
            MESSAGE_EXTEND: self.__encode_extend,
            MESSAGE_EXTENDED: self.__encode_extended,
            MESSAGE_DATA: self.__encode_data,
            MESSAGE_PING: lambda _: '',
            MESSAGE_PONG: lambda _: ''
        }

        self.decode_functions = {
            MESSAGE_CREATE: self.__decode_create,
            MESSAGE_CREATED: self.__decode_created,
            MESSAGE_EXTEND: self.__decode_extend,
            MESSAGE_EXTENDED: self.__decode_extended,
            MESSAGE_DATA: self.__decode_data,
            MESSAGE_PING: lambda offset, data: PingMessage(),
            MESSAGE_PONG: lambda offset, data: PongMessage(),
        }

    def encode(self, message_type, message):
        """
        Encodes an object into a byte string
        @param str message_type: the messages type (see the constants)
        @param BaseMessage message: the message to serialize
        @return: the message in byte format
        @rtype: str
        """
        return message_type + self.encode_functions[message_type](message)

    def decode(self, data, offset=0):
        """
        Decode a byte string to a message
        @param str data: raw byte string to decode
        @param int offset: the offset to start at
        @return: the message in object format
        @rtype: BaseMessage
        """
        message_type = data[offset]
        assert message_type > 0
        return message_type, self.decode_functions[message_type](
            data, offset + 1)

    @staticmethod
    def get_circuit_and_data(message_buffer, offset=0):
        """
        Get the circuit id and the payload byte string from a byte string
        @param str message_buffer: the byte string to parse
        @param int offset: the offset to start decoding from
        @rtype (int, str)
        """
        circuit_id, = struct.unpack_from("!L", message_buffer, offset)
        offset += 4

        return circuit_id, message_buffer[offset:]

    @staticmethod
    def get_type(data):
        """
        Gets the type from a raw byte string

        @param str data: the raw byte string to get the type of
        @rtype: str
        """
        return data[0]

    @staticmethod
    def add_circuit(data, new_id):
        """
        Prepends the circuit id to the raw byte string
        @param str data: the raw byte string to prepend the circuit id to
        @param int new_id: the circuit id to prepend
        @rtype: str
        """
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

        return struct.pack(
            "!LLLLL", len(host), port, len(origin[0]),
            origin[1], len(data_message.data)
        ) + host + origin[0] + data_message.data

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

        return DataMessage(destination, payload, origin)

    @staticmethod
    def __encode_created(messages):
        key = long_to_bytes(messages.key, DIFFIE_HELLMAN_MODULUS_SIZE / 8)
        return key + encode(messages.candidate_list)

    @staticmethod
    def __decode_created(message_buffer, offset=0):

        key = bytes_to_long(
            message_buffer[offset:offset + (DIFFIE_HELLMAN_MODULUS_SIZE / 8)])
        offset += (DIFFIE_HELLMAN_MODULUS_SIZE / 8)

        offset, candidate_dict = decode(message_buffer[offset:])

        return CreatedMessage(key, candidate_dict)

    @staticmethod
    def __encode_extended(message):
        key = long_to_bytes(message.key, DIFFIE_HELLMAN_MODULUS_SIZE / 8)
        return key + encode(message.candidate_list)

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