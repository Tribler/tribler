import logging

from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

from Tribler.Core.Modules.restapi.util import convert_db_torrent_to_json
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_CHANNELCAST
import Tribler.Core.Utilities.json_util as json


class TorrentsEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def getChild(self, path, request):
        if path == "random":
            return TorrentsRandomEndpoint(self.session)
        return SpecificTorrentEndpoint(self.session, path)


class TorrentsRandomEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.torrents_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)

    def render_GET(self, request):
        """
        .. http:get:: /torrents/random?limit=(int: max nr of torrents)

        A GET request to this endpoint returns random (channel) torrents.
        You can optionally specify a limit parameter to limit the maximum number of results. By default, this is 10.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/torrents/random?limit=1

            **Example response**:

            .. sourcecode:: javascript

                {
                    "torrents": [{
                        "id": 4,
                        "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779",
                        "name": "Ubuntu-16.04-desktop-amd64",
                        "size": 8592385,
                        "category": "other",
                        "num_seeders": 42,
                        "num_leechers": 184,
                        "last_tracker_check": 1463176959
                    }]
                }
        """
        limit_torrents = 10

        if 'limit' in request.args and len(request.args['limit']) > 0:
            limit_torrents = int(request.args['limit'][0])

            if limit_torrents <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "the limit parameter must be a positive number"})

        torrent_db_columns = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length', 'Torrent.category',
                              'num_seeders', 'num_leechers', 'last_tracker_check', 'ChannelTorrents.inserted']

        popular_torrents = self.channel_db_handler.get_random_channel_torrents(torrent_db_columns, limit=limit_torrents)

        results_json = []
        for popular_torrent in popular_torrents:
            torrent_json = convert_db_torrent_to_json(popular_torrent)
            if (self.session.config.get_family_filter_enabled() and
                    self.session.lm.category.xxx_filter.isXXX(torrent_json['category'])) \
                    or torrent_json['name'] is None:
                continue

            results_json.append(torrent_json)

        return json.dumps({"torrents": results_json})


class SpecificTorrentEndpoint(resource.Resource):
    """
    This class handles requests for a specific torrent.
    """

    def __init__(self, session, infohash):
        resource.Resource.__init__(self)
        self.session = session
        self.infohash = infohash

        self.putChild("health", TorrentHealthEndpoint(self.session, self.infohash))
        self.putChild("trackers", TorrentTrackersEndpoint(self.session, self.infohash))


class TorrentTrackersEndpoint(resource.Resource):
    """
    This class is responsible for fetching all trackers of a specific torrent.
    """

    def __init__(self, session, infohash):
        resource.Resource.__init__(self)
        self.session = session
        self.infohash = infohash
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)

    def render_GET(self, request):
        """
        .. http:get:: /torrents/(string: torrent infohash)/tracker

        Fetch all trackers of a specific torrent.

            **Example request**:

            .. sourcecode:: none

                curl http://localhost:8085/torrents/97d2d8f5d37e56cfaeaae151d55f05b077074779/trackers

            **Example response**:

            .. sourcecode:: javascript

                {
                    "trackers": [
                        "http://mytracker.com:80/announce",
                        "udp://fancytracker.org:1337/announce"
                    ]
                }

            :statuscode 404: if the torrent is not found in the database
        """
        torrent_info = self.torrent_db.getTorrent(self.infohash.decode('hex'), ['C.torrent_id', 'num_seeders'])

        if torrent_info is None:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "torrent not found in database"})

        trackers = self.torrent_db.getTrackerListByInfohash(self.infohash.decode('hex'))
        return json.dumps({"trackers": trackers})


class TorrentHealthEndpoint(resource.Resource):
    """
    This class is responsible for endpoints regarding the health of a torrent.
    """

    def __init__(self, session, infohash):
        resource.Resource.__init__(self)
        self.session = session
        self.infohash = infohash
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
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
        if 'refresh' in request.args and len(request.args['refresh']) > 0 and request.args['refresh'][0] == "1":
            refresh = True

        torrent_db_columns = ['C.torrent_id', 'num_seeders', 'num_leechers', 'next_tracker_check']
        torrent_info = self.torrent_db.getTorrent(self.infohash.decode('hex'), torrent_db_columns)

        if torrent_info is None:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "torrent not found in database"})

        def on_health_result(result):
            request.write(json.dumps({'health': result}))
            self.finish_request(request)

        def on_request_error(failure):
            request.setResponseCode(http.BAD_REQUEST)
            request.write(json.dumps({"error": failure.getErrorMessage()}))
            self.finish_request(request)

        self.session.check_torrent_health(self.infohash.decode('hex'), timeout=timeout, scrape_now=refresh)\
            .addCallback(on_health_result).addErrback(on_request_error)

        return NOT_DONE_YET
