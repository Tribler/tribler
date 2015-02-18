from struct import pack, unpack_from
from Tribler.dispersy.conversion import BinaryConversion


class StatisticsConversion(BinaryConversion):

    MTU_SIZE = 1500

    def __init__(self, community):
        super(StatisticsConversion, self).__init__(community, "\x02")
        self.define_meta_message(chr(1), community.get_meta_message(u"stats-request"),
                                 self._encode_statistics_request, self._decode_statistics_request)
        self.define_meta_message(chr(2), community.get_meta_message(u"stats-response"),
                                 self._encode_statistics_response, self._decode_statistics_response)

    def _encode_statistics_request(self, message):
        stats_type = message.payload.stats_type
        return pack("!i", stats_type),

    def _decode_statistics_request(self, placeholder, offset, data):
        stats_type, = unpack_from("!i", data, offset)
        offset += 4
        return offset, placeholder.meta.payload.implement(stats_type)

    # TODO fix for dictionaries larger than MTU (split message)
    def _encode_statistics_response(self, message):
        stats_type = message.payload.stats_type
        records = message.payload.records
        packed = pack("!i", stats_type)
        for r in records:
            peer_id = r[0].encode('utf8')
            value = r[1]
            packed = packed + pack("!H%dsi" % len(peer_id), len(peer_id), peer_id, value)
        return packed,

    def _decode_statistics_response(self, placeholder, offset, data):
        stats_type, = unpack_from("!i", data, offset)
        offset += 4
        records = []
        while offset < len(data):
            len_key, = unpack_from("!H", data, offset)
            if len_key < 1:
                break
            offset += 2
            key, = unpack_from("!%ds" % len_key, data, offset)
            offset += len_key
            value = data[offset: offset + 4]
            offset += 4
            r = [key, value]
            records.append(r)
        return offset, placeholder.meta.payload.implement(stats_type, records)
