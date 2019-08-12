from __future__ import absolute_import

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from Tribler.util import cast_to_unicode_utf8

json2pony_columns = {
    u'category': "tags",
    u'id': "rowid",
    u'name': "title",
    u'size': "size",
    u'infohash': "infohash",
    u'date': "torrent_date",
    u'updated': "torrent_date",
    u'status': 'status',
    u'torrents': 'num_entries',
    u'votes': 'votes',
    u'health': 'HEALTH',
}

# TODO: use the same representation for metatada nodes as in the database
metadata_type_to_search_scope = {
    '': [REGULAR_TORRENT, CHANNEL_TORRENT, COLLECTION_NODE],
    "channel": [CHANNEL_TORRENT, COLLECTION_NODE],
    "torrent": [REGULAR_TORRENT],
    str(CHANNEL_TORRENT): [CHANNEL_TORRENT],
    str(REGULAR_TORRENT): [REGULAR_TORRENT],
    str(COLLECTION_NODE): [COLLECTION_NODE],
}


def convert_sort_param_to_pony_col(sort_param):
    """
    Convert an incoming sort parameter to a pony column in the database.
    :return a string with the right column. None if there exists no value for the given key.
    """

    return json2pony_columns[sort_param] if sort_param in json2pony_columns else None


class MetadataEndpointBase(RESTEndpoint):

    @classmethod
    def sanitize_parameters(cls, parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        sanitized = {
            "first": 1 if 'first' not in parameters else int(parameters['first']),
            "last": 50 if 'last' not in parameters else int(parameters['last']),
            "sort_by": None
            if 'sort_by' not in parameters
            else convert_sort_param_to_pony_col(parameters['sort_by']),
            "sort_desc": True if 'sort_desc' not in parameters else bool(int(parameters['sort_desc'])),
            "query_filter": None if 'filter' not in parameters else parameters['filter'],
            "hide_xxx": False if 'hide_xxx' not in parameters else bool(int(parameters['hide_xxx']) > 0),
            "category": None if 'category' not in parameters else parameters['category'],
            "exclude_deleted": None
            if 'exclude_deleted' not in parameters
            else bool(int(parameters['exclude_deleted']) > 0),
        }
        if 'metadata_type' in parameters:
            mtypes = []
            for arg in parameters.getall('metadata_type'):
                mtypes.extend(metadata_type_to_search_scope[arg])
            sanitized['metadata_type'] = mtypes
        return sanitized
