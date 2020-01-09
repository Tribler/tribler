from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.restapi.rest_endpoint import RESTEndpoint

json2pony_columns = {
    'category': "tags",
    'id': "rowid",
    'name': "title",
    'size': "size",
    'infohash': "infohash",
    'date': "torrent_date",
    'updated': "torrent_date",
    'status': 'status',
    'torrents': 'num_entries',
    'votes': 'votes',
    'health': 'HEALTH',
}

# TODO: use the same representation for metatada nodes as in the database
metadata_type_to_search_scope = {
    '': frozenset((REGULAR_TORRENT, CHANNEL_TORRENT, COLLECTION_NODE)),
    "channel": frozenset((CHANNEL_TORRENT, COLLECTION_NODE)),
    "torrent": frozenset((REGULAR_TORRENT,)),
    str(CHANNEL_TORRENT): frozenset((CHANNEL_TORRENT,)),
    str(REGULAR_TORRENT): frozenset((REGULAR_TORRENT,)),
    str(COLLECTION_NODE): frozenset((COLLECTION_NODE,)),
}


class MetadataEndpointBase(RESTEndpoint):
    @classmethod
    def sanitize_parameters(cls, parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        sanitized = {
            "first": int(parameters.get('first', 1)),
            "last": int(parameters.get('last', 50)),
            "sort_by": json2pony_columns.get(parameters.get('sort_by')),
            "sort_desc": bool(int(parameters.get('sort_desc', 1)) > 0),
            "txt_filter": parameters.get('txt_filter'),
            "hide_xxx": bool(int(parameters.get('hide_xxx', 0)) > 0),
            "category": parameters.get('category'),
            "exclude_deleted": bool(int(parameters.get('exclude_deleted', 0)) > 0),
        }
        if 'remote_query' in parameters:
            sanitized["remote_query"] = (bool(int(parameters.get('remote_query', 0)) > 0),)
        if 'metadata_type' in parameters:
            mtypes = []
            for arg in parameters.getall('metadata_type'):
                mtypes.extend(metadata_type_to_search_scope[arg])
            sanitized['metadata_type'] = frozenset(mtypes)
        return sanitized
