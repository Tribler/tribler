import time
from collections import defaultdict
from typing import Dict, List

from aiohttp import web
from aiohttp_apispec import docs, querystring_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Integer, String
from pony.orm import db_session

from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.core.components.metadata_store.db.serialization import SNIPPET
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.metadata_store.restapi.metadata_endpoint import MetadataEndpointBase
from tribler.core.components.metadata_store.restapi.metadata_schema import MetadataSchema, SearchMetadataParameters
from tribler.core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse
from tribler.core.utilities.pony_utils import run_threaded
from tribler.core.utilities.utilities import froze_it

SNIPPETS_TO_SHOW = 3  # The number of snippets we return from the search results
MAX_TORRENTS_IN_SNIPPETS = 4  # The maximum number of torrents in each snippet


@froze_it
class SearchEndpoint(MetadataEndpointBase):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    """
    path = '/search'

    def setup_routes(self):
        self.app.add_routes([web.get('', self.search), web.get('/completions', self.completions)])

    @classmethod
    def sanitize_parameters(cls, parameters):
        sanitized = super().sanitize_parameters(parameters)
        if "max_rowid" in parameters:
            sanitized["max_rowid"] = int(parameters["max_rowid"])
        return sanitized

    def build_snippets(self, search_results: List[Dict]) -> List[Dict]:
        """
        Build a list of snippets that bundle torrents describing the same content item.
        For each search result we determine the content item it is associated to and bundle it inside a snippet.
        We sort the snippets based on the number of torrents inside the snippet.
        Within each snippet, we sort on torrent popularity, putting the torrent with the most seeders on top.
        Torrents bundled in a snippet are filtered out from the search results.
        """
        content_to_torrents: Dict[str, list] = defaultdict(list)
        for search_result in search_results:
            if "infohash" not in search_result:
                continue
            with db_session:
                content_items: List[str] = self.tribler_db.knowledge.get_objects(subject_type=ResourceType.TORRENT,
                                                                                 subject=search_result["infohash"],
                                                                                 predicate=ResourceType.CONTENT_ITEM)
            if content_items:
                for content_id in content_items:
                    content_to_torrents[content_id].append(search_result)

        # Sort the search results within each snippet by the number of seeders
        for torrents_list in content_to_torrents.values():
            torrents_list.sort(key=lambda x: x["num_seeders"], reverse=True)

        # Determine the most popular content items - this is the one we show
        sorted_content_info = list(content_to_torrents.items())
        sorted_content_info.sort(key=lambda x: x[1][0]["num_seeders"], reverse=True)

        snippets: List[Dict] = []
        for content_info in sorted_content_info:
            content_id = content_info[0]
            torrents_in_snippet = content_to_torrents[content_id][:MAX_TORRENTS_IN_SNIPPETS]

            snippet = {
                "type": SNIPPET,
                "infohash": content_id,
                "category": "",
                "name": content_id,
                "torrents": len(content_info[1]),
                "torrents_in_snippet": torrents_in_snippet
            }
            snippets.append(snippet)

        snippets = snippets[:SNIPPETS_TO_SHOW]

        # Filter out search results that are included in a snippet
        torrents_in_snippets = set()
        for snippet in snippets:
            snippet_id = snippet["infohash"]
            infohases = {search_result["infohash"] for search_result in content_to_torrents[snippet_id]}
            torrents_in_snippets |= infohases

        search_results = [search_result for search_result in search_results if
                          (("infohash" not in search_result) or
                           (search_result["infohash"] not in torrents_in_snippets))]
        return snippets + search_results

    @docs(
        tags=['Metadata'],
        summary="Perform a search for a given query.",
        responses={
            200: {
                'schema': schema(
                    SearchResponse={
                        'results': [MetadataSchema],
                        'first': Integer(),
                        'last': Integer(),
                        'sort_by': String(),
                        'sort_desc': Integer(),
                        'total': Integer(),
                    }
                )
            }
        },
    )
    @querystring_schema(SearchMetadataParameters)
    async def search(self, request):
        try:
            sanitized = self.sanitize_parameters(request.query)
            tags = sanitized.pop('tags', None)
        except (ValueError, KeyError):
            return RESTResponse({"error": "Error processing request parameters"}, status=HTTP_BAD_REQUEST)

        include_total = request.query.get('include_total', '')

        mds: MetadataStore = self.mds

        def search_db():
            with db_session:
                t1 = time.time()
                pony_query = mds.get_entries(**sanitized)
                t2 = time.time()
                search_results = [r.to_simple_dict() for r in pony_query]
                t3 = time.time()
                if include_total:
                    total = mds.get_total_count(**sanitized)
                    t4 = time.time()
                    max_rowid = mds.get_max_rowid()
                    t5 = time.time()
                    self._logger.info(f'Search performance for {sanitized}:\n'
                                      f'Main query executed in {t2 - t1:.6} seconds;\n'
                                      f'Result constructed in {t3 - t2:.6} seconds;\n'
                                      f'Total rows count calculated in {t4 - t3:.6} seconds;\n'
                                      f'Max rowid determined in {t5 - t4:.6} seconds.')
                else:
                    total = max_rowid = None
                    self._logger.info(f'Search performance for {sanitized}:\n'
                                      f'Main query executed in {t2 - t1:.6} seconds;\n'
                                      f'Result constructed in {t3 - t2:.6} seconds.')

            return search_results, total, max_rowid

        try:
            with db_session:
                if tags:
                    infohash_set = self.tribler_db.knowledge.get_subjects_intersection(
                        subjects_type=ResourceType.TORRENT,
                        objects=set(tags),
                        predicate=ResourceType.TAG,
                        case_sensitive=False)
                    if infohash_set:
                        sanitized['infohash_set'] = {bytes.fromhex(s) for s in infohash_set}

            search_results, total, max_rowid = await run_threaded(mds.db, search_db)
        except Exception as e:  # pylint: disable=broad-except;  # pragma: no cover
            self._logger.exception("Error while performing DB search: %s: %s", type(e).__name__, e)
            return RESTResponse(status=HTTP_BAD_REQUEST)

        if self.tag_rules_processor:
            await self.tag_rules_processor.process_queue()

        self.add_statements_to_metadata_list(search_results, hide_xxx=sanitized["hide_xxx"])

        if sanitized["first"] == 1:  # Only show a snippet on top
            search_results = self.build_snippets(search_results)

        response_dict = {
            "results": search_results,
            "first": sanitized["first"],
            "last": sanitized["last"],
            "sort_by": sanitized["sort_by"],
            "sort_desc": sanitized["sort_desc"],
        }
        if include_total:
            response_dict.update(total=total, max_rowid=max_rowid)

        return RESTResponse(response_dict)

    @docs(
        tags=['Metadata'],
        summary="Return auto-completion suggestions for a given query.",
        parameters=[{'in': 'query', 'name': 'q', 'description': 'Search query', 'type': 'string', 'required': True}],
        responses={
            200: {
                'schema': schema(
                    CompletionsResponse={
                        'completions': [String],
                    }
                ),
                'examples': {'completions': ['pioneer one', 'pioneer movie']},
            }
        },
    )
    async def completions(self, request):
        args = request.query
        if 'q' not in args:
            return RESTResponse({"error": "query parameter missing"}, status=HTTP_BAD_REQUEST)

        keywords = args['q'].strip().lower()
        # TODO: add XXX filtering for completion terms
        results = self.mds.get_auto_complete_terms(keywords, max_terms=5)
        return RESTResponse({"completions": results})
