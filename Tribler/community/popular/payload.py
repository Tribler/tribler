import struct
from struct import pack, unpack_from, calcsize

from Tribler.pyipv8.ipv8.deprecated.payload import Payload


def encode_values(values):
    return ''.join([pack('!H', len(value)) + str(value) for value in values])


def decode_values(values_str):
    values = []
    index = 0
    while index < len(values_str):
        length = unpack_from('!H', values_str)[0]
        index += calcsize('!H')
        values.append(values_str[index:index + length])
        index += length
    return values


class ContentSubscription(Payload):

    format_list = ['?']

    def __init__(self, subscribe):
        super(ContentSubscription, self).__init__()
        self.subscribe = subscribe

    def to_pack_list(self):
        data = [('?', self.subscribe)]
        return data

    @classmethod
    def from_unpack_list(cls, subscribe):
        return ContentSubscription(subscribe)


class TorrentHealthPayload(Payload):

    format_list = ['20s', 'I', 'I', 'I']

    def __init__(self, infohash, num_seeders, num_leechers, timestamp):
        super(TorrentHealthPayload, self).__init__()
        self._infohash = infohash
        self._num_seeders = num_seeders
        self._num_leechers = num_leechers
        self._timestamp = timestamp

    def to_pack_list(self):
        data = [('20s', self.infohash),
                ('I', self.num_seeders),
                ('I', self.num_leechers),
                ('I', self.timestamp)]

        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (infohash, num_seeders, num_leechers, timestamp) = args
        return TorrentHealthPayload(infohash, num_seeders, num_leechers, timestamp)

    @property
    def infohash(self):
        return self._infohash

    @property
    def num_seeders(self):
        return self._num_seeders

    @property
    def num_leechers(self):
        return self._num_leechers

    @property
    def timestamp(self):
        return self._timestamp


class ChannelHealthPayload(Payload):
    """
    Payload for a channel popularity message in the popular community.
    """

    format_list = ['varlenI', 'I', 'I', 'I', 'I']

    def __init__(self, channel_id, num_votes, num_torrents, swarm_size_sum, timestamp):
        super(ChannelHealthPayload, self).__init__()
        self.channel_id = channel_id
        self.num_votes = num_votes
        self.num_torrents = num_torrents
        self.swarm_size_sum = swarm_size_sum
        self.timestamp = timestamp

    def to_pack_list(self):
        data = [('varlenI', self.channel_id),
                ('I', self.num_votes),
                ('I', self.num_torrents),
                ('I', self.swarm_size_sum),
                ('I', self.timestamp)]

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
        infohash = args
        return TorrentInfoRequestPayload(infohash)


class TorrentInfoResponsePayload(Payload):
    """
    Payload for torrent info response.
    """
    format_list = ['20s', 'varlenH', 'I', 'I', 'I', 'varlenH']

    def __init__(self, infohash, name, length, creation_date, num_files, comment):
        super(TorrentInfoResponsePayload, self).__init__()
        self._infohash = infohash
        self._name = name
        self._length = length
        self._creation_date = creation_date
        self._num_files = num_files
        self._comment = comment

    def to_pack_list(self):
        data = [('20s', self.infohash),
                ('varlenH', str(self._name)),
                ('I', self._length),
                ('I', self._creation_date),
                ('I', self._num_files),
                ('varlenH', str(self._comment))]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (infohash, name, length, creation_date, num_files, comment) = args
        return TorrentInfoResponsePayload(infohash, name, length, creation_date, num_files, comment)

    @property
    def infohash(self):
        return self._infohash


class SearchRequestPayload(Payload):
    """
    Payload for search request
    """
    format_list = ['I', 'I', 'varlenH']

    def __init__(self, identifier, search_type, query):
        super(SearchRequestPayload, self).__init__()
        self.identifier = identifier
        self.search_type = search_type
        self.query = query

    def to_pack_list(self):
        data = [('I', self.identifier),
                ('I', self.search_type),
                ('varlenH', str(self.query))]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (timestamp, search_type, query) = args
        return SearchRequestPayload(timestamp, search_type, query)


class SearchResponseItemPayload(Payload):
    """
    Payload for search response items
    """

    format_list = ['20s', 'varlenH', 'Q', 'I', 'varlenH', 'l', 'I', 'I', '20s']
    is_list_descriptor = True

    def __init__(self, infohash, name, length, num_files, category_list, creation_date, seeders, leechers, cid):
        self.infohash = infohash
        self.name = name
        self.length = length
        self.num_files = num_files
        self.category_list = category_list
        self.creation_date = creation_date
        self.seeders = seeders
        self.leechers = leechers
        self.cid = cid

    def to_pack_list(self):
        data = [('20s', str(self.infohash)),
                ('varlenH', str(self.name)),
                ('Q', self.length),
                ('I', self.num_files),
                ('varlenH', encode_values(self.category_list)),
                ('l', self.creation_date),
                ('I', self.seeders),
                ('I', self.leechers),
                ('20s', self.cid if self.cid else '')]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (infohash, name, length, num_files, category_list_str, creation_date, seeders, leechers, cid) = args
        category_list = decode_values(category_list_str)
        return SearchResponseItemPayload(infohash, name, length, num_files, category_list, creation_date, seeders,
                                         leechers, cid)


class ChannelItemPayload(Payload):
    """
    Payload for search response channel items
    """
    format_list = ['I', '20s', 'varlenH', 'varlenH', 'I', 'I', 'I', 'I']
    is_list_descriptor = True

    def __init__(self, dbid, dispersy_cid, name, description, nr_torrents, nr_favorite, nr_spam, modified):
        self.id = dbid
        self.name = name
        self.description = description
        self.cid = dispersy_cid
        self.modified = modified
        self.nr_torrents = nr_torrents
        self.nr_favorite = nr_favorite
        self.nr_spam = nr_spam

    def to_pack_list(self):
        data = [('I', id),
                ('20s', str(self.cid)),
                ('varlenH', self.name),
                ('varlenH', self.description),
                ('I', self.nr_torrents),
                ('I', self.nr_favorite),
                ('I', self.nr_spam),
                ('I', self.modified)]
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        (dbid, dispersy_cid, name, description, nr_torrents, nr_favorite, nr_spam, modified) = args[:8]
        return ChannelItemPayload(dbid, dispersy_cid, name, description, nr_torrents, nr_favorite, nr_spam, modified)


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
