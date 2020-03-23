from binascii import unhexlify

from aiohttp import web

from aiohttp_apispec import docs, querystring_schema

from ipv8.REST.schema import schema

from marshmallow.fields import Boolean

from tribler_core.modules.metadata_store.restapi.metadata_endpoint import MetadataEndpointBase
from tribler_core.modules.metadata_store.restapi.metadata_schema import RemoteQueryParameters
from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse
from tribler_core.utilities.unicode import hexlify


class RemoteQueryEndpoint(MetadataEndpointBase):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    It also fires a remote search in the IPv8 channel community.
    """

    def setup_routes(self):
        self.app.add_routes([web.put('', self.create_remote_search_request)])

    def sanitize_parameters(self, parameters):
        sanitized = super(RemoteQueryEndpoint, self).sanitize_parameters(parameters)
        sanitized.update({'uuid': parameters['uuid'], 'channel_pk': unhexlify(parameters.get('channel_pk', ""))})
        return sanitized

    @docs(
        tags=['Metadata'],
        summary="Perform a search for a given query.",
        responses={
            200: {
                'schema': schema(RemoteSearchResponse={
                    'success': Boolean
                })
            }
        }
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
            if sanitized["txt_filter"] and sanitized["channel_pk"]:
                return RESTResponse({"error": "Remote search by text and pk is not supported"}, status=HTTP_BAD_REQUEST)
        except (ValueError, KeyError) as e:
            return RESTResponse({"error": "Error processing request parameters: %s" % e}, status=HTTP_BAD_REQUEST)

        self.session.gigachannel_community.send_search_request(
            sanitized['txt_filter'] or ('"%s"*' % hexlify(sanitized['channel_pk'])),
            metadata_type=sanitized.get('metadata_type'),
            sort_by=sanitized['sort_by'],
            sort_asc=sanitized['sort_desc'],
            hide_xxx=sanitized['hide_xxx'],
            uuid=sanitized['uuid'],
        )

        return RESTResponse({"success": True})
