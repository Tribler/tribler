from socket import inet_ntoa, inet_aton
from struct import pack, unpack_from

from .efforthistory import EffortHistory

from Tribler.dispersy.member import Member
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.revision import update_revision_information

# update version information directly from SVN
update_revision_information("$HeadURL$", "$Revision$")

class EffortConversion(BinaryConversion):
    def __init__(self, community):
        super(EffortConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"effort-record"), self._encode_effort_record, self._decode_effort_record)
        self.define_meta_message(chr(2), community.get_meta_message(u"ping"), self._encode_ping_pong, self._decode_ping_pong)
        self.define_meta_message(chr(3), community.get_meta_message(u"pong"), self._encode_ping_pong, self._decode_ping_pong)
        self.define_meta_message(chr(4), community.get_meta_message(u"debug-request"), self._encode_debug_request, self._decode_debug_request)
        self.define_meta_message(chr(5), community.get_meta_message(u"debug-response"), self._encode_debug_response, self._decode_debug_response)

    def _encode_effort_record(self, message):
        payload = message.payload
        bytes_ = payload.history.bytes
        return pack(">LLLLLLB", int(payload.first_timestamp), int(payload.second_timestamp), payload.first_up, payload.first_down, payload.second_up, payload.second_down, len(bytes_)), bytes_

    def _decode_effort_record(self, placeholder, offset, data):
        if len(data) < offset + 25:
            raise DropPacket("Insufficient packet size (_decode_effort_record)")

        first_timestamp, second_timestamp, first_up, first_down, second_up, second_down, length = unpack_from(">LLLLLLB", data, offset)
        offset += 25

        # internally we use floats for timestamps
        first_timestamp = float(first_timestamp)
        second_timestamp = float(second_timestamp)

        if len(data) < offset + length:
            raise DropPacket("Insufficient packet size (_decode_effort_record)")

        history = EffortHistory(data[offset:offset+length], (first_timestamp + second_timestamp) / 2.0)
        offset += length

        return offset, placeholder.meta.payload.implement(first_timestamp, second_timestamp, history, first_up, first_down, second_up, second_down)

    def _encode_ping_pong(self, message):
        payload = message.payload
        return self._struct_BH.pack(len(payload.member.public_key), payload.identifier), payload.member.public_key

    def _decode_ping_pong(self, placeholder, offset, data):
        if len(data) < offset + 3:
            raise DropPacket("Insufficient packet size (_decode_ping_pong)")

        key_length, identifier, = self._struct_BH.unpack_from(data, offset)
        offset += 3

        if len(data) < offset + key_length:
            raise DropPacket("Insufficient packet size (_decode_ping_pong)")
        try:
            member = Member(data[offset:offset+key_length])
        except:
            raise DropPacket("Invalid public key (_decode_ping_pong)")
        offset += key_length

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, identifier, member)

    def _encode_debug_request(self, message):
        payload = message.payload
        data = [inet_aton(payload.source_address[0]),
                self._struct_H.pack(payload.source_address[1])]
        data.extend(message.payload.members)
        return data

    def _decode_debug_request(self, placeholder, offset, data):
        if len(data) < offset + 6:
            raise DropPacket("Insufficient packet size (_decode_debug_request)")

        source_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        members = []
        while len(data) >= offset + 20:
            members.append(data[offset:offset+20])
            offset += 20

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, source_address, members)

    def _encode_debug_response(self, message):
        payload = message.payload
        datas = [pack(">HfII", payload.revision, payload.now, payload.observations, payload.records)]
        datas.extend(pack(">20sHH", mid, view[0], view[1]) for mid, view in payload.views.iteritems())
        return datas

    def _decode_debug_response(self, placeholder, offset, data):
        revision, now, observations, records = unpack_from(">HfII", data, offset)
        offset += 14

        views = {}
        while len(data) >= offset + 24:
            mid, direct_seen, indirect_seen = unpack_from(">20sHH", data, offset)
            views[mid] = (direct_seen, indirect_seen)
            offset += 24

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, revision, now, observations, records, views)
