from binascii import unhexlify
from typing import Dict, Tuple, List

from aiohttp import web

from aiohttp_apispec import docs, querystring_schema

from ipv8.REST.schema import schema

from marshmallow.fields import Integer, String

from pony.orm import db_session

from tribler.core.components.metadata_store.db.serialization import SNIPPET
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.metadata_store.restapi.metadata_endpoint import MetadataEndpointBase
from tribler.core.components.metadata_store.restapi.metadata_schema import MetadataParameters, MetadataSchema
from tribler.core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse
from tribler.core.utilities.utilities import froze_it


SNIPPETS_TO_SHOW = 1          # The number of snippets we return from the search results
MAX_TORRENTS_IN_SNIPPETS = 4  # The maximum number of torrents in each snippet


@froze_it
class SearchEndpoint(MetadataEndpointBase):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Read content
        self.content: Dict[str, Tuple] = {}
        self.torrent_to_content: Dict[str, str] = {}

        with open("/Users/martijndevos/Documents/tribler/content.csv") as content_file:
            parsed_header = False
            for line in content_file.readlines():
                if not parsed_header:
                    parsed_header = True
                    continue

                parts = line.strip().split(",")
                content_id = parts[0]
                content_title = parts[1]
                content_year = parts[2]
                self.content[content_id] = (content_title, content_year)

        with open("/Users/martijndevos/Documents/tribler/content_relations.csv") as content_file:
            parsed_header = False
            for line in content_file.readlines():
                if not parsed_header:
                    parsed_header = True
                    continue

                parts = line.strip().split(",")
                content_id = parts[0]
                torrent_ih = parts[1]
                self.torrent_to_content[torrent_ih] = content_id

    def setup_routes(self):
        self.app.add_routes([web.get('', self.search), web.get('/completions', self.completions)])

    @classmethod
    def sanitize_parameters(cls, parameters):
        sanitized = super().sanitize_parameters(parameters)
        if "max_rowid" in parameters:
            sanitized["max_rowid"] = int(parameters["max_rowid"])
        return sanitized

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
    @querystring_schema(MetadataParameters)
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
                pony_query = mds.get_entries(**sanitized)
                search_results = [r.to_simple_dict() for r in pony_query]
                if include_total:
                    total = mds.get_total_count(**sanitized)
                    max_rowid = mds.get_max_rowid()
                else:
                    total = max_rowid = None
            return search_results, total, max_rowid

        try:
            with db_session:
                if tags:
                    infohash_set = self.tags_db.get_infohashes(set(tags))
                    sanitized['infohash_set'] = infohash_set

            search_results, total, max_rowid = await mds.run_threaded(search_db)
        except Exception as e:  # pylint: disable=broad-except;  # pragma: no cover
            self._logger.exception("Error while performing DB search: %s: %s", type(e).__name__, e)
            return RESTResponse(status=HTTP_BAD_REQUEST)

        self.add_tags_to_metadata_list(search_results, hide_xxx=sanitized["hide_xxx"])

        # Build snippets
        # TODO we probably need to do another database query to get ALL possible content that should go in the snippet
        if sanitized["first"] == 1:  # Only show a snippet on top
            content_to_torrents: Dict[str, list] = {}
            most_popular_torrents_for_content: Dict[str, List] = {}
            for search_result in search_results:
                if search_result["infohash"] in self.torrent_to_content:
                    content_id = self.torrent_to_content[search_result["infohash"]]
                    if content_id not in content_to_torrents:
                        content_to_torrents[content_id] = []
                    content_to_torrents[content_id].append(search_result)

                    if content_id not in most_popular_torrents_for_content:
                        most_popular_torrents_for_content[content_id] = []
                    most_popular_torrents_for_content[content_id].append(search_result)

            # Sort by popularity
            for torrents_list in most_popular_torrents_for_content.values():
                torrents_list.sort(key=lambda x: x["num_seeders"], reverse=True)

            # Determine the most popular content item - this is the one we show
            sorted_content_info = list(content_to_torrents.items())
            sorted_content_info.sort(key=lambda x: len(x[1]), reverse=True)
            snippets = []
            torrents_in_snippets = []

            for content_info in sorted_content_info:
                content_id = content_info[0]
                content = self.content[content_id]
                torrents_in_snippet = most_popular_torrents_for_content[content_id][:MAX_TORRENTS_IN_SNIPPETS]

                snippet = {
                    "type": SNIPPET,
                    "infohash": content_id,
                    "category": "",
                    "name": "%s (%s)" % (content[0], content[1]),
                    "torrents": len(content_info[1]),
                    "torrents_in_snippet": torrents_in_snippet
                }
                torrents_in_snippets += torrents_in_snippet
                snippets.append(snippet)

            snippets = snippets[:SNIPPETS_TO_SHOW]

            # Remove search results that are displayed in a snippet
            for snippet in snippets:
                torrents_in_snippets += content_to_torrents[snippet["infohash"]]

            search_results = [search_result for search_result in search_results if (search_result["infohash"] not in torrents_in_snippets)]
            search_results = snippets + search_results

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
