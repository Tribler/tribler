from binascii import unhexlify

from aiohttp import web
from aiohttp_apispec import docs, querystring_schema
from ipv8.REST.schema import schema
from marshmallow.fields import String, List


from tribler.core.components.metadata_store.restapi.metadata_endpoint import MetadataEndpointBase
from tribler.core.components.metadata_store.restapi.metadata_schema import RemoteQueryParameters
from tribler.core.components.popularity.community.popularity_community import PopularityCommunity
from tribler.core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import froze_it


@froze_it
class RemoteQueryEndpoint(MetadataEndpointBase):
    """
    This endpoint fires a remote search in the IPv8 GigaChannel Community.
    """
    path = '/remote_query'

    def __init__(self, popularity_community: PopularityCommunity, *args, **kwargs):
        MetadataEndpointBase.__init__(self, *args, **kwargs)
        self.popularity_community = popularity_community

    def setup_routes(self):
        self.app.add_routes([web.put('', self.create_remote_search_request)])

    def sanitize_parameters(self, parameters):
        sanitized = super().sanitize_parameters(parameters)

        if "channel_pk" in parameters:
            sanitized["channel_pk"] = unhexlify(parameters["channel_pk"])
        if "origin_id" in parameters:
            sanitized["origin_id"] = int(parameters["origin_id"])

        return sanitized

    @docs(
        tags=['Metadata'],
        summary="Perform a search for a given query.",
        responses={200: {
            'schema': schema(RemoteSearchResponse={'request_uuid': String(), 'peers': List(String())})},
            "examples": {
                'Success': {
                    "request_uuid": "268560c0-3f28-4e6e-9d85-d5ccb0269693",
                    "peers": ["50e9a2ce646c373985a8e827e328830e053025c6", "107c84e5d9636c17b46c88c3ddb54842d80081b0"]
                }
            }
        },
    )
    @querystring_schema(RemoteQueryParameters)
    async def create_remote_search_request(self, request):
        self._logger.info('Create remote search request')
        # Query remote results from the GigaChannel Community.
        # Results are returned over the Events endpoint.
        try:
            sanitized = self.sanitize_parameters(request.query)
        except (ValueError, KeyError) as e:
            return RESTResponse({"error": f"Error processing request parameters: {e}"}, status=HTTP_BAD_REQUEST)
        self._logger.info(f'Parameters: {sanitized}')

        request_uuid, peers_list = self.popularity_community.send_search_request(**sanitized)
        peers_mid_list = [hexlify(p.mid) for p in peers_list]

        return RESTResponse({"request_uuid": str(request_uuid), "peers": peers_mid_list})
