from struct import pack, unpack_from
from socket import inet_ntoa, inet_aton

from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


class TunnelConversion(BinaryConversion):
    def __init__(self, community):
        super(TunnelConversion, self).__init__(community, "\x02")

        self.define_meta_message(chr(1), community.get_meta_message(u"cell"), lambda message: self._encode_decode(self._encode_cell, self._decode_cell, message), self._decode_cell)
        self.define_meta_message(chr(2), community.get_meta_message(u"create"), lambda message: self._encode_decode(self._encode_create, self._decode_create, message), self._decode_create)
        self.define_meta_message(chr(3), community.get_meta_message(u"created"), lambda message: self._encode_decode(self._encode_created, self._decode_created, message), self._decode_created)
        self.define_meta_message(chr(4), community.get_meta_message(u"extend"), lambda message: self._encode_decode(self._encode_extend, self._decode_extend, message), self._decode_extend)
        self.define_meta_message(chr(5), community.get_meta_message(u"extended"), lambda message: self._encode_decode(self._encode_extended, self._decode_extended, message), self._decode_extended)
        self.define_meta_message(chr(6), community.get_meta_message(u"ping"), lambda message: self._encode_decode(self._encode_ping, self._decode_ping, message), self._decode_ping)
        self.define_meta_message(chr(7), community.get_meta_message(u"pong"), lambda message: self._encode_decode(self._encode_pong, self._decode_pong, message), self._decode_pong)

    def _encode_cell(self, message):
        payload = message.payload
        packet = pack("!IB", payload.circuit_id, self._encode_message_map[payload.message_type].byte) + payload.encrypted_message
        return packet,

    def _decode_cell(self, placeholder, offset, data):
        circuit_id, = unpack_from('!I', data, offset)
        offset += 4

        if not self._decode_message_map.has_key(data[offset]):
            raise DropPacket("Invalid message")
        message_type = self._decode_message_map[data[offset]].meta.name
        offset += 1

        encrypted_message = data[offset:]
        offset += len(encrypted_message)

        return offset, placeholder.meta.payload.implement(circuit_id, message_type, encrypted_message)

    def _encode_create(self, message):
        payload = message.payload
        packet = pack("!IHH", payload.circuit_id, len(payload.key), len(payload.public_key)) + payload.key + payload.public_key
        return packet,

    def _decode_create(self, placeholder, offset, data):
        circuit_id, = unpack_from('!I', data, offset)
        offset += 4

        len_key, len_pub_key = unpack_from("!HH", data, offset)
        offset += 4

        key = data[offset:offset + len_key]
        offset += len_key

        public_key = data[offset:offset + len_pub_key]
        offset += len_pub_key

        return offset, placeholder.meta.payload.implement(circuit_id, key, public_key)

    def _encode_created(self, message):
        payload = message.payload
        packet = pack("!IH", payload.circuit_id, len(payload.key)) + payload.key + encode(payload.candidate_list)
        return packet,

    def _decode_created(self, placeholder, offset, data):
        circuit_id, = unpack_from('!I', data, offset)
        offset += 4

        len_key, = unpack_from("!H", data, offset)
        offset += 2

        key = data[offset:offset + len_key]
        offset += len_key

        encoded_candidate_list = data[offset:]
        offset += len(encoded_candidate_list)
        _, candidate_list = decode(encoded_candidate_list)

        return offset, placeholder.meta.payload.implement(circuit_id, key, candidate_list)

    def _encode_extend(self, message):
        payload = message.payload
        packet = pack("!IHH", payload.circuit_id, len(payload.extend_with), len(payload.key)) + payload.extend_with + payload.key
        return packet,

    def _decode_extend(self, placeholder, offset, data):
        circuit_id, = unpack_from('!I', data, offset)
        offset += 4

        len_extend_with, len_key = unpack_from("!HH", data, offset)
        offset += 4

        extend_with = data[offset:offset + len_extend_with]
        offset += len_extend_with

        key = data[offset:offset + len_key]
        offset += len_key

        return offset, placeholder.meta.payload.implement(circuit_id, key, extend_with)

    def _encode_extended(self, message):
        payload = message.payload
        return pack("!IH", payload.circuit_id, len(payload.key)) + payload.key + encode(payload.candidate_list),

    def _decode_extended(self, placeholder, offset, data):
        circuit_id, = unpack_from('!I', data, offset)
        offset += 4

        key_length, = unpack_from("!H", data, offset)
        offset += 2

        key = data[offset:offset + key_length]
        offset += key_length

        encoded_candidate_list = data[offset:]
        offset += len(encoded_candidate_list)
        _, candidate_list = decode(encoded_candidate_list)

        return offset, placeholder.meta.payload.implement(circuit_id, key, candidate_list)

    def _encode_data(self, message):
        host, port = ("0.0.0.0", 0) if message.destination is None else message.destination
        origin = ("0.0.0.0", 0) if message.origin is None else message.origin
        packet = pack("!IHHHHL", message.payload.circuit_id, len(host), port, len(origin[0]), origin[1], len(message.data)) + \
                 host + origin[0] + message.data
        return packet,

    def _decode_data(self, placeholder, offset, data):
        circuit_id, host_length, port, origin_host_length, origin_port, payload_length = unpack_from("!IHHHHL", data, offset)
        offset += 16

        if len(data) < offset + host_length:
            raise ValueError("Cannot unpack Host, insufficient packet size")
        host = data[offset:offset + host_length]
        offset += host_length

        destination = (host, port)

        if len(data) < offset + origin_host_length:
            raise ValueError("Cannot unpack Origin Host, insufficient packet size")
        origin_host = data[offset:offset + origin_host_length]
        offset += origin_host_length

        origin = (origin_host, origin_port)

        if origin == ("0.0.0.0", 0):
            origin = None

        if destination == ("0.0.0.0", 0):
            destination = None

        if payload_length == 0:
            payload = None
        else:
            if len(data) < offset + payload_length:
                raise ValueError("Cannot unpack Data, insufficient packet size")
            payload = data[offset:offset + payload_length]

        return offset, placeholder.meta.payload.implement(circuit_id, destination, payload, origin)

    def _encode_ping(self, message):
        return pack('!IH', message.payload.circuit_id, message.payload.identifier),

    def _decode_ping(self, placeholder, offset, data):
        if len(data) < offset + 6:
            raise DropPacket("Insufficient packet size")

        circuit_id, identifier = unpack_from('!IH', data, offset)
        offset += 6

        return offset, placeholder.meta.payload.implement(circuit_id, identifier)

    def _encode_pong(self, message):
        return self._encode_ping(message)

    def _decode_pong(self, placeholder, offset, data):
        return self._decode_ping(placeholder, offset, data)

    def _encode_decode(self, encode, decode, message):
        result = encode(message)
        try:
            decode(None, 0, result[0])

        except DropPacket:
            from traceback import print_exc
            print_exc()
            raise
        except:
            pass
        return result

    @staticmethod
    def swap_circuit_id(packet, message_type, old_circuit_id, new_circuit_id):
        circuit_id_pos = 0 if message_type == u"data" else 31
        circuit_id, = unpack_from('!I', packet, circuit_id_pos)
        assert circuit_id == old_circuit_id, circuit_id
        packet = packet[:circuit_id_pos] + pack('!I', new_circuit_id) + packet[circuit_id_pos + 4:]
        return packet

    @staticmethod
    def encode_data(circuit_id, dest_address, org_address, data):
        return pack("!I4sH4sH", circuit_id, inet_aton(dest_address[0]), dest_address[1],
                                            inet_aton(org_address[0]), org_address[1]) + data

    @staticmethod
    def decode_data(packet):
        circuit_id, = unpack_from("!I", packet)

        dest_ip, dest_port = unpack_from('!4sH', packet, 4)
        dest_address = (inet_ntoa(dest_ip), dest_port)

        org_ip, org_port = unpack_from('!4sH', packet, 10)
        org_address = (inet_ntoa(org_ip), org_port)

        data = packet[16:]

        return circuit_id, dest_address, org_address, data

    @staticmethod
    def convert_from_cell(packet):
        header = packet[:22] + packet[35] + packet[23:31]
        return header + packet[31:35] + packet[36:]

    @staticmethod
    def convert_to_cell(packet):
        header = packet[:22] + '\x01' + packet[23:31]
        return header + packet[31:35] + packet[22] + packet[35:]
