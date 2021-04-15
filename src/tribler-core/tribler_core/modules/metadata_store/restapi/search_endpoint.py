import asyncio

from aiohttp import web

from aiohttp_apispec import docs, querystring_schema

from ipv8.REST.schema import schema

from marshmallow.fields import Boolean, Integer, String

from pony.orm import db_session

from tribler_core.modules.metadata_store.restapi.metadata_endpoint import MetadataEndpointBase
from tribler_core.modules.metadata_store.restapi.metadata_schema import MetadataParameters
from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse


class SearchEndpoint(MetadataEndpointBase):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.search), web.get('/completions', self.completions)])

    @staticmethod
    def get_uuid(parameters):
        return parameters['uuid'] if 'uuid' in parameters else None

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
                        'torrents': [
                            schema(
                                Torrent={
                                    'commit_status': Integer,
                                    'num_leechers': Integer,
                                    'date': Integer,
                                    'relevance_score': Integer,
                                    'id': Integer,
                                    'size': Integer,
                                    'category': String,
                                    'public_key': String,
                                    'name': String,
                                    'last_tracker_check': Integer,
                                    'infohash': String,
                                    'num_seeders': Integer,
                                    'type': String,
                                }
                            )
                        ],
                        'chant_dirty': Boolean,
                    }
                )
            }
        },
    )
    @querystring_schema(MetadataParameters)
    async def search(self, request):
        try:
            sanitized = self.sanitize_parameters(request.query)
        except (ValueError, KeyError):
            return RESTResponse({"error": "Error processing request parameters"}, status=HTTP_BAD_REQUEST)

        if not sanitized["txt_filter"]:
            return RESTResponse({"error": "Filter parameter missing"}, status=HTTP_BAD_REQUEST)

        include_total = request.query.get('include_total', '')

        def search_db():
            try:
                with db_session:
                    pony_query = self.session.mds.get_entries(**sanitized)
                    search_results = [r.to_simple_dict() for r in pony_query]
                    if include_total:
                        total = self.session.mds.get_total_count(**sanitized)
                        max_rowid = self.session.mds.get_max_rowid()
                    else:
                        total = max_rowid = None
            finally:
                # DB must be disconnected explicitly if run on a thread
                self.session.mds._db.disconnect()  # pylint: disable=protected-access
            return search_results, total, max_rowid

        try:
            search_results, total, max_rowid = await asyncio.get_event_loop().run_in_executor(None, search_db)
        except Exception as e:  # pylint: disable=broad-except;  # pragma: no cover
            self._logger.error("Error while performing DB search: %s: %s", type(e).__name__, e)
            return RESTResponse(status=HTTP_BAD_REQUEST)

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
        results = self.session.mds.get_auto_complete_terms(keywords, max_terms=5)
        return RESTResponse({"completions": results})
