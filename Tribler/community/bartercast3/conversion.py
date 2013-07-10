from struct import pack, unpack_from

from .efforthistory import EffortHistory, CYCLE_SIZE

from Tribler.dispersy.member import Member
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


class BarterConversion(BinaryConversion):

    def __init__(self, community):
        super(BarterConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"barter-record"), self._encode_barter_record, self._decode_barter_record)
        self.define_meta_message(chr(2), community.get_meta_message(u"ping"), self._encode_ping_pong, self._decode_ping_pong)
        self.define_meta_message(chr(3), community.get_meta_message(u"pong"), self._encode_ping_pong, self._decode_ping_pong)
        self.define_meta_message(chr(4), community.get_meta_message(u"member-request"), self._encode_identifier, self._decode_identifier)
        self.define_meta_message(chr(5), community.get_meta_message(u"member-response"), self._encode_identifier, self._decode_identifier)

    def _encode_barter_record(self, message):
        payload = message.payload
        bytes_ = payload.effort.bytes

        return (pack(">LQQB",
                     long(payload.cycle),
                     long(payload.upload_first_to_second),
                     long(payload.upload_second_to_first),
                     len(bytes_)),
                bytes_,
                # the following parameters are used for debugging only
                pack(">LQQQQQQLQQQQQQ",
                     long(payload.first_timestamp),
                     long(payload.first_upload),
                     long(payload.first_download),
                     long(payload.first_total_up),
                     long(payload.first_total_down),
                     long(payload.first_associated_up),
                     long(payload.first_associated_down),
                     long(payload.second_timestamp),
                     long(payload.second_upload),
                     long(payload.second_download),
                     long(payload.second_total_up),
                     long(payload.second_total_down),
                     long(payload.second_associated_up),
                     long(payload.second_associated_down)))

    def _decode_barter_record(self, placeholder, offset, data):
        if len(data) < offset + 21:
            raise DropPacket("Insufficient packet size (_decode_barter_record)")

        cycle, upload_first_to_second, upload_second_to_first, length = unpack_from(">LQQB", data, offset)
        offset += 21

        if len(data) < offset + length:
            raise DropPacket("Insufficient packet size (_decode_barter_record)")
        effort = EffortHistory(data[offset:offset + length], cycle * CYCLE_SIZE)
        offset += length

        # the following parameters are used for debugging only
        if len(data) < offset + 104:
            raise DropPacket("Insufficient packet size (_decode_barter_record)")
        (first_timestamp,
         first_upload,
         first_download,
         first_total_up,
         first_total_down,
         first_associated_up,
         first_associated_down,
         second_timestamp,
         second_upload,
         second_download,
         second_total_up,
         second_total_down,
         second_associated_up,
         second_associated_down) = unpack_from(">LQQQQQQLQQQQQQ", data, offset)
        offset += 104

        return offset, placeholder.meta.payload.implement(cycle,
                                                          effort,
                                                          upload_first_to_second,
                                                          upload_second_to_first,
                                                          # the following parameters are used for debugging only
                                                          float(first_timestamp),
                                                          first_upload,
                                                          first_download,
                                                          first_total_up,
                                                          first_total_down,
                                                          first_associated_up,
                                                          first_associated_down,
                                                          float(second_timestamp),
                                                          second_upload,
                                                          second_download,
                                                          second_total_up,
                                                          second_total_down,
                                                          second_associated_up,
                                                          second_associated_down)

    def _encode_ping_pong(self, message):
        payload = message.payload
        return self._struct_BH.pack(len(payload.member.public_key), payload.identifier), payload.member.public_key

    def _decode_ping_pong(self, placeholder, offset, data):
        if len(data) < offset + 3:
            raise DropPacket("Insufficient packet size (_decode_ping_pong)")

        key_length, identifier = self._struct_BH.unpack_from(data, offset)
        offset += 3

        if len(data) < offset + key_length:
            raise DropPacket("Insufficient packet size (_decode_ping_pong)")
        try:
            member = Member(data[offset:offset + key_length])
        except:
            raise DropPacket("Invalid public key (_decode_ping_pong)")
        offset += key_length

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, identifier, member)

    def _encode_identifier(self, message):
        return self._struct_Q.pack(message.payload.identifier),

    def _decode_identifier(self, placeholder, offset, data):
        if len(data) < offset + 8:
            raise DropPacket("Insufficient packet size (_decode_identifier)")

        identifier, = self._struct_Q.unpack_from(data, offset)
        offset += 8

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, identifier)
