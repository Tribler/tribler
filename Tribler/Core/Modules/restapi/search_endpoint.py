from __future__ import absolute_import

import logging
from binascii import unhexlify

from pony.orm import db_session

from twisted.web import http, resource

import Tribler.Core.Utilities.json_util as json
from Tribler.util import cast_to_unicode_utf8


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

    @staticmethod
    def convert_sort_param_to_pony_col(sort_param):
        """
        Convert an incoming sort parameter to a pony column in the database.
        :return a string with the right column. None if there exists no value for the given key.
        """
        json2pony_columns = {
            u'category': "tags",
            u'id': "rowid",
            u'name': "title",
            u'health': "health",
        }

        if sort_param not in json2pony_columns:
            return None
        return json2pony_columns[sort_param]

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters and check whether they exist
        """
        first = 1 if 'first' not in parameters else int(parameters['first'][0])
        last = 50 if 'last' not in parameters else int(parameters['last'][0])
        sort_by = None if 'sort_by' not in parameters else parameters['sort_by'][0]
        sort_asc = True if 'sort_asc' not in parameters else bool(int(parameters['sort_asc'][0]))
        data_type = None if 'type' not in parameters else parameters['type'][0]

        if sort_by:
            sort_by = SearchEndpoint.convert_sort_param_to_pony_col(sort_by)

        return first, last, sort_by, sort_asc, data_type

    @db_session
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
        subscribed option limits query to channels you are subscribed for

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
        if 'q' not in request.args or not request.args['q'] or not request.args['q'][0]:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "q parameter missing"})

        first, last, sort_by, sort_asc, data_type = SearchEndpoint.sanitize_parameters(request.args)
        query = request.args['q'][0]

        torrent_results, total_torrents = self.session.lm.mds.TorrentMetadata.get_torrents(
            first, last, sort_by, sort_asc, query_filter=query)
        torrents_json = []
        for torrent in torrent_results:
            torrent_json = torrent.to_simple_dict()
            torrent_json['type'] = 'torrent'
            torrents_json.append(torrent_json)

        channel_results, total_channels = self.session.lm.mds.ChannelMetadata.get_channels(
            first, last, sort_by, sort_asc, query_filter=query)
        channels_json = []
        for channel in channel_results:
            channel_json = channel.to_simple_dict()
            channel_json['type'] = 'channel'
            channels_json.append(channel_json)

        if not data_type:
            search_results = channels_json + torrents_json
        elif data_type == 'channel':
            search_results = channels_json
        elif data_type == 'torrent':
            search_results = torrents_json
        else:
            search_results = []

        return json.dumps({
            "results": search_results[first - 1:last],
            "first": first,
            "last": last,
            "sort_by": sort_by,
            "sort_asc": sort_asc,
            "total": total_torrents + total_channels
        })


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
        results = self.session.lm.mds.TorrentMetadata.get_auto_complete_terms(keywords, max_terms=5)
        return json.dumps({"completions": results})
