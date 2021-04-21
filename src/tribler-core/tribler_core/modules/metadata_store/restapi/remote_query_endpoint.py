import time

from aiohttp import web

from aiohttp_apispec import docs, querystring_schema

from ipv8.REST.schema import schema

from marshmallow.fields import String

from pony.orm import db_session

from tribler_core.modules.metadata_store.restapi.metadata_endpoint import MetadataEndpointBase
from tribler_core.modules.metadata_store.restapi.metadata_schema import RemoteQueryParameters
from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse
from tribler_core.utilities.unicode import hexlify


class RemoteQueryEndpoint(MetadataEndpointBase):
    """
    This endpoint fires a remote search in the IPv8 GigaChannel Community.
    """

    def setup_routes(self):
        self.app.add_routes([web.put('', self.create_remote_search_request)])
        self.app.add_routes([web.get('/channels_peers', self.get_channels_peers)])

    def sanitize_parameters(self, parameters):
        sanitized = super().sanitize_parameters(parameters)

        # Convert frozenset to string
        if "metadata_type" in sanitized:
            sanitized["metadata_type"] = [str(mt) for mt in sanitized["metadata_type"] if mt]
        if "channel_pk" in parameters:
            sanitized["channel_pk"] = parameters["channel_pk"]
        if "origin_id" in parameters:
            sanitized["origin_id"] = int(parameters["origin_id"])

        return sanitized

    @docs(
        tags=['Metadata'],
        summary="Perform a search for a given query.",
        responses={200: {'schema': schema(RemoteSearchResponse={'request_uuid': String()})}},
    )
    @querystring_schema(RemoteQueryParameters)
    async def create_remote_search_request(self, request):
        # Query remote results from the GigaChannel Community.
        # Results are returned over the Events endpoint.
        try:
            sanitized = self.sanitize_parameters(request.query)
        except (ValueError, KeyError) as e:
            return RESTResponse({"error": f"Error processing request parameters: {e}"}, status=HTTP_BAD_REQUEST)

        request_uuid, peers_list = self.session.gigachannel_community.send_search_request(**sanitized)
        peers_mid_list = [hexlify(p.mid) for p in peers_list]

        return RESTResponse({"request_uuid": str(request_uuid), "peers": peers_mid_list})

    async def get_channels_peers(self, _):
        # Get debug stats for peers serving channels
        current_time = time.time()
        result = []
        mapping = self.session.gigachannel_community.channels_peers
        with db_session:
            for id_tuple, peers in mapping._channels_dict.items():  # pylint:disable=W0212
                channel_pk, channel_id = id_tuple
                chan = self.session.mds.ChannelMetadata.get(public_key=channel_pk, id_=channel_id)

                peers_list = []
                for p in peers:
                    peers_list.append((hexlify(p.mid), int(current_time - p.last_response)))

                chan_dict = {
                    "channel_name": chan.title if chan else None,
                    "channel_pk": hexlify(channel_pk),
                    "channel_id": channel_id,
                    "peers": peers_list,
                }
                result.append(chan_dict)

        return RESTResponse({"channels_list": result})
