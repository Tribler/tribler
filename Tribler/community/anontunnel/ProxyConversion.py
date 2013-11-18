import struct
from Tribler.Core.Utilities.encoding import encode, decode

from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.payload import Payload


class PongPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id):
            super(PongPayload.Implementation, self).__init__(meta)

            self.circuit_id = circuit_id


class PingPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id):
            super(PingPayload.Implementation, self).__init__(meta)

            self.circuit_id = circuit_id


class CreatePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id):
            super(CreatePayload.Implementation, self).__init__(meta)

            self.circuit_id = circuit_id


class BreakPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id):
            super(BreakPayload.Implementation, self).__init__(meta)

            self.circuit_id = circuit_id


class ExtendPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id):
            super(ExtendPayload.Implementation, self).__init__(meta)

            self.circuit_id = circuit_id
            #self.extend_with = extend_with


class ExtendedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, extended_with):
            super(ExtendedPayload.Implementation, self).__init__(meta)

            self.circuit_id = circuit_id
            self.extended_with = extended_with


class DataPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, destination, data, origin=None):
            super(DataPayload.Implementation, self).__init__(meta)

            self.circuit_id = circuit_id
            self.destination = destination
            self.data = data
            self.origin = origin

class StatsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, stats):
            super(StatsPayload.Implementation, self).__init__(meta)
            self.stats = stats


class ProxyConversion(BinaryConversion):
    def __init__(self, community):
        super(ProxyConversion, self).__init__(community, "\x01")

        self.define_meta_message(
            chr(1)
            , community.get_meta_message(u"create")
            , self._encode_create_created
            , self._decode_create_or_created)

        self.define_meta_message(
            chr(2)
            , community.get_meta_message(u"created")
            , self._encode_create_created
            , self._decode_create_or_created)

        self.define_meta_message(
            chr(3)
            , community.get_meta_message(u"extend")
            , self._encode_extend
            , self._decode_extend)

        self.define_meta_message(
            chr(4)
            , community.get_meta_message(u"extended")
            , self._encode_extended
            , self._decode_extended)

        self.define_meta_message(
            chr(5)
            , community.get_meta_message(u"data")
            , self._encode_data
            , self._decode_data)

        self.define_meta_message(
            chr(6),
            community.get_meta_message(u"break")
            , self._encode_break
            , self._decode_break
        )

        self.define_meta_message(
            chr(7),
            community.get_meta_message(u"ping")
            , self._encode_ping_pong
            , self._decode_ping_pong
        )

        self.define_meta_message(
            chr(8),
            community.get_meta_message(u"pong")
            , self._encode_ping_pong
            , self._decode_ping_pong
        )

        self.define_meta_message(
            chr(9),
            community.get_meta_message(u"stats")
            , self._encode_stats
            , self._decode_stats
        )

        #self.define_meta_message(
        #    chr(10),
        #    community.get_meta_message(u"circuit")
        #    , self._encode_circuit
        #    , self._decode_circuit
        #)

    @staticmethod
    def _encode_circuit(message):
        return message.payload.data

    @staticmethod
    def _decode_circuit(placeholder, offset, data):
        return offset + len(data), placeholder.meta.payload.implement(data)

    @staticmethod
    def _encode_stats(message):
        return encode(message.payload.stats),

    @staticmethod
    def _decode_stats(placeholder, offset, data):
        offset, stats = decode(data, offset)

        return offset, placeholder.meta.payload.implement(stats[0])

    @staticmethod
    def _encode_ping_pong(message):
        return struct.pack("!L", message.payload.circuit_id),

    @staticmethod
    def _decode_ping_pong(placeholder, offset, data):
        circuit_id, = struct.unpack_from("!L", data, offset)
        offset += 4


        return offset, placeholder.meta.payload.implement(circuit_id)

    @staticmethod
    def _encode_break(message):
        return struct.pack("!L", message.payload.circuit_id),

    @staticmethod
    def _decode_break(placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack circuit_id, insufficient packet size")

        circuit_id, = struct.unpack_from("!L", data, offset)
        offset += 4

        return offset, placeholder.meta.payload.implement(circuit_id)

    @staticmethod
    def _encode_create_created(message):
        return struct.pack("!L", message.payload.circuit_id),

    @staticmethod
    def _decode_create_or_created(placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack circuit_id, insufficient packet size")

        circuit_id, = struct.unpack_from("!L", data, offset)
        offset += 4

        return offset, placeholder.meta.payload.implement(circuit_id)

    @staticmethod
    def _encode_extended(message):
        (host, port) = message.payload.extended_with
        return (
            struct.pack("!LL", message.payload.circuit_id, len(host))
            , host
            , struct.pack("!L", port)
        )

    @staticmethod
    def _encode_extend(message):
        return struct.pack("!L", message.payload.circuit_id),

    @staticmethod
    def _encode_data(message):

        if message.payload.destination is None:
            (host, port) = ("0.0.0.0", 0)
        else:
            (host, port) = message.payload.destination

        if message.payload.origin is None:
            origin = ("0.0.0.0", 0)
        else:
            origin = message.payload.origin

        return (
            struct.pack("!LLLLLL", message.payload.circuit_id, len(host), port, len(origin[0]), origin[1],
                        len(message.payload.data))
            , host
            , origin[0]
            , message.payload.data
        )

    @staticmethod
    def _decode_extend(placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack circuit_id, insufficient packet size")
        circuit_id, = struct.unpack_from("!L", data, offset)
        offset += 4

        return offset, placeholder.meta.payload.implement(circuit_id)

    @staticmethod
    def _decode_extended(placeholder, offset, data):
        if len(data) < offset + 8:
            raise DropPacket("Cannot unpack circuit_id/HostLength, insufficient packet size")
        circuit_id, host_length = struct.unpack_from("!LL", data, offset)
        offset += 8

        if len(data) < offset + host_length:
            raise DropPacket("Cannot unpack Host, insufficient packet size")
        host = data[offset:offset + host_length]
        offset += host_length

        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack Port, insufficient packet size")
        port, = struct.unpack_from("!L", data, offset)
        offset += 4

        extend_with = (host, port)

        return offset, placeholder.meta.payload.implement(circuit_id, extend_with)

    @staticmethod
    def _decode_data(placeholder, offset, data):
        if len(data) < offset + 24:
            raise DropPacket("Cannot unpack circuit_id/HostLength, insufficient packet size")
        circuit_id, host_length, port, origin_host_length, origin_port, payload_length = struct.unpack_from("!LLLLLL",
                                                                                                            data,
                                                                                                            offset)
        offset += 24

        if len(data) < offset + host_length:
            raise DropPacket("Cannot unpack Host, insufficient packet size")
        host = data[offset:offset + host_length]
        offset += host_length

        destination = (host, port)

        if len(data) < offset + origin_host_length:
            raise DropPacket("Cannot unpack Origin Host, insufficient packet size")
        origin_host = data[offset:offset + origin_host_length]
        offset += origin_host_length

        origin = (origin_host, origin_port)

        if origin == ("0.0.0.0", 0):
            origin = None

        if payload_length == 0:
            payload = None
        else:
            if len(data) < offset + payload_length:
                raise DropPacket("Cannot unpack Data, insufficient packet size")
            payload = data[offset:offset + payload_length]
            offset += payload_length

        return offset, placeholder.meta.payload.implement(circuit_id, destination, payload, origin)