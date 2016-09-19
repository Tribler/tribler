import json
import logging

from twisted.web import http, resource
from Tribler.Core.Utilities.search_utils import split_into_keywords
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_TORRENTS, SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, \
    SIGNAL_CHANNEL


class SearchEndpoint(resource.Resource):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database. It also
    fires a remote search in the Dispersy communities.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.events_endpoint = None
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)
        self._logger = logging.getLogger(self.__class__.__name__)

        self.putChild("completions", SearchCompletionsEndpoint(session))

    def render_GET(self, request):
        """
        .. http:get:: /search?q=(string:query)

        A GET request to this endpoint will create a search. Results are returned over the events endpoint, one by one.
        First, the results available in the local database will be pushed. After that, incoming Dispersy results are
        pushed. The query to this endpoint is passed using the url, i.e. /search?q=pioneer.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/search?q=tribler

            **Example response**:

            .. sourcecode:: javascript

                {
                    "type": "search_result_channel",
                    "query": "test",
                    "result": {
                        "id": 3,
                        "dispersy_cid": "da69aaad39ccf468aba2ab9177d5f8d8160135e6",
                        "name": "My fancy channel",
                        "description": "A description of this fancy channel",
                        "subscribed": True,
                        "votes": 23,
                        "torrents": 3,
                        "spam": 5,
                        "modified": 14598395,
                    }
                }
        """
        if 'q' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "query parameter missing"})

        # Notify the events endpoint that we are starting a new search query
        self.events_endpoint.start_new_query()

        # We first search the local database for torrents and channels
        query = unicode(request.args['q'][0])
        keywords = split_into_keywords(query)
        results_local_channels = self.channel_db_handler.search_in_local_channels_db(query)
        results_dict = {"keywords": keywords, "result_list": results_local_channels}
        self.session.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

        torrent_db_columns = ['T.torrent_id', 'infohash', 'T.name', 'length', 'category',
                              'num_seeders', 'num_leechers', 'last_tracker_check']
        results_local_torrents = self.torrent_db_handler.search_in_local_torrents_db(query, keys=torrent_db_columns)
        results_dict = {"keywords": keywords, "result_list": results_local_torrents}
        self.session.notifier.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

        # Create remote searches
        try:
            self.session.search_remote_torrents(keywords)
            self.session.search_remote_channels(keywords)
        except OperationNotEnabledByConfigurationException as exc:
            self._logger.error(exc)

        return json.dumps({"queried": True})


class SearchCompletionsEndpoint(resource.Resource):
    """
    This class is responsible for managing requests regarding the search completions terms of a query.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)

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

        keywords = unicode(request.args['q'][0]).lower()
        results = self.torrent_db_handler.getAutoCompleteTerms(keywords, max_terms=5)
        return json.dumps({"completions": results})
