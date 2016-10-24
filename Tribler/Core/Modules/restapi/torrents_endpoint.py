import json

from twisted.web import http, resource

from Tribler.Core.Modules.restapi.util import convert_db_torrent_to_json
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_CHANNELCAST


class TorrentsEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"random": TorrentsRandomEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session))


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
            if (self.session.tribler_config.get_family_filter_enabled() and
                    self.session.lm.category.xxx_filter.isXXX(torrent_json['category'])) \
                    or torrent_json['name'] is None:
                continue

            results_json.append(torrent_json)

        return json.dumps({"torrents": results_json})
