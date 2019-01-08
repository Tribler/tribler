from __future__ import absolute_import

import json
import logging
from binascii import unhexlify

from pony.orm import db_session
from twisted.web import resource, http
from twisted.web.server import NOT_DONE_YET

from Tribler.pyipv8.ipv8.database import database_blob


class BaseMetadataEndpoint(resource.Resource):

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        first = 1 if 'first' not in parameters else int(parameters['first'][0])
        last = 50 if 'last' not in parameters else int(parameters['last'][0])
        sort_by = None if 'sort_by' not in parameters else parameters['sort_by'][0]
        sort_asc = True if 'sort_asc' not in parameters else bool(int(parameters['sort_asc'][0]))
        query_filter = None if 'filter' not in parameters else parameters['filter'][0]

        if sort_by:
            sort_by = MetadataEndpoint.convert_sort_param_to_pony_col(sort_by)

        return first, last, sort_by, sort_asc, query_filter


class MetadataEndpoint(BaseMetadataEndpoint):

    def __init__(self, session):
        BaseMetadataEndpoint.__init__(self)

        child_handler_dict = {
            "channels": ChannelsEndpoint,
            "torrents": TorrentsEndpoint
        }

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls(session))

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
            u'size': "size",
            u'infohash': "infohash",
            u'date': "torrent_date",
            u'status': 'status'
        }

        if sort_param not in json2pony_columns:
            return None
        return json2pony_columns[sort_param]


class BaseChannelsEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        first, last, sort_by, sort_asc, query_filter = BaseMetadataEndpoint.sanitize_parameters(parameters)

        subscribed = False
        if 'subscribed' in parameters:
            subscribed = bool(int(parameters['subscribed'][0]))

        return first, last, sort_by, sort_asc, query_filter, subscribed


class ChannelsEndpoint(BaseChannelsEndpoint):

    def getChild(self, path, request):
        if path == "popular":
            return ChannelsPopularEndpoint(self.session)

        return SpecificChannelEndpoint(self.session, path)

    def render_GET(self, request):
        first, last, sort_by, sort_asc, query_filter, subscribed = ChannelsEndpoint.sanitize_parameters(request.args)
        channels, total = self.session.lm.mds.ChannelMetadata.get_channels(
            first, last, sort_by, sort_asc, query_filter, subscribed)

        channels = [channel.to_simple_dict() for channel in channels]

        return json.dumps({
            "channels": channels,
            "first": first,
            "last": last,
            "sort_by": sort_by,
            "sort_asc": int(sort_asc),
            "total": total
        })


class ChannelsPopularEndpoint(BaseChannelsEndpoint):

    def render_GET(self, request):
        limit_channels = 10

        if 'limit' in request.args and request.args['limit']:
            limit_channels = int(request.args['limit'][0])

            if limit_channels <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "the limit parameter must be a positive number"})

        popular_channels = self.session.lm.mds.ChannelMetadata.get_random_channels(limit=limit_channels)
        return json.dumps({"channels": [channel.to_simple_dict() for channel in popular_channels]})


class SpecificChannelEndpoint(BaseChannelsEndpoint):

    def __init__(self, session, channel_pk):
        BaseChannelsEndpoint.__init__(self, session)
        self.channel_pk = unhexlify(channel_pk)

        self.putChild("torrents", SpecificChannelTorrentsEndpoint(session, self.channel_pk))

    def render_POST(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        if 'subscribe' not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"success": False, "error": "subscribe parameter missing"})

        to_subscribe = bool(int(parameters['subscribe'][0]))
        with db_session:
            channel = self.session.lm.mds.ChannelMetadata.get(public_key=database_blob(self.channel_pk))
            if not channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": "this channel cannot be found"})

            channel.subscribed = to_subscribe

        return json.dumps({"success": True, "subscribed": to_subscribe})


class BaseTorrentsEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        first, last, sort_by, sort_asc, query_filter = BaseMetadataEndpoint.sanitize_parameters(parameters)

        channel = ''
        if 'channel' in parameters:
            channel = unhexlify(parameters['channel'][0])

        return first, last, sort_by, sort_asc, query_filter, channel


class SpecificChannelTorrentsEndpoint(BaseTorrentsEndpoint):

    def __init__(self, session, channel_pk):
        BaseTorrentsEndpoint.__init__(self, session)
        self.channel_pk = channel_pk

    @db_session
    def render_GET(self, request):
        first, last, sort_by, sort_asc, query_filter, _ = \
            SpecificChannelTorrentsEndpoint.sanitize_parameters(request.args)
        torrents, total = self.session.lm.mds.TorrentMetadata.get_torrents(
            first, last, sort_by, sort_asc, query_filter, self.channel_pk)

        torrents = [torrent.to_simple_dict() for torrent in torrents]

        return json.dumps({
            "torrents": torrents,
            "first": first,
            "last": last,
            "sort_by": sort_by,
            "sort_asc": int(sort_asc),
            "total": total
        })


class TorrentsEndpoint(BaseTorrentsEndpoint):

    def __init__(self, session):
        BaseTorrentsEndpoint.__init__(self, session)
        self.putChild("random", TorrentsRandomEndpoint(session))

    def getChild(self, path, request):
        return SpecificTorrentEndpoint(self.session, path)


class SpecificTorrentEndpoint(resource.Resource):
    """
    This class handles requests for a specific torrent.
    """

    def __init__(self, session, infohash):
        resource.Resource.__init__(self)
        self.session = session
        self.infohash = infohash

        self.putChild("health", TorrentHealthEndpoint(self.session, self.infohash))


class TorrentsRandomEndpoint(BaseTorrentsEndpoint):

    @db_session
    def render_GET(self, request):
        limit_torrents = 10

        if 'limit' in request.args and request.args['limit']:
            limit_torrents = int(request.args['limit'][0])

            if limit_torrents <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "the limit parameter must be a positive number"})

        random_torrents = self.session.lm.mds.TorrentMetadata.get_random_torrents(limit=limit_torrents)
        return json.dumps({"torrents": [torrent.to_simple_dict() for torrent in random_torrents]})


class TorrentHealthEndpoint(resource.Resource):
    """
    This class is responsible for endpoints regarding the health of a torrent.
    """

    def __init__(self, session, infohash):
        resource.Resource.__init__(self)
        self.session = session
        self.infohash = unhexlify(infohash)
        self._logger = logging.getLogger(self.__class__.__name__)

    def finish_request(self, request):
        try:
            request.finish()
        except RuntimeError:
            self._logger.warning("Writing response failed, probably the client closed the connection already.")

    def render_GET(self, request):
        """
        .. http:get:: /torrents/(string: torrent infohash)/health

        Fetch the swarm health of a specific torrent. You can optionally specify the timeout to be used in the
        connections to the trackers. This is by default 20 seconds.
        By default, we will not check the health of a torrent again if it was recently checked. You can force a health
        recheck by passing the refresh parameter.

            **Example request**:

            .. sourcecode:: none

                curl http://localhost:8085/torrents/97d2d8f5d37e56cfaeaae151d55f05b077074779/health?timeout=15&refresh=1

            **Example response**:

            .. sourcecode:: javascript

                {
                    "http://mytracker.com:80/announce": [{
                        "seeders": 43,
                        "leechers": 20,
                        "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779"
                    }],
                    "http://nonexistingtracker.com:80/announce": {
                        "error": "timeout"
                    }
                }

            :statuscode 404: if the torrent is not found in the database
        """
        timeout = 20
        if 'timeout' in request.args:
            timeout = int(request.args['timeout'][0])

        refresh = False
        if 'refresh' in request.args and request.args['refresh'] and request.args['refresh'][0] == "1":
            refresh = True

        def on_health_result(result):
            request.write(json.dumps({'health': result}))
            self.finish_request(request)

        def on_request_error(failure):
            if not request.finished:
                request.setResponseCode(http.BAD_REQUEST)
                request.write(json.dumps({"error": failure.getErrorMessage()}))
            # If the above request.write failed, the request will have already been finished
            if not request.finished:
                self.finish_request(request)

        with db_session:
            md_list = list(self.session.lm.mds.TorrentMetadata.select(lambda g:
                                                                      g.infohash == database_blob(self.infohash)))
            if not md_list:
                request.setResponseCode(http.NOT_FOUND)
                request.write(json.dumps({"error": "torrent not found in database"}))

        self.session.check_torrent_health(self.infohash, timeout=timeout, scrape_now=refresh) \
            .addCallback(on_health_result).addErrback(on_request_error)

        return NOT_DONE_YET
