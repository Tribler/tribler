from __future__ import absolute_import

import struct
from struct import calcsize, pack, unpack_from

from Tribler.pyipv8.ipv8.messaging.payload import Payload
from Tribler.pyipv8.ipv8.messaging.serialization import default_serializer


def encode_values(values):
    encoded_list = [value.encode('utf-8') for value in values]
    return ''.join([pack('!H', len(encoded)) + encoded for encoded in encoded_list])


def decode_values(values_str):
    values = []
    index = 0
    while index < len(values_str):
        length = unpack_from('!H', values_str[index:])[0]
        index += calcsize('!H')
        values.append(values_str[index:index + length].decode('utf-8'))
        index += length
    return values


def unpack_responses(serialized_responses, as_payload=False):
    """
    Unpack a custom serialization of a list of SearchResponseItemPayload payloads.

    :param serialized_responses: the serialized data
    :return: [[str, str, int, int, str, int, int, int, str]] or SearchResponseItemPayload
    """
    data = serialized_responses
    out = []
    while data:
        unpacked, data = default_serializer.unpack_to_serializables([SearchResponseItemPayload], data)
        if as_payload:
            out.append(unpacked)
        else:
            out.append([unpacked.infohash, unpacked.name, unpacked.length, unpacked.num_files, unpacked.category_list,
                        unpacked.creation_date, unpacked.seeders, unpacked.leechers, unpacked.cid])
    return out


class ContentSubscription(Payload):

    format_list = ['I', '?']

    def __init__(self, identifier, subscribe):
        super(ContentSubscription, self).__init__()
        self.identifier = identifier
        self.subscribe = subscribe

    def to_pack_list(self):
        data = [('I', self.identifier),
                ('?', self.subscribe)]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (identifier, subscribe) = args
        return ContentSubscription(identifier, subscribe)


class TorrentHealthPayload(Payload):

    format_list = ['20s', 'I', 'I', 'Q']

    def __init__(self, infohash, num_seeders, num_leechers, timestamp):
        super(TorrentHealthPayload, self).__init__()
        self.infohash = infohash
        self.num_seeders = num_seeders or 0
        self.num_leechers = num_leechers or 0
        self.timestamp = timestamp or 0

    def to_pack_list(self):
        data = [('20s', self.infohash),
                ('I', self.num_seeders),
                ('I', self.num_leechers),
                ('Q', self.timestamp)]

        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (infohash, num_seeders, num_leechers, timestamp) = args
        return TorrentHealthPayload(infohash, num_seeders, num_leechers, timestamp)


class ChannelHealthPayload(Payload):
    """
    Payload for a channel popularity message in the popularity community.
    """

    format_list = ['varlenI', 'I', 'I', 'I', 'Q']

    def __init__(self, channel_id, num_votes, num_torrents, swarm_size_sum, timestamp):
        super(ChannelHealthPayload, self).__init__()
        self.channel_id = channel_id
        self.num_votes = num_votes or 0
        self.num_torrents = num_torrents or 0
        self.swarm_size_sum = swarm_size_sum or 0
        self.timestamp = timestamp or 0

    def to_pack_list(self):
        data = [('varlenI', self.channel_id),
                ('I', self.num_votes),
                ('I', self.num_torrents),
                ('I', self.swarm_size_sum),
                ('Q', self.timestamp)]

        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (channel_id, num_votes, num_torrents, swarm_size_sum, timestamp) = args
        return ChannelHealthPayload(channel_id, num_votes, num_torrents, swarm_size_sum, timestamp)


class TorrentInfoRequestPayload(Payload):
    """
    Payload for requesting torrent info for a given infohash.
    """
    format_list = ['20s']

    def __init__(self, infohash):
        super(TorrentInfoRequestPayload, self).__init__()
        self.infohash = infohash

    def to_pack_list(self):
        data = [('20s', str(self.infohash))]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (infohash, ) = args
        return TorrentInfoRequestPayload(infohash)


class TorrentInfoResponsePayload(Payload):
    """
    Payload for torrent info response.
    """
    format_list = ['20s', 'varlenH', 'Q', 'Q', 'I', 'varlenH']

    def __init__(self, infohash, name, length, creation_date, num_files, comment):
        super(TorrentInfoResponsePayload, self).__init__()
        self.infohash = infohash
        self.name = name or ''
        self.length = length or 0
        self.creation_date = creation_date or 0
        self.num_files = num_files or 0
        self.comment = comment or ''

    def to_pack_list(self):
        data = [('20s', self.infohash),
                ('varlenH', self.name.encode('utf-8')),
                ('Q', self.length),
                ('Q', self.creation_date),
                ('I', self.num_files),
                ('varlenH', str(self.comment))]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (infohash, name, length, creation_date, num_files, comment) = args
        return TorrentInfoResponsePayload(infohash, name.decode('utf-8'), length, creation_date, num_files, comment)


class SearchResponseItemPayload(Payload):
    """
    Payload for search response items
    """

    format_list = ['20s', 'varlenH', 'Q', 'I', 'varlenH', 'Q', 'I', 'I', '20s']
    is_list_descriptor = True

    def __init__(self, infohash, name, length, num_files, category_list, creation_date, seeders, leechers, cid):
        self.infohash = infohash
        self.name = name
        self.length = length or 0
        self.num_files = num_files or 0
        self.category_list = category_list or []
        self.creation_date = creation_date or 0
        self.seeders = seeders or 0
        self.leechers = leechers or 0
        self.cid = cid

    def to_pack_list(self):
        data = [('20s', str(self.infohash)),
                ('varlenH', self.name.encode('utf-8')),
                ('Q', self.length),
                ('I', self.num_files),
                ('varlenH', encode_values(self.category_list)),
                ('Q', self.creation_date),
                ('I', self.seeders),
                ('I', self.leechers),
                ('20s', self.cid if self.cid else '')]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (infohash, name, length, num_files, category_list_str, creation_date, seeders, leechers, cid) = args
        category_list = decode_values(category_list_str)
        return SearchResponseItemPayload(infohash, name.decode('utf-8'), length, num_files, category_list,
                                         creation_date, seeders, leechers, cid)


class ChannelItemPayload(Payload):
    """
    Payload for search response channel items
    """
    format_list = ['I', '20s', 'varlenH', 'varlenH', 'I', 'I', 'I', 'Q']
    is_list_descriptor = True

    def __init__(self, dbid, dispersy_cid, name, description, nr_torrents, nr_favorite, nr_spam, modified):
        self.id = dbid
        self.name = name
        self.description = description or ''
        self.cid = dispersy_cid
        self.modified = modified or 0
        self.nr_torrents = nr_torrents or 0
        self.nr_favorite = nr_favorite or 0
        self.nr_spam = nr_spam or 0

    def to_pack_list(self):
        data = [('I', id),
                ('20s', str(self.cid)),
                ('varlenH', self.name),
                ('varlenH', self.description.encode('utf-8')),
                ('I', self.nr_torrents),
                ('I', self.nr_favorite),
                ('I', self.nr_spam),
                ('Q', self.modified)]
        return data

    @classmethod
    def from_unpack_list(cls, dbid, dispersy_cid, name, description, nr_torrents, nr_favorite, nr_spam, modified):
        return ChannelItemPayload(dbid, dispersy_cid, name.decode('utf-8'), description.decode('utf-8'), nr_torrents,
                                  nr_favorite, nr_spam, modified)


class SearchResponsePayload(Payload):
    """
    Payload for search response
    """
    format_list = ['varlenI', 'I', 'varlenH']

    def __init__(self, identifier, response_type, results):
        self.identifier = identifier
        self.response_type = response_type
        self.results = results

    def to_pack_list(self):
        data = [('varlenI', str(self.identifier)),
                ('I', self.response_type),
                ('varlenH', self.results)]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (identifier, response_type, results) = args
        return SearchResponsePayload(identifier, response_type, results)


class Pagination(object):

    def __init__(self, page_number, page_size, max_results, more):
        self.page_number = page_number
        self.page_size = page_size
        self.max_results = max_results
        self.more = more

    def serialize(self):
        return struct.pack('!HHH?', self.page_number, self.page_size, self.max_results, self.more)

    @classmethod
    def deserialize(cls, pagination_str):
        return Pagination(*struct.unpack('!HHH?', pagination_str))


class ContentInfoRequest(Payload):
    """ Payload for generic content request """

    format_list = ['I', 'I', 'varlenH', 'I']

    def __init__(self, identifier, content_type, query_list, limit):
        self.identifier = identifier
        self.content_type = content_type
        self.query_list = query_list
        self.limit = limit

    def to_pack_list(self):
        data = [('I', self.identifier),
                ('I', self.content_type),
                ('varlenH', encode_values(self.query_list)),
                ('I', self.limit)]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (identifier, content_type, query_list_str, limit) = args
        query_list = decode_values(query_list_str)
        return ContentInfoRequest(identifier, content_type, query_list, limit)


class ContentInfoResponse(Payload):
    """ Payload for generic content response """

    format_list = ['I', 'I', 'varlenH', 'varlenH']

    def __init__(self, identifier, content_type, response, pagination):
        self.identifier = identifier
        self.content_type = content_type
        self.response = response
        self.pagination = pagination

    def to_pack_list(self):
        data = [('I', self.identifier),
                ('I', self.content_type),
                ('varlenH', self.response),
                ('varlenH', self.pagination.serialize())]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (identifier, content_type, response, pagination_str) = args
        pagination = Pagination.deserialize(pagination_str)
        return ContentInfoResponse(identifier, content_type, response, pagination)
