from binascii import hexlify

from aiohttp import web
from aiohttp_apispec import docs, querystring_schema
from ipv8.REST.schema import schema
from marshmallow.fields import List, String

from tribler.core.components.content_discovery.community.content_discovery_community import ContentDiscoveryCommunity
from tribler.core.components.content_discovery.restapi.schema import RemoteQueryParameters
from tribler.core.components.database.restapi.database_endpoint import DatabaseEndpoint
from tribler.core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, MAX_REQUEST_SIZE, RESTEndpoint, \
    RESTResponse
from tribler.core.utilities.utilities import froze_it, to_fts_query


@froze_it
class SearchEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    """
    path = '/search'

    def __init__(self,
                 popularity_community: ContentDiscoveryCommunity,
                 middlewares=(),
                 client_max_size=MAX_REQUEST_SIZE):
        super().__init__(middlewares, client_max_size)
        self.popularity_community = popularity_community

    def setup_routes(self):
        self.app.add_routes([web.put('/remote', self.remote_search)])

    @classmethod
    def sanitize_parameters(cls, parameters):
        return DatabaseEndpoint.sanitize_parameters(parameters)

    @docs(
        tags=['Metadata'],
        summary="Perform a search for a given query.",
        responses={
            200: {
                'schema': schema(RemoteSearchResponse={'request_uuid': String(), 'peers': List(String())}),
                "examples": {
                    'Success': {
                        "request_uuid": "268560c0-3f28-4e6e-9d85-d5ccb0269693",
                        "peers": ["50e9a2ce646c373985a8e827e328830e053025c6",
                                  "107c84e5d9636c17b46c88c3ddb54842d80081b0"]
                    }
                }
            }
        },
    )
    @querystring_schema(RemoteQueryParameters)
    async def remote_search(self, request):
        try:
            sanitized = self.sanitize_parameters(request.query)
        except (ValueError, KeyError) as e:
            return RESTResponse({"error": f"Error processing request parameters: {e}"}, status=HTTP_BAD_REQUEST)
        query = request.query.get('fts_text')
        if t_filter := request.query.get('filter'):
            query += f' {t_filter}'
        fts = to_fts_query(query)
        sanitized['txt_filter'] = fts
        self._logger.info(f'Parameters: {sanitized}')
        self._logger.info(f'FTS: {fts}')

        request_uuid, peers_list = self.popularity_community.send_search_request(**sanitized)
        peers_mid_list = [hexlify(p.mid).decode() for p in peers_list]

        return RESTResponse({"request_uuid": str(request_uuid), "peers": peers_mid_list})
