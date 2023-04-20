from dataclasses import asdict
from typing import Optional

from pony.orm import db_session

from tribler.core.components.knowledge.db.knowledge_db import KnowledgeDatabase, ResourceType
from tribler.core.components.knowledge.rules.knowledge_rules_processor import KnowledgeRulesProcessor
from tribler.core.components.metadata_store.category_filter.family_filter import default_xxx_filter
from tribler.core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.restapi.rest.rest_endpoint import RESTEndpoint
# This dict is used to translate JSON fields into the columns used in Pony for _sorting_.
# id_ is not in the list because there is not index on it, so we never really want to sort on it.
from tribler.core.utilities.unicode import hexlify

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
    def __init__(self, metadata_store: MetadataStore, *args, knowledge_db: KnowledgeDatabase = None,
                 tag_rules_processor: KnowledgeRulesProcessor = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mds = metadata_store
        self.knowledge_db: Optional[KnowledgeDatabase] = knowledge_db
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
            "sort_desc": bool(int(parameters.get('sort_desc', 1)) > 0),
            "txt_filter": parameters.get('txt_filter'),
            "hide_xxx": bool(int(parameters.get('hide_xxx', 0)) > 0),
            "category": parameters.get('category'),
            "exclude_deleted": bool(int(parameters.get('exclude_deleted', 0)) > 0),
        }
        if 'tags' in parameters:
            sanitized['tags'] = parameters.getall('tags')
        if "remote" in parameters:
            sanitized["remote"] = (bool(int(parameters.get('remote', 0)) > 0),)
        if 'metadata_type' in parameters:
            mtypes = []
            for arg in parameters.getall('metadata_type'):
                mtypes.extend(metadata_type_to_search_scope[arg])
            sanitized['metadata_type'] = frozenset(mtypes)
        return sanitized

    def extract_tags(self, entry):
        is_torrent = entry.get_type() == REGULAR_TORRENT
        if not is_torrent or not self.tag_rules_processor:
            return

        is_auto_generated_tags_not_created = entry.tag_processor_version is None or \
                                             entry.tag_processor_version < self.tag_rules_processor.version
        if is_auto_generated_tags_not_created:
            generated = self.tag_rules_processor.process_torrent_title(infohash=entry.infohash, title=entry.title)
            entry.tag_processor_version = self.tag_rules_processor.version
            self._logger.info(f'Generated {generated} tags for {hexlify(entry.infohash)}')

    @db_session
    def add_statements_to_metadata_list(self, contents_list, hide_xxx=False):
        if self.knowledge_db is None:
            self._logger.error(f'Cannot add statements to metadata list: '
                               f'knowledge_db is not set in {self.__class__.__name__}')
            return
        for torrent in contents_list:
            if torrent['type'] == REGULAR_TORRENT:
                raw_statements = self.knowledge_db.get_statements(
                    subject_type=ResourceType.TORRENT,
                    subject=torrent["infohash"]
                )
                statements = [asdict(stmt) for stmt in raw_statements]
                if hide_xxx:
                    statements = [stmt for stmt in statements if not default_xxx_filter.isXXX(stmt["object"],
                                                                                              isFilename=False)]
                torrent["statements"] = statements
