import logging

from pony.orm import db_session
from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.util import convert_db_torrent_to_json
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_CHANNELCAST


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
                    or torrent_json['name'] is None \
                    or torrent_json['infohash'] in self.session.lm.downloads:
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
        self.torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)

        self.putChild("health", TorrentHealthEndpoint(self.session, self.infohash))
        self.putChild("trackers", TorrentTrackersEndpoint(self.session, self.infohash))

    def render_GET(self, request):
        """
        .. http:get:: /torrents/(string: torrent infohash)

        Get information of a torrent with a given infohash from a given channel.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/torrents/97d2d8f5d37e56cfaeaae151d55f05b077074779

            **Example response**:

            .. sourcecode:: javascript

                {
                    "id": 4,
                    "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779",
                    "name": "Ubuntu-16.04-desktop-amd64",
                    "size": 8592385,
                    "category": "other",
                    "num_seeders": 42,
                    "num_leechers": 184,
                    "last_tracker_check": 1463176959,
                    "files": [{"path": "test.txt", "length": 1234}, ...],
                    "trackers": ["http://tracker.org:8080", ...]
                }

            :statuscode 404: if the torrent is not found in the specified channel
        """
        torrent_db_columns = ['C.torrent_id', 'infohash', 'name', 'length', 'category',
                              'num_seeders', 'num_leechers', 'last_tracker_check']
        torrent_info = self.torrent_db_handler.getTorrent(self.infohash.decode('hex'), keys=torrent_db_columns)
        if torrent_info is None:
            # Maybe this is a chant torrent?
            infohash = self.infohash.decode('hex')
            with db_session:
                md_list = list(self.session.lm.mds.TorrentMetadata.select(lambda g: g.infohash == buffer(infohash)))
                if md_list:
                    torrent_md = md_list[0]  # Any MD containing this infohash is fine
                    # FIXME: replace these placeholder values when Dispersy is gone
                    torrent_info = {
                        "C.torrent_id": "",
                        "name": torrent_md.title,
                        "length": torrent_md.size,
                        "category": torrent_md.tags.split(",")[0] or '',
                        "last_tracker_check": 0,
                        "num_seeders": 0,
                        "num_leechers": 0
                    }

        if torrent_info is None:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "Unknown torrent"})

        torrent_files = []
        for path, length in self.torrent_db_handler.getTorrentFiles(torrent_info['C.torrent_id']):
            torrent_files.append({"path": path, "size": length})

        torrent_json = {
            "id": torrent_info['C.torrent_id'],
            "infohash": self.infohash,
            "name": torrent_info['name'],
            "size": torrent_info['length'],
            "category": torrent_info['category'],
            "num_seeders": torrent_info['num_seeders'] if torrent_info['num_seeders'] else 0,
            "num_leechers": torrent_info['num_leechers'] if torrent_info['num_leechers'] else 0,
            "last_tracker_check": torrent_info['last_tracker_check'],
            "files": torrent_files,
            "trackers": self.torrent_db_handler.getTrackerListByTorrentID(torrent_info['C.torrent_id'])
        }

        return json.dumps(torrent_json)


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

        def make_torrent_health_request():
            self.session.check_torrent_health(self.infohash.decode('hex'), timeout=timeout, scrape_now=refresh) \
                .addCallback(on_health_result).addErrback(on_request_error)

        magnet = None
        if torrent_info is None:
            # Maybe this is a chant torrent?
            infohash = self.infohash.decode('hex')
            with db_session:
                md_list = list(self.session.lm.mds.TorrentMetadata.select(lambda g: g.infohash == buffer(infohash)))
                if md_list:
                    torrent_md = md_list[0]  # Any MD containing this infohash is fine
                    magnet = torrent_md.get_magnet()
                    timeout = 50

        def _add_torrent_and_check(metainfo):
            tdef = TorrentDef.load_from_dict(metainfo)
            assert (tdef.infohash == infohash), "DHT infohash does not match locally generated one"
            self._logger.info("Chant-managed torrent fetched from DHT. Adding it to local cache, %s", self.infohash)
            self.session.lm.torrent_db.addExternalTorrent(tdef)
            self.session.lm.torrent_db._db.commit_now()
            make_torrent_health_request()

        if magnet:
            # Try to get the torrent from DHT and add it to the local cache
            self._logger.info("Chant-managed torrent not in cache. Going to fetch it from DHT, %s", self.infohash)
            self.session.lm.ltmgr.get_metainfo(magnet, callback=_add_torrent_and_check,
                                               timeout=30, timeout_callback=on_request_error, notify=False)
        elif torrent_info is None:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "torrent not found in database"})
        else:
            make_torrent_health_request()

        return NOT_DONE_YET
