from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.restapi.rest_endpoint import RESTEndpoint

# This dict is used to translate JSON fields into the columns used in Pony for _sorting_.
# id_ is not in the list because there is not index on it, so we never really want to sort on it.
json2pony_columns = {
    'category': "tags",
    'name': "title",
    'size': "size",
    'infohash': "infohash",
    'date': "torrent_date",
    'updated': "torrent_date",
    'status': 'status',
    'torrents': 'num_entries',
    'votes': 'votes',
    'subscribed': 'subscribed',
    'health': 'HEALTH',
}

# TODO: use the same representation for metadata nodes as in the database
metadata_type_to_search_scope = {
    '': frozenset((REGULAR_TORRENT, CHANNEL_TORRENT, COLLECTION_NODE)),
    "channel": frozenset((CHANNEL_TORRENT, COLLECTION_NODE)),
    "torrent": frozenset((REGULAR_TORRENT,)),
    str(CHANNEL_TORRENT): frozenset((CHANNEL_TORRENT,)),
    str(REGULAR_TORRENT): frozenset((REGULAR_TORRENT,)),
    str(COLLECTION_NODE): frozenset((COLLECTION_NODE,)),
}


class MetadataEndpointBase(RESTEndpoint):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mds = None

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
        if "remote" in parameters:
            sanitized["remote"] = (bool(int(parameters.get('remote', 0)) > 0),)
        if 'metadata_type' in parameters:
            mtypes = []
            for arg in parameters.getall('metadata_type'):
                mtypes.extend(metadata_type_to_search_scope[arg])
            sanitized['metadata_type'] = frozenset(mtypes)
        return sanitized
