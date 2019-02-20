from __future__ import absolute_import

import json
import logging
from binascii import unhexlify

from pony.orm import db_session
from twisted.web import resource, http
from twisted.web.server import NOT_DONE_YET

from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.util import cast_to_unicode_utf8


class BaseMetadataEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        sanitized = {
            "first": 1 if 'first' not in parameters else int(parameters['first'][0]),
            "last": 50 if 'last' not in parameters else int(parameters['last'][0]),
            "sort_by": None if 'sort_by' not in parameters else BaseMetadataEndpoint.convert_sort_param_to_pony_col(
                parameters['sort_by'][0]),
            "sort_asc": True if 'sort_asc' not in parameters else bool(int(parameters['sort_asc'][0])),
            "query_filter": None if 'filter' not in parameters else cast_to_unicode_utf8(parameters['filter'][0]),
            "hide_xxx": False if 'hide_xxx' not in parameters else bool(int(parameters['hide_xxx'][0]) > 0)}

        return sanitized

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
            u'status': 'status',
            u'torrents': 'num_entries',
            u'health': 'HEALTH'
        }

        return json2pony_columns[sort_param] if sort_param in json2pony_columns else None


class MetadataEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {
            "channels": ChannelsEndpoint,
            "torrents": TorrentsEndpoint
        }

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls(session))


class BaseChannelsEndpoint(BaseMetadataEndpoint):
    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        sanitized = BaseMetadataEndpoint.sanitize_parameters(parameters)

        if 'subscribed' in parameters:
            sanitized['subscribed'] = bool(int(parameters['subscribed'][0]))

        return sanitized


class ChannelsEndpoint(BaseChannelsEndpoint):

    def getChild(self, path, request):
        if path == "popular":
            return ChannelsPopularEndpoint(self.session)

        return SpecificChannelEndpoint(self.session, path)

    def render_GET(self, request):
        sanitized = ChannelsEndpoint.sanitize_parameters(request.args)
        with db_session:
            channels, total = self.session.lm.mds.ChannelMetadata.get_entries(**sanitized)
            channels_list = [channel.to_simple_dict() for channel in channels]

        return json.dumps({
            "channels": channels_list,
            "first": sanitized["first"],
            "last": sanitized["last"],
            "sort_by": sanitized["sort_by"],
            "sort_asc": int(sanitized["sort_asc"]),
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
            channel.local_version = 0

        return json.dumps({"success": True, "subscribed": to_subscribe})


class SpecificChannelTorrentsEndpoint(BaseMetadataEndpoint):

    def __init__(self, session, channel_pk):
        BaseMetadataEndpoint.__init__(self, session)
        self.channel_pk = channel_pk

    def render_GET(self, request):
        sanitized = SpecificChannelTorrentsEndpoint.sanitize_parameters(request.args)
        with db_session:
            torrents, total = self.session.lm.mds.TorrentMetadata.get_entries(channel_pk=self.channel_pk, **sanitized)
            torrents_list = [torrent.to_simple_dict() for torrent in torrents]

        return json.dumps({
            "torrents": torrents_list,
            "first": sanitized['first'],
            "last": sanitized['last'],
            "sort_by": sanitized['sort_by'],
            "sort_asc": int(sanitized['sort_asc']),
            "total": total
        })


class TorrentsEndpoint(BaseMetadataEndpoint):

    def __init__(self, session):
        BaseMetadataEndpoint.__init__(self, session)
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
        self.infohash = unhexlify(infohash)

        self.putChild("health", TorrentHealthEndpoint(self.session, self.infohash))

    def render_GET(self, request):
        with db_session:
            md = self.session.lm.mds.TorrentMetadata.select(lambda g: g.infohash == database_blob(self.infohash))[:1]
            torrent_dict = md[0].to_simple_dict(include_trackers=True) if md else None

        if not md:
            request.setResponseCode(http.NOT_FOUND)
            request.write(json.dumps({"error": "torrent not found in database"}))
            return

        return json.dumps({"torrent": torrent_dict})


class TorrentsRandomEndpoint(BaseMetadataEndpoint):

    def render_GET(self, request):
        limit_torrents = 10

        if 'limit' in request.args and request.args['limit']:
            limit_torrents = int(request.args['limit'][0])

            if limit_torrents <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "the limit parameter must be a positive number"})

        with db_session:
            random_torrents = self.session.lm.mds.TorrentMetadata.get_random_torrents(limit=limit_torrents)
            torrents = [torrent.to_simple_dict() for torrent in random_torrents]
        return json.dumps({"torrents": torrents})


class TorrentHealthEndpoint(resource.Resource):
    """
    This class is responsible for endpoints regarding the health of a torrent.
    """

    def __init__(self, session, infohash):
        resource.Resource.__init__(self)
        self.session = session
        self.infohash = infohash
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

                curl http://localhost:8085/metadata/torrents/97d2d8f5d37e56cfaeaae151d55f05b077074779/health
                     ?timeout=15&refresh=1

            **Example response**:

            .. sourcecode:: javascript

                {
                    "health": {
                        "http://mytracker.com:80/announce": {
                            "seeders": 43,
                            "leechers": 20,
                            "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779"
                        },
                            "http://nonexistingtracker.com:80/announce": {
                                "error": "timeout"
                        }
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

        nowait = False
        if 'nowait' in request.args and request.args['nowait'] and request.args['nowait'][0] == "1":
            nowait = True

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

        result_deferred = self.session.check_torrent_health(self.infohash, timeout=timeout, scrape_now=refresh)
        # return immediately. Used by GUI to schedule health updates through the EventsEndpoint
        if nowait:
            return json.dumps({'checking': '1'})
        result_deferred.addCallback(on_health_result).addErrback(on_request_error)

        return NOT_DONE_YET
