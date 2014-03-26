import logging
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.community.anontunnel.globals import MESSAGE_CREATE, \
    MESSAGE_CREATED, MESSAGE_EXTEND, MESSAGE_EXTENDED, MESSAGE_DATA, \
    MESSAGE_PING, MESSAGE_PONG
from Tribler.community.anontunnel.payload import ExtendMessage, DataMessage, \
    PingMessage, PongMessage, CreatedMessage, ExtendedMessage, CreateMessage
from Tribler.dispersy.conversion import BinaryConversion
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

    def get_circuit_and_data(self, message_buffer, offset=0):
        """
        Get the circuit id and the payload byte string from a byte string
        @param str message_buffer: the byte string to parse
        @param int offset: the offset to start decoding from
        @rtype (int, str)
        """
        circuit_id, = struct.unpack_from("!L", message_buffer, offset)
        offset += 4

        return circuit_id, message_buffer[offset:]

    def get_type(self, data):
        """
        Gets the type from a raw byte string

        @param str data: the raw byte string to get the type of
        @rtype: str
        """
        return data[0]

    def add_circuit(self, data, new_id):
        """
        Prepends the circuit id to the raw byte string
        @param str data: the raw byte string to prepend the circuit id to
        @param int new_id: the circuit id to prepend
        @rtype: str
        """
        return struct.pack("!L", new_id) + data

    def __encode_extend(self, extend_message):
        extend_with = extend_message.extend_with
        key = extend_message.key

        data = extend_with + key
        return data

    def __decode_extend(self, message_buffer, offset=0):
        if len(message_buffer) < offset + 6:
            raise ValueError(
                "Cannot unpack extend_with, insufficient packet size")
        extend_with = message_buffer[offset : offset + 6]
        offset += 6

        key = message_buffer[offset:]

        message = ExtendMessage(extend_with)
        message.key = key
        return message

    def __encode_data(self, data_message):
        if data_message.destination is None:
            (host, port) = ("0.0.0.0", 0)
        else:
            (host, port) = data_message.destination

        if data_message.origin is None:
            origin = ("0.0.0.0", 0)
        else:
            origin = data_message.origin

        return ''.join([
            struct.pack(
                "!LHLLL", len(host), port, len(origin[0]),
                origin[1], len(data_message.data)
            ),
            host,
            origin[0],
            data_message.data
        ])

    def __decode_data(self, message_buffer, offset=0):
        host_length, port, origin_host_length, origin_port, payload_length = \
            struct.unpack_from("!LHLLL", message_buffer, offset)
        offset += 18

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

    def __encode_created(self, message):
        #key = long_to_bytes(messages.key, DIFFIE_HELLMAN_MODULUS_SIZE / 8)
        return struct.pack("!L", len(message.key)) + message.key + \
               message.candidate_list

    def __decode_created(self, message_buffer, offset=0):
        key_length, = struct.unpack_from("!L",
                                         message_buffer[offset:offset + 4])
        offset += 4
        key = message_buffer[offset:offset + key_length]
        offset += key_length

        encrypted_candidate_list = message_buffer[offset:]
        message = CreatedMessage(encrypted_candidate_list)
        message.key = key
        return message

    def __encode_extended(self, message):
        return struct.pack("!L", len(message.key)) + message.key + \
               message.candidate_list

    def __decode_extended(self, message_buffer, offset=0):
        key_length, = struct.unpack_from("!L", message_buffer[offset:])
        offset += 4
        key = message_buffer[offset:offset+key_length]
        offset += key_length

        encrypted_candidate_list = message_buffer[offset:]

        return ExtendedMessage(key, encrypted_candidate_list)

    def __encode_create(self, create_message):
        """
        :type create_message : CreateMessage
        """
        return create_message.key

    def __decode_create(self, message_buffer, offset=0):
        key = message_buffer[offset:]
        return CreateMessage(key)