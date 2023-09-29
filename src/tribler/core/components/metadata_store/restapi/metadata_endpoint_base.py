from dataclasses import asdict
from typing import Optional

from pony.orm import db_session

from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.components.knowledge.rules.knowledge_rules_processor import KnowledgeRulesProcessor
from tribler.core.components.metadata_store.category_filter.family_filter import default_xxx_filter
from tribler.core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.restapi.rest.rest_endpoint import RESTEndpoint

from tribler.core.utilities.utilities import parse_bool

# This dict is used to translate JSON fields into the columns used in Pony for _sorting_.
# id_ is not in the list because there is not index on it, so we never really want to sort on it.

json2pony_columns = {
    'category': "tags",
    'name': "title",
    'size': "size",
    'infohash': "infohash",
    'date': "torrent_date",
    'created': "torrent_date",
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
    def __init__(self, metadata_store: MetadataStore, *args, tribler_db: TriblerDatabase = None,
                 tag_rules_processor: KnowledgeRulesProcessor = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mds = metadata_store
        self.tribler_db: Optional[TriblerDatabase] = tribler_db
        self.tag_rules_processor: Optional[KnowledgeRulesProcessor] = tag_rules_processor

    @classmethod
    def sanitize_parameters(cls, parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        sanitized = {
            "first": int(parameters.get('first', 1)),
            "last": int(parameters.get('last', 50)),
            "sort_by": json2pony_columns.get(parameters.get('sort_by')),
            "sort_desc": parse_bool(parameters.get('sort_desc', True)),
            "txt_filter": parameters.get('txt_filter'),
            "hide_xxx": parse_bool(parameters.get('hide_xxx', False)),
            "category": parameters.get('category'),
            "exclude_deleted": parse_bool(parameters.get('exclude_deleted', False)),
        }
        if 'tags' in parameters:
            sanitized['tags'] = parameters.getall('tags')
        if "remote" in parameters:
            sanitized["remote"] = (parse_bool(parameters.get('remote', False)),)
        if 'metadata_type' in parameters:
            mtypes = []
            for arg in parameters.getall('metadata_type'):
                mtypes.extend(metadata_type_to_search_scope[arg])
            sanitized['metadata_type'] = frozenset(mtypes)
        return sanitized

    @db_session
    def add_statements_to_metadata_list(self, contents_list, hide_xxx=False):
        if self.tribler_db is None:
            self._logger.error(f'Cannot add statements to metadata list: '
                               f'tribler_db is not set in {self.__class__.__name__}')
            return
        for torrent in contents_list:
            if torrent['type'] == REGULAR_TORRENT:
                raw_statements = self.tribler_db.knowledge.get_statements(
                    subject_type=ResourceType.TORRENT,
                    subject=torrent["infohash"]
                )
                statements = [asdict(stmt) for stmt in raw_statements]
                if hide_xxx:
                    statements = [stmt for stmt in statements if not default_xxx_filter.isXXX(stmt["object"],
                                                                                              isFilename=False)]
                torrent["statements"] = statements
