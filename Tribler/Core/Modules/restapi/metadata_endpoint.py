from __future__ import absolute_import

import logging
from binascii import unhexlify

from ipv8.database import database_blob

from pony.orm import db_session

from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.metadata_endpoint_base import MetadataEndpointBase
from Tribler.Core.Utilities.unicode import hexlify, recursive_unicode


class UpdateEntryMixin(object):
    @db_session
    def update_entry(self, public_key, id_, update_dict):
        entry = self.session.lm.mds.ChannelNode.get(public_key=public_key, id_=id_)
        if not entry:
            return http.NOT_FOUND, {"error": "Object with the specified pk+id could not be found."}

        signed_parameters_to_change = set(entry.payload_arguments).intersection(set(update_dict.keys()))
        if signed_parameters_to_change:
            if 'status' in update_dict:
                return http.BAD_REQUEST, {"error": "Cannot set status manually when changing signed attributes."}
            if not entry.is_personal:
                return (
                    http.BAD_REQUEST,
                    {"error": "Changing signed parameters in non-personal entries is not supported."},
                )

        return None, entry.update_properties(update_dict).to_simple_dict()


class MetadataEndpoint(resource.Resource, UpdateEntryMixin):
    """
    This is the top-level endpoint class that serves other endpoints.

    # /metadata
    #          /channels
    #          /torrents
    #          /<public_key>
    """

    def __init__(self, session):
        self.session = session
        resource.Resource.__init__(self)

        child_handler_dict = {b"torrents": TorrentsEndpoint}

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls(self.session))

    def getChild(self, path, request):
        return MetadataPublicKeyEndpoint(self.session, path)

    def render_PATCH(self, request):
        try:
            request_parsed = recursive_unicode(json.twisted_loads(request.content.read()))
        except ValueError:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "Bad JSON"})
        results_list = []
        for entry in request_parsed:
            public_key = database_blob(unhexlify(entry.pop("public_key")))
            id_ = entry.pop("id")
            error, result = self.update_entry(public_key, id_, entry)
            # TODO: handle the results for a list that contains some errors in a smarter way
            if error:
                request.setResponseCode(error)
                return json.twisted_dumps(result)
            results_list.append(result)
        return json.twisted_dumps(results_list)

    @db_session
    def render_DELETE(self, request):
        request_parsed = recursive_unicode(json.twisted_loads(request.content.read()))
        results_list = []
        for entry in request_parsed:
            public_key = database_blob(unhexlify(entry.pop("public_key")))
            id_ = entry.pop("id")
            entry = self.session.lm.mds.ChannelNode.get(public_key=public_key, id_=id_)
            if not entry:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "Entry %i not found" % id_})
            entry.delete()
            result = {"public_key": hexlify(public_key), "id": id_, "state": "Deleted"}
            results_list.append(result)
        return json.twisted_dumps(results_list)


class MetadataPublicKeyEndpoint(resource.Resource):
    """
    Intermediate endpoint for parsing public_key part of the request.

    # /<public_key>
    #              /<id_>
    """

    def getChild(self, path, request):
        return SpecificMetadataEndpoint(self.session, self.channel_pk, path)

    def __init__(self, session, path):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_pk = unhexlify(path)


class SpecificMetadataEndpoint(resource.Resource, UpdateEntryMixin):
    """
    The endpoint to modify and get individual metadata entries.

    # /<id_>
    """

    def __init__(self, session, public_key, path):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.public_key = public_key
        self.id_ = int(path)
        resource.Resource.__init__(self)

    def render_PATCH(self, request):
        # TODO: unify checks for parts of the path, i.e. proper hex for public key, etc.
        try:
            parameters = recursive_unicode(json.twisted_loads(request.content.read()))
        except ValueError:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "bad JSON input data"})

        error, result = self.update_entry(self.public_key, self.id_, parameters)
        if error:
            request.setResponseCode(error)
        return json.twisted_dumps(result)

    def render_GET(self, request):
        with db_session:
            entry = self.session.lm.mds.ChannelNode.get(public_key=database_blob(self.public_key), id_=self.id_)

            if entry:
                # TODO: handle costly attributes in a more graceful and generic way for all types of metadata
                entry_dict = entry.to_simple_dict(
                    include_trackers=isinstance(entry, self.session.lm.mds.TorrentMetadata)
                )
            else:
                request.setResponseCode(http.NOT_FOUND)
                return json.twisted_dumps({"error": "entry not found in database"})

        return json.twisted_dumps(entry_dict)


class TorrentsEndpoint(MetadataEndpointBase):
    """
    The endpoint that provides and interface to torrent objects in the metadata database.

    # /torrents
    #          /random
    """

    def __init__(self, session):
        MetadataEndpointBase.__init__(self, session)
        self.putChild(b"random", TorrentsRandomEndpoint(session))

    def getChild(self, path, request):
        return SpecificTorrentEndpoint(self.session, path)


class SpecificTorrentEndpoint(resource.Resource):
    """
    This class handles requests for a specific torrent, based on infohash.
    """

    def __init__(self, session, infohash):
        resource.Resource.__init__(self)
        self.session = session
        self.infohash = unhexlify(infohash)

        self.putChild(b"health", TorrentHealthEndpoint(self.session, self.infohash))


class TorrentsRandomEndpoint(MetadataEndpointBase):
    """
    A specialized endpoint to get a random torrent from the metadata database.
    """

    def render_GET(self, request):
        limit_torrents = 10

        args = recursive_unicode(request.args)
        if 'limit' in args and args['limit']:
            limit_torrents = int(args['limit'][0])

            if limit_torrents <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "the limit parameter must be a positive number"})

        with db_session:
            random_torrents = self.session.lm.mds.TorrentMetadata.get_random_torrents(limit=limit_torrents)
            torrents = [torrent.to_simple_dict() for torrent in random_torrents]
        return json.twisted_dumps({"torrents": torrents})


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
        args = recursive_unicode(request.args)
        timeout = 20
        if 'timeout' in args:
            timeout = int(args['timeout'][0])

        refresh = False
        if 'refresh' in args and args['refresh'] and args['refresh'][0] == "1":
            refresh = True

        nowait = False
        if 'nowait' in args and args['nowait'] and args['nowait'][0] == "1":
            nowait = True

        def on_health_result(result):
            request.write(json.twisted_dumps({'health': result}))
            self.finish_request(request)

        def on_request_error(failure):
            if not request.finished:
                request.setResponseCode(http.BAD_REQUEST)
                request.write(json.twisted_dumps({"error": failure.getErrorMessage()}))
            # If the above request.write failed, the request will have already been finished
            if not request.finished:
                self.finish_request(request)

        result_deferred = self.session.check_torrent_health(self.infohash, timeout=timeout, scrape_now=refresh)
        # return immediately. Used by GUI to schedule health updates through the EventsEndpoint
        if nowait:
            return json.twisted_dumps({'checking': '1'})
        result_deferred.addCallback(on_health_result).addErrback(on_request_error)

        return NOT_DONE_YET
