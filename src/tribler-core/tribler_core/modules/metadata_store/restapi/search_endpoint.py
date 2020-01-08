import asyncio

from aiohttp import web

from pony.orm import db_session

from tribler_core.modules.metadata_store.restapi.metadata_endpoint import MetadataEndpointBase
from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse


class SearchEndpoint(MetadataEndpointBase):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    It also fires a remote search in the IPv8 channel community.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.search), web.get('/completions', self.completions)])

    @staticmethod
    def get_uuid(parameters):
        return parameters['uuid'] if 'uuid' in parameters else None

    async def search(self, request):
        """
        .. http:get:: /search?q=(string:query)

        A GET request to this endpoint will create a search.

        first and last options limit the range of the query.
        xxx_filter option disables xxx filter
        channel option limits search to a certain channel
        sort_by option sorts results in forward or backward, based on column name (e.g. "id" vs "-id")
        filter option uses FTS search on the chosen word* terms
        type option limits query to certain metadata types (e.g. "torrent" or "channel")

            **Example request**:

            .. sourcecode:: none

                curl -X GET 'http://localhost:8085/search?filter=ubuntu&first=0&last=30&type=torrent&sort_by=size'

            **Example response**:

            .. sourcecode:: javascript

                {
                   "torrents":[
                      {
                         "commit_status":1,
                         "num_leechers":0,
                         "date":"1539867830.0",
                         "relevance_score":0,
                         "id":21,
                         "size":923795456,
                         "category":"unknown",
                         "public_key":"4c69624e...",
                         "name":"ubuntu-18.10-live-server-amd64.iso",
                         "last_tracker_check":0,
                         "infohash":"8c4adbf9ebe66f1d804fb6a4fb9b74966c3ab609",
                         "num_seeders":0,
                         "type":"torrent"
                      },
                      ...
                   ],
                   "chant_dirty":false
                }
        """
        try:
            sanitized = self.sanitize_parameters(request.query)
        except (ValueError, KeyError):
            return RESTResponse({"error": "Error processing request parameters"}, status=HTTP_BAD_REQUEST)

        if not sanitized["txt_filter"]:
            return RESTResponse({"error": "Filter parameter missing"}, status=HTTP_BAD_REQUEST)

        include_total = request.query.get('include_total', '')
        search_uuid = SearchEndpoint.get_uuid(request.query)

        # Apart from the local search results, we also do remote search to get search results from peers in the
        # Giga channel community.
        if self.session.gigachannel_community and sanitized["first"] == 1:
            raw_metadata_type = request.query.get('metadata_type', '')
            self.session.gigachannel_community.send_search_request(
                sanitized['txt_filter'],
                metadata_type=raw_metadata_type,
                sort_by=sanitized['sort_by'],
                sort_asc=sanitized['sort_desc'],
                hide_xxx=sanitized['hide_xxx'],
                uuid=search_uuid,
            )

        def search_db():
            with db_session:
                pony_query = self.session.mds.MetadataNode.get_entries(**sanitized)
                total = self.session.mds.MetadataNode.get_total_count(**sanitized) if include_total else None
                search_results = [r.to_simple_dict() for r in pony_query]
            self.session.mds._db.disconnect()
            return search_results, total

        try:
            search_results, total = await asyncio.get_event_loop().run_in_executor(None, search_db)
        except Exception as e:
            self._logger.error("Error while performing DB search: %s", e)
            return RESTResponse(status=HTTP_BAD_REQUEST)

        response_dict = {
            "uuid": search_uuid,
            "results": search_results,
            "first": sanitized["first"],
            "last": sanitized["last"],
            "sort_by": sanitized["sort_by"],
            "sort_desc": sanitized["sort_desc"],
        }
        if total is not None:
            response_dict.update({"total": total})

        return RESTResponse(response_dict)

    async def completions(self, request):
        """
        .. http:get:: /search/completions?q=(string:query)

        A GET request to this endpoint will return autocompletion suggestions for the given query. For instance,
        when searching for "pioneer", this endpoint might return "pioneer one" if that torrent is present in the
        local database. This endpoint can be used to suggest terms to users while they type their search query.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/search/completions?q=pioneer

            **Example response**:

            .. sourcecode:: javascript

                {
                    "completions": ["pioneer one", "pioneer movie"]
                }
        """
        args = request.query
        if 'q' not in args:
            return RESTResponse({"error": "query parameter missing"}, status=HTTP_BAD_REQUEST)

        keywords = args['q'].strip().lower()
        # TODO: add XXX filtering for completion terms
        results = self.session.mds.TorrentMetadata.get_auto_complete_terms(keywords, max_terms=5)
        return RESTResponse({"completions": results})
