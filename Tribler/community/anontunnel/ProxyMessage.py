import struct
from Tribler.Core.Utilities.encoding import decode, encode

__author__ = 'Chris'

MESSAGE_CREATE = chr(1)
MESSAGE_CREATED = chr(2)
MESSAGE_EXTEND = chr(3)
MESSAGE_EXTENDED = chr(4)
MESSAGE_DATA = chr(5)
MESSAGE_BREAK = chr(6)
MESSAGE_PING = chr(7)
MESSAGE_PONG = chr(8)
MESSAGE_PUNCTURE = chr(9)
MESSAGE_STATS = chr(10)


MESSAGE_STRING_REPRESENTATION = {
    MESSAGE_CREATE: u'create',
    MESSAGE_CREATED: u'created',
    MESSAGE_EXTEND: u'extend',
    MESSAGE_EXTENDED: u'extended',
    MESSAGE_DATA: u'data',
    MESSAGE_BREAK: u'break',
    MESSAGE_PING: u'ping',
    MESSAGE_PONG: u'pong',
    MESSAGE_PUNCTURE: u'puncture',
    MESSAGE_STATS: u'stats'
}

encode_functions = {}
decode_functions = {}


class CreateMessage:
    pass


class BreakMessage:
    pass


class PingMessage:
    pass


class CreatedMessage:
    pass


class ExtendMessage:
    @property
    def host(self):
        return self.extend_with[0] if self.extend_with else None

    @property
    def port(self):
        return self.extend_with[1] if self.extend_with else None

    def __init__(self, extend_with):
        self.extend_with = extend_with


class PunctureMessage:
    def __init__(self, sock_addr):
        self.sock_addr = sock_addr

class ExtendedWithMessage:
    @property
    def host(self):
        return self.extended_with[0]

    @property
    def port(self):
        return self.extended_with[1]

    def __init__(self, extended_with):
        self.extended_with = extended_with


class DataMessage:
    def __init__(self, destination, data, origin=None):
        self.destination = destination
        self.data = data
        self.origin = origin


def serialize(circuit_id, type, message):
    return struct.pack("!L", circuit_id) + type + encode_functions[type](message)


def change_circuit(buffer, new_id):
    return struct.pack("!L", new_id) + buffer[4:]


def get_circuit_and_data(buffer, offset=0):
    circuit_id, = struct.unpack_from("!L", buffer, offset)
    offset += 4

    return circuit_id, buffer[offset:]


def parse_payload(buffer, offset=0):
    message_type = buffer[offset]
    return message_type, decode_functions[message_type](buffer, offset+1)


def get_type(buffer):
    return buffer[5]

def __decode_extend(buffer, offset=0):
    if len(buffer) < offset + 8:
        raise ValueError("Cannot unpack HostLength/Port, insufficient packet size")
    host_length, port = struct.unpack_from("!LL", buffer, offset)
    offset += 8

    if len(buffer) < offset + host_length:
        raise ValueError("Cannot unpack Host, insufficient packet size")
    host = buffer[offset:offset + host_length]
    offset += host_length

    extended_with = (host, port) if host and port else None

    return ExtendMessage(extended_with)


def __encode_extend(extend_message):
    host = extend_message.host if extend_message.host else ''
    port = extend_message.port if extend_message.port else 0

    data = struct.pack("!LL", len(host), port) + host
    return data


def __decode_extended(buffer, offset=0):
    if len(buffer) < offset + 8:
        raise ValueError("Cannot unpack HostLength/Port, insufficient packet size")
    host_length, port = struct.unpack_from("!LL", buffer, offset)
    offset += 8

    if len(buffer) < offset + host_length:
        raise ValueError("Cannot unpack Host, insufficient packet size")
    host = buffer[offset:offset + host_length]
    offset += host_length

    extended_with = (host, port)

    return ExtendedWithMessage(extended_with)


def __encode_extended(extended_with_message):
    data = struct.pack("!LL", len(extended_with_message.host), extended_with_message.port) + extended_with_message.host
    return data


def __decode_data(buffer, offset=0):
    host_length, port, origin_host_length, origin_port, payload_length = struct.unpack_from("!LLLLL", buffer, offset)
    offset += 20

    if len(buffer) < offset + host_length:
            raise ValueError("Cannot unpack Host, insufficient packet size")
    host = buffer[offset:offset + host_length]
    offset += host_length

    destination = (host, port)

    if len(buffer) < offset + origin_host_length:
        raise ValueError("Cannot unpack Origin Host, insufficient packet size")
    origin_host = buffer[offset:offset + origin_host_length]
    offset += origin_host_length

    origin = (origin_host, origin_port)

    if origin == ("0.0.0.0", 0):
        origin = None

    if payload_length == 0:
        payload = None
    else:
        if len(buffer) < offset + payload_length:
            raise ValueError("Cannot unpack Data, insufficient packet size")
        payload = buffer[offset:offset + payload_length]
        offset += payload_length

    return DataMessage(destination, payload, origin)

def __decode_puncture(buffer, offset=0):
    host_length, port = struct.unpack_from("!LL", buffer, offset)
    offset += 8

    if len(buffer) < offset + host_length:
            raise ValueError("Cannot unpack Host, insufficient packet size")
    host = buffer[offset:offset + host_length]
    offset += host_length

    destination = (host, port)

    return PunctureMessage(destination)


def __encode_puncture(puncture_message):
    return struct.pack("!LL", len(puncture_message.sock_addr[0]), puncture_message.sock_addr[1]) + puncture_message.sock_addr[0]


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


empty_string_lambda = lambda message: ''

decode_functions[MESSAGE_CREATE] = lambda buffer, offset: CreateMessage()
encode_functions[MESSAGE_CREATE] = empty_string_lambda

decode_functions[MESSAGE_CREATED] = lambda buffer, offset: CreatedMessage()
encode_functions[MESSAGE_CREATED] = empty_string_lambda

decode_functions[MESSAGE_EXTEND] = __decode_extend
encode_functions[MESSAGE_EXTEND] = __encode_extend

decode_functions[MESSAGE_EXTENDED] = __decode_extended
encode_functions[MESSAGE_EXTENDED] = __encode_extended

decode_functions[MESSAGE_DATA] = __decode_data
encode_functions[MESSAGE_DATA] = __encode_data

decode_functions[MESSAGE_BREAK] = lambda buffer, offset: BreakMessage()
encode_functions[MESSAGE_BREAK] = empty_string_lambda

decode_functions[MESSAGE_PING] = lambda buffer, offset: PingMessage()
encode_functions[MESSAGE_PING] = empty_string_lambda

decode_functions[MESSAGE_PUNCTURE] = __decode_puncture
encode_functions[MESSAGE_PUNCTURE] = __encode_puncture

decode_functions[MESSAGE_STATS] = lambda buffer, offset: decode(buffer[offset:])[1]
encode_functions[MESSAGE_STATS] = lambda stats: encode(stats)