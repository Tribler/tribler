from aiohttp import web

from aiohttp_apispec import docs, querystring_schema

from ipv8.REST.schema import schema

from marshmallow.fields import String

from tribler_core.modules.metadata_store.restapi.metadata_endpoint import MetadataEndpointBase
from tribler_core.modules.metadata_store.restapi.metadata_schema import RemoteQueryParameters
from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse


class RemoteQueryEndpoint(MetadataEndpointBase):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    It also fires a remote search in the IPv8 channel community.
    """

    def setup_routes(self):
        self.app.add_routes([web.put('', self.create_remote_search_request)])

    def sanitize_parameters(self, parameters):
        sanitized = super(RemoteQueryEndpoint, self).sanitize_parameters(parameters)

        # Convert frozenset to string
        if "metadata_type" in sanitized:
            sanitized["metadata_type"] = [str(mt) for mt in sanitized["metadata_type"] if mt]
        if "channel_pk" in parameters:
            sanitized["channel_pk"] = parameters["channel_pk"]

        return sanitized

    @docs(
        tags=['Metadata'],
        summary="Perform a search for a given query.",
        responses={200: {'schema': schema(RemoteSearchResponse={'request_uuid': String()})}},
    )
    @querystring_schema(RemoteQueryParameters)
    async def create_remote_search_request(self, request):
        # Query remote results from the GigaChannel Community v1.0.
        # v1.0 does not support searching for text limited by public key.
        # GigaChannel v1.0 search community sends requests for channel contents by putting channel's public key
        # into the text filter field. To communicate with older clients we have to shape the request accordingly.
        # Results are returned over the Events endpoint.
        try:
            sanitized = self.sanitize_parameters(request.query)
        except (ValueError, KeyError) as e:
            return RESTResponse({"error": "Error processing request parameters: %s" % e}, status=HTTP_BAD_REQUEST)

        request_uuid = self.session.gigachannel_community.send_search_request(**sanitized)
        return RESTResponse({"request_uuid": str(request_uuid)})
