from struct import pack, unpack_from

from efforthistory import EffortHistory

from Tribler.Core.dispersy.conversion import BinaryConversion
from Tribler.Core.dispersy.message import DropPacket

class EffortConversion(BinaryConversion):
    def __init__(self, community):
        super(EffortConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"effort-record"), self._encode_effort_record, self._decode_effort_record)

    def _encode_effort_record(self, message):
        payload = message.payload
        return pack("!LL", payload.first_timestamp, payload.second_timestamp), payload.history.bytes

    def _decode_effort_record(self, placeholder, offset, data):
        if len(data) < offset + 72:
            raise DropPacket("Insufficient packet size")

        first_timestamp, second_timestamp = unpack_from("!LL", data, offset)
        offset += 8

        # internally we use floats for timestamps
        first_timestamp = float(first_timestamp)
        second_timestamp = float(second_timestamp)

        # decide the timestamp to use: if we are either the first or second member, we use the
        # associated timestamp, otherwise, use the average
        if placeholder.authentication.members[0] == self._community.my_member:
            origin = first_timestamp
        elif placeholder.authentication.members[1] == self._community.my_member:
            origin = second_timestamp
        else:
            origin = (first_timestamp + second_timestamp) / 2.0

        history = EffortHistory(data[offset:offset+64], 64*8, origin)
        offset += 64

        return offset, placeholder.meta.payload.implement(first_timestamp, second_timestamp, history)
