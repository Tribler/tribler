from __future__ import absolute_import

import logging

from pony.orm import db_session

from twisted.internet.threads import deferToThread
from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from Tribler.Core.Modules.restapi.metadata_endpoint import BaseMetadataEndpoint
from Tribler.util import cast_to_unicode_utf8


class SearchEndpoint(BaseMetadataEndpoint):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database. It also
    fires a remote search in the Dispersy communities.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.events_endpoint = None
        self._logger = logging.getLogger(self.__class__.__name__)

        self.putChild("completions", SearchCompletionsEndpoint(session))

    @staticmethod
    def convert_datatype_param_to_search_scope(data_type):
        return {'': [REGULAR_TORRENT, CHANNEL_TORRENT],
                "channel": CHANNEL_TORRENT,
                "torrent": REGULAR_TORRENT}.get(data_type)

    @staticmethod
    def sanitize_parameters(parameters):
        sanitized = BaseMetadataEndpoint.sanitize_parameters(parameters)
        sanitized['metadata_type'] = SearchEndpoint.convert_datatype_param_to_search_scope(
            parameters['metadata_type'][0] if 'metadata_type' in parameters else '')
        return sanitized

    def render_GET(self, request):
        """
        .. http:get:: /search?q=(string:query)

        A GET request to this endpoint will create a search.

        first and last options limit the range of the query.
        xxx_filter option disables xxx filter
        channel option limits search to a certain channel
        sort_by option sorts results in forward or backward, based on column name (e.g. "id" vs "-id")
        txt option uses FTS search on the chosen word* terms
        type option limits query to certain metadata types (e.g. "torrent" or "channel")

            **Example request**:

            .. sourcecode:: none

                curl -X GET 'http://localhost:8085/search?txt=ubuntu&first=0&last=30&type=torrent&sort_by=size'

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
        sanitized = SearchEndpoint.sanitize_parameters(request.args)

        if not sanitized["query_filter"]:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "filter parameter missing"})

        if not sanitized["metadata_type"]:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "Trying to query for unknown type of metadata"})

        # Apart from the local search results, we also do remote search to get search results from peers in the
        # Giga channel community.
        if self.session.lm.gigachannel_community and sanitized["first"] == 1:
            raw_metadata_type = request.args['metadata_type'][0] if 'metadata_type' in request.args else ''
            self.session.lm.gigachannel_community.send_search_request(sanitized['query_filter'],
                                                                      metadata_type=raw_metadata_type,
                                                                      sort_by=sanitized['sort_by'],
                                                                      sort_asc=sanitized['sort_asc'],
                                                                      hide_xxx=sanitized['hide_xxx'])

        def search_db():
            with db_session:
                pony_query, total = self.session.lm.mds.TorrentMetadata.get_entries(**sanitized)
                search_results = [(dict(type={REGULAR_TORRENT: 'torrent', CHANNEL_TORRENT: 'channel'}[r.metadata_type],
                                        **(r.to_simple_dict()))) for r in pony_query]
            self.session.lm.mds._db.disconnect()
            return search_results, total

        def on_search_results(search_results_tuple):
            search_results, total = search_results_tuple
            request.write(json.dumps({
                "results": search_results,
                "first": sanitized["first"],
                "last": sanitized["last"],
                "sort_by": sanitized["sort_by"],
                "sort_asc": sanitized["sort_asc"],
                "total": total
            }))
            request.finish()
        deferToThread(search_db).addCallback(on_search_results)

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
        if 'q' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "query parameter missing"})

        keywords = cast_to_unicode_utf8(request.args['q'][0]).lower()
        # TODO: add XXX filtering for completion terms
        results = self.session.lm.mds.TorrentMetadata.get_auto_complete_terms(keywords, max_terms=5)
        return json.dumps({"completions": results})
