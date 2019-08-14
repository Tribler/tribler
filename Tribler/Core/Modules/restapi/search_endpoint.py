from __future__ import absolute_import

import logging

from pony.orm import db_session

from twisted.internet.threads import deferToThread
from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.metadata_endpoint import MetadataEndpointBase
from Tribler.Core.Utilities.unicode import recursive_unicode


class SearchEndpoint(MetadataEndpointBase):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    It also fires a remote search in the IPv8 channel community.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.events_endpoint = None
        self._logger = logging.getLogger(self.__class__.__name__)

        self.putChild(b"completions", SearchCompletionsEndpoint(session))

    @staticmethod
    def get_uuid(parameters):
        return parameters['uuid'][0] if 'uuid' in parameters else None

    def render_GET(self, request):
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
            args = recursive_unicode(request.args)
            sanitized = self.sanitize_parameters(args)
        except (ValueError, KeyError):
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "Error processing request parameters"})

        if not sanitized["query_filter"]:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "filter parameter missing"})

        include_total = request.args['include_total'][0] if 'include_total' in request.args else ''
        search_uuid = SearchEndpoint.get_uuid(args)

        # Apart from the local search results, we also do remote search to get search results from peers in the
        # Giga channel community.
        if self.session.lm.gigachannel_community and sanitized["first"] == 1:
            raw_metadata_type = args['metadata_type'][0] if 'metadata_type' in args else ''
            self.session.lm.gigachannel_community.send_search_request(
                sanitized['query_filter'],
                metadata_type=raw_metadata_type,
                sort_by=sanitized['sort_by'],
                sort_asc=sanitized['sort_desc'],
                hide_xxx=sanitized['hide_xxx'],
                uuid=search_uuid,
            )

        def search_db():
            with db_session:
                pony_query = self.session.lm.mds.MetadataNode.get_entries(**sanitized)
                total = self.session.lm.mds.MetadataNode.get_total_count(**sanitized) if include_total else None
                search_results = [r.to_simple_dict() for r in pony_query]
            self.session.lm.mds._db.disconnect()
            return search_results, total

        def on_search_results(search_results_tuple):
            search_results, total = search_results_tuple
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

            request.write(json.twisted_dumps(response_dict))
            request.finish()

        def on_error(failure):
            self._logger.error("Error while performing DB search: %s", failure)
            request.setResponseCode(http.BAD_REQUEST)
            request.finish()

        deferToThread(search_db).addCallbacks(on_search_results, on_error)
        return NOT_DONE_YET


class SearchCompletionsEndpoint(resource.Resource):
    """
    This class is responsible for managing requests regarding the search completions terms of a query.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
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
        args = recursive_unicode(request.args)
        if 'q' not in args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "query parameter missing"})

        keywords = args['q'][0].lower()
        # TODO: add XXX filtering for completion terms
        results = self.session.lm.mds.MetadataNode.get_auto_complete_terms(keywords, max_terms=5)
        return json.twisted_dumps({"completions": results})
