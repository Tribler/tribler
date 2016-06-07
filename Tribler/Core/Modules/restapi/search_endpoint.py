import json
import logging

from twisted.web import http, resource
from Tribler.Core.Utilities.search_utils import split_into_keywords
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_TORRENTS, SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, \
    SIGNAL_CHANNEL


class SearchEndpoint(resource.Resource):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.

    A GET request to this endpoint will create a search. Results are returned over the events endpoint, one by one.
    First, the results available in the local database will be pushed. After that, incoming Dispersy results are pushed.
    The query to this endpoint is passed using the url, i.e. /search?q=pioneer

    Example response over the events endpoint:
    {
        "type": "search_result_channel",
        "event": {
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
    }
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.events_endpoint = None
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)
        self._logger = logging.getLogger(self.__class__.__name__)

    def render_GET(self, request):
        """
        This method first fires a search query in the SearchCommunity/AllChannelCommunity to search for torrents and
        channels. Next, the results in the local database are queried and returned over the events endpoint.
        """
        request.setHeader('Content-Type', 'text/json')
        if 'q' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "query parameter missing"})

        # Notify the events endpoint that we are starting a new search query
        self.events_endpoint.start_new_query()

        # We first search the local database for torrents and channels
        keywords = split_into_keywords(unicode(request.args['q'][0]))
        results_local_channels = self.channel_db_handler.searchChannels(keywords)
        results_dict = {"keywords": keywords, "result_list": results_local_channels}
        self.session.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

        torrent_db_columns = ['T.torrent_id', 'infohash', 'T.name', 'length', 'category',
                              'num_seeders', 'num_leechers', 'last_tracker_check']
        results_local_torrents = self.torrent_db_handler.searchNames(keywords, keys=torrent_db_columns, doSort=False)
        results_dict = {"keywords": keywords, "result_list": results_local_torrents}
        self.session.notifier.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

        # Create remote searches
        try:
            self.session.search_remote_torrents(keywords)
            self.session.search_remote_channels(keywords)
        except OperationNotEnabledByConfigurationException as exc:
            self._logger.error(exc)

        return json.dumps({"queried": True})
