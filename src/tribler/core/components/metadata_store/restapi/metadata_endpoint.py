from binascii import unhexlify
from typing import Optional

from aiohttp import ContentTypeError, web
from aiohttp_apispec import docs
from ipv8.REST.base_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean
from pony.orm import db_session

from tribler.core.components.metadata_store.restapi.metadata_endpoint_base import MetadataEndpointBase
from tribler.core.components.restapi.rest.rest_endpoint import RESTResponse
from tribler.core.components.restapi.rest.schema import HandledErrorSchema
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import froze_it

TORRENT_CHECK_TIMEOUT = 20


class UpdateEntryMixin:
    @db_session
    def update_entry(self, public_key, id_, update_dict):
        entry = self.mds.ChannelNode.get(public_key=public_key, id_=id_)
        if not entry:
            return HTTP_NOT_FOUND, {"error": "Object with the specified pk+id could not be found."}

        signed_parameters_to_change = set(entry.payload_arguments).intersection(set(update_dict.keys()))
        if signed_parameters_to_change:
            if 'status' in update_dict:
                return HTTP_BAD_REQUEST, {"error": "Cannot set status manually when changing signed attributes."}
            if entry.status == LEGACY_ENTRY:
                return HTTP_BAD_REQUEST, {"error": "Changing parameters of legacy entries is not supported."}
            if not entry.is_personal:
                return (
                    HTTP_BAD_REQUEST,
                    {"error": "Changing signed parameters in non-personal entries is not supported."},
                )

        return None, entry.update_properties(update_dict).to_simple_dict()


@froze_it
class MetadataEndpoint(MetadataEndpointBase, UpdateEntryMixin):
    """
    This is the top-level endpoint class that serves other endpoints.

    # /metadata
    #          /torrents
    #          /<public_key>
    """
    path = '/metadata'

    def __init__(self, torrent_checker: Optional[TorrentChecker], *args, **kwargs):
        MetadataEndpointBase.__init__(self, *args, **kwargs)
        self.torrent_checker = torrent_checker

    def setup_routes(self):
        self.app.add_routes(
            [
                web.patch('', self.update_channel_entries),
                web.delete('', self.delete_channel_entries),
                web.get('/torrents/{infohash}/health', self.get_torrent_health),
                web.patch(r'/{public_key:\w*}/{id:\w*}', self.update_channel_entry),
                web.get(r'/{public_key:\w*}/{id:\w*}', self.get_channel_entries),
            ]
        )

    @docs(
        tags=['Metadata'],
        summary='Update channel entries.',
        parameters=[
            {
                'in': 'body',
                'name': 'entries',
                'description': 'List of entries to update',
                'example': [{'public_key': '1234567890', 'id': 123, 'property_to_update': 'new_value'}],
                'required': True,
            }
        ],
        responses={
            200: {'description': 'Returns a list of updated entries'},
            HTTP_NOT_FOUND: {'schema': HandledErrorSchema},
            HTTP_BAD_REQUEST: {'schema': HandledErrorSchema},
        },
    )
    async def update_channel_entries(self, request):
        try:
            request_parsed = await request.json()
        except (ContentTypeError, ValueError):
            return RESTResponse({"error": "Bad JSON"}, status=HTTP_BAD_REQUEST)
        results_list = []
        for entry in request_parsed:
            public_key = unhexlify(entry.pop("public_key"))
            id_ = entry.pop("id")
            error, result = self.update_entry(public_key, id_, entry)
            # TODO: handle the results for a list that contains some errors in a smarter way
            if error:
                return RESTResponse(result, status=error)
            results_list.append(result)
        return RESTResponse(results_list)

    @docs(
        tags=['Metadata'],
        summary='Delete channel entries.',
        parameters=[
            {
                'in': 'body',
                'name': 'entries',
                'description': 'List of entries to delete',
                'example': [{'public_key': '1234567890', 'id': 123}],
                'required': True,
            }
        ],
        responses={
            200: {'description': 'Returns a list of deleted entries'},
            HTTP_BAD_REQUEST: {'schema': HandledErrorSchema},
        },
    )
    async def delete_channel_entries(self, request):
        with db_session:
            request_parsed = await request.json()
            results_list = []
            for entry in request_parsed:
                public_key = unhexlify(entry.pop("public_key"))
                id_ = entry.pop("id")
                entry = self.mds.ChannelNode.get(public_key=public_key, id_=id_)
                if not entry:
                    return RESTResponse({"error": "Entry %i not found" % id_}, status=HTTP_BAD_REQUEST)
                entry.delete()
                result = {"public_key": hexlify(public_key), "id": id_, "state": "Deleted"}
                results_list.append(result)
            return RESTResponse(results_list)

    @docs(
        tags=['Metadata'],
        summary='Update a single channel entry.',
        responses={
            200: {'description': 'The updated entry'},
            HTTP_NOT_FOUND: {'schema': HandledErrorSchema},
            HTTP_BAD_REQUEST: {'schema': HandledErrorSchema},
        },
    )
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

    @docs(
        tags=['Metadata'],
        summary='Get channel entries.',
        responses={200: {'description': 'Returns a list of entries'}, HTTP_NOT_FOUND: {'schema': HandledErrorSchema}},
    )
    async def get_channel_entries(self, request):
        public_key = unhexlify(request.match_info['public_key'])
        id_ = request.match_info['id']
        with db_session:
            entry = self.mds.ChannelNode.get(public_key=public_key, id_=id_)

            if entry:
                # TODO: handle costly attributes in a more graceful and generic way for all types of metadata
                entry_dict = entry.to_simple_dict()
            else:
                return RESTResponse({"error": "entry not found in database"}, status=HTTP_NOT_FOUND)

        return RESTResponse(entry_dict)

    @docs(
        tags=["Metadata"],
        summary="Fetch the swarm health of a specific torrent.",
        parameters=[
            {
                'in': 'path',
                'name': 'infohash',
                'description': 'Infohash of the download to remove',
                'type': 'string',
                'required': True,
            },
            {
                'in': 'query',
                'name': 'timeout',
                'description': 'Timeout to be used in the connections to the trackers',
                'type': 'integer',
                'default': 20,
                'required': False,
            },
        ],
        responses={
            200: {
                'schema': schema(
                    HealthCheckResponse={
                        'checking': Boolean()
                    }
                ),
                'examples': [
                    {'checking': 1},
                ],
            }
        },
    )
    async def get_torrent_health(self, request):
        self._logger.info(f'Get torrent health request: {request}')
        try:
            timeout = int(request.query.get('timeout', TORRENT_CHECK_TIMEOUT))
        except ValueError as e:
            return RESTResponse({"error": f"Error processing timeout parameter: {e}"}, status=HTTP_BAD_REQUEST)

        if self.torrent_checker is None:
            return RESTResponse({'checking': False})

        infohash = unhexlify(request.match_info['infohash'])
        check_coro = self.torrent_checker.check_torrent_health(infohash, timeout=timeout, scrape_now=True)
        self.async_group.add_task(check_coro)
        return RESTResponse({'checking': True})
