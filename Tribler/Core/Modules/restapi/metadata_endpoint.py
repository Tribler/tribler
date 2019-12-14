from asyncio import ensure_future
from binascii import unhexlify

from aiohttp import ContentTypeError, web

from ipv8.database import database_blob

from pony.orm import db_session

from Tribler.Core.Modules.restapi.metadata_endpoint_base import MetadataEndpointBase
from Tribler.Core.Modules.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, RESTResponse
from Tribler.Core.Utilities.unicode import hexlify


class UpdateEntryMixin(object):
    @db_session
    def update_entry(self, public_key, id_, update_dict):
        entry = self.session.mds.ChannelNode.get(public_key=public_key, id_=id_)
        if not entry:
            return HTTP_NOT_FOUND, {"error": "Object with the specified pk+id could not be found."}

        signed_parameters_to_change = set(entry.payload_arguments).intersection(set(update_dict.keys()))
        if signed_parameters_to_change:
            if 'status' in update_dict:
                return HTTP_BAD_REQUEST, {"error": "Cannot set status manually when changing signed attributes."}
            if not entry.is_personal:
                return (
                    HTTP_BAD_REQUEST,
                    {"error": "Changing signed parameters in non-personal entries is not supported."},
                )

        return None, entry.update_properties(update_dict).to_simple_dict()


class MetadataEndpoint(MetadataEndpointBase, UpdateEntryMixin):
    """
    This is the top-level endpoint class that serves other endpoints.

    # /metadata
    #          /channels
    #          /torrents
    #          /<public_key>
    """

    def setup_routes(self):
        self.app.add_routes(
            [web.patch('', self.update_channel_entries),
             web.delete('', self.delete_channel_entries),
             web.get('/torrents/random', self.get_random_torrents),
             web.get('/torrents/{infohash}/health', self.get_torrent_health),
             web.patch(r'/{public_key:\w*}/{id:\w*}', self.update_channel_entry),
             web.get(r'/{public_key:\w*}/{id:\w*}', self.get_channel_entries)])

    async def update_channel_entries(self, request):
        try:
            request_parsed = await request.json()
        except (ContentTypeError, ValueError):
            return RESTResponse({"error": "Bad JSON"}, status=HTTP_BAD_REQUEST)
        results_list = []
        for entry in request_parsed:
            public_key = database_blob(unhexlify(entry.pop("public_key")))
            id_ = entry.pop("id")
            error, result = self.update_entry(public_key, id_, entry)
            # TODO: handle the results for a list that contains some errors in a smarter way
            if error:
                return RESTResponse(result, status=error)
            results_list.append(result)
        return RESTResponse(results_list)

    async def delete_channel_entries(self, request):
        with db_session:
            request_parsed = await request.json()
            results_list = []
            for entry in request_parsed:
                public_key = database_blob(unhexlify(entry.pop("public_key")))
                id_ = entry.pop("id")
                entry = self.session.mds.ChannelNode.get(public_key=public_key, id_=id_)
                if not entry:
                    return RESTResponse({"error": "Entry %i not found" % id_}, status=HTTP_BAD_REQUEST)
                entry.delete()
                result = {"public_key": hexlify(public_key), "id": id_, "state": "Deleted"}
                results_list.append(result)
            return RESTResponse(results_list)

    async def update_channel_entry(self, request):
        # TODO: unify checks for parts of the path, i.e. proper hex for public key, etc.
        try:
            parameters = await request.json()
        except (ContentTypeError, ValueError):
            return RESTResponse({"error": "Bad JSON input data"}, status=HTTP_BAD_REQUEST)

        public_key = unhexlify(request.match_info['public_key'])
        id_ = request.match_info['id']
        error, result = self.update_entry(public_key, id_, parameters)
        return RESTResponse(result, status=error or 200)

    async def get_channel_entries(self, request):
        public_key = unhexlify(request.match_info['public_key'])
        id_ = request.match_info['id']
        with db_session:
            entry = self.session.mds.ChannelNode.get(public_key=database_blob(public_key), id_=id_)

            if entry:
                # TODO: handle costly attributes in a more graceful and generic way for all types of metadata
                entry_dict = entry.to_simple_dict(
                    include_trackers=isinstance(entry, self.session.mds.TorrentMetadata)
                )
            else:
                return RESTResponse({"error": "entry not found in database"}, status=HTTP_NOT_FOUND)

        return RESTResponse(entry_dict)

    async def get_random_torrents(self, request):
        limit_torrents = int(request.query.get('limit', 10))
        if limit_torrents <= 0:
            return RESTResponse({"error": "the limit parameter must be a positive number"},
                                status=HTTP_BAD_REQUEST)

        with db_session:
            random_torrents = self.session.mds.TorrentMetadata.get_random_torrents(limit=limit_torrents)
            torrents = [torrent.to_simple_dict() for torrent in random_torrents]
        return RESTResponse({"torrents": torrents})

    async def get_torrent_health(self, request):
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
        timeout = request.query.get('timeout', 20)
        refresh = request.query.get('refresh', '0') == '1'
        nowait = request.query.get('nowait', '0') == '1'

        infohash = unhexlify(request.match_info['infohash'])
        result_future = self.session.torrent_checker.check_torrent_health(infohash, timeout=timeout, scrape_now=refresh)
        # Return immediately. Used by GUI to schedule health updates through the EventsEndpoint
        if nowait:
            ensure_future(result_future)
            return RESTResponse({'checking': '1'})

        # Errors will be handled by error_middleware
        result = await result_future
        return RESTResponse({'health': result})
