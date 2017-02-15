from struct import pack, unpack_from

from Tribler.community.basecommunity import BaseConversion
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.payload import Payload

"""Backward compatibility for Bartercast4.

    Usage:
        1. Create TemplateCompatibility(newcommunity)
        2. Register compatibility.deprecated_meta_messages()
        3. Register Conversion

"""

class StatisticsRequestPayload(Payload):
    '''
    Request statistics for key 'key' from peer.
    '''

    class Implementation(Payload.Implementation):

        def __init__(self, meta, stats_type):
            super(StatisticsRequestPayload.Implementation, self).__init__(meta)
            self.stats_type = stats_type


class StatisticsResponsePayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, stats_type, records):
            super(StatisticsResponsePayload.Implementation, self).__init__(meta)
            self.stats_type = stats_type
            self.records = records

class StatisticsConversion(BaseConversion):

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

class Bartercast4Compatibility:

    """Class for providing backward compatibility for
        the Bartercast4 community.
    """

    def __init__(self, parent):
        self.parent = parent

    def deprecated_meta_messages(self):
        return [Message(self.parent,
                        u"stats-request",
                        MemberAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        StatisticsRequestPayload(),
                        self.check_stats_request,
                        self.on_stats_request),
                Message(self.parent,
                        u"stats-response",
                        MemberAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        StatisticsResponsePayload(),
                        self.check_stats_response,
                        self.on_stats_response)
               ]

    class Mock:
        innerdict = {}
        def put(self, field, value):
            self.innerdict[field] = value
        def __getattr__(self, name):
            if name in self.innerdict:
                return self.innerdict[name]
            else:
                raise AttributeError

    def _reconstruct_statsrequest(self, message):
        mock_main = self.Mock()
        mock_main.put('statstype', message.payload.stats_type)
        return mock_main

    def _reconstruct_statsresponse(self, message):
        mock_main = self.Mock()
        mock_main.put('statstype', message.payload.stats_type)
        mock_records = []
        for r in message.payload.records:
            mock_record = self.Mock()
            mock_record.put('peerid', r[0])
            mock_record.put('value', r[1])
            mock_records.append(mock_record)
        mock_main.put('records', mock_records)
        return mock_main

    def check_stats_request(self, messages):
        for message in messages:
            out = self.parent.check_statsrequest(message, self._reconstruct_statsrequest(message)).next()
            yield out

    def on_stats_request(self, messages):
        for message in messages:
            self.parent.on_statsrequest(message, self._reconstruct_statsrequest(message))

    def check_stats_response(self, messages):
        for message in messages:
            out = self.parent.check_statsresponse(message, self._reconstruct_statsresponse(message)).next()
            yield out

    def on_stats_response(self, messages):
        for message in messages:
            self.parent.on_statsresponse(message, self._reconstruct_statsresponse(message))
