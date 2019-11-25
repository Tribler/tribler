from binascii import unhexlify
from random import sample

from aiohttp import web

from Tribler.Core.Modules.restapi.metadata_endpoint_base import MetadataEndpointBase
from Tribler.Core.Modules.restapi.rest_endpoint import RESTResponse, HTTP_BAD_REQUEST
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.GUI.FakeTriblerAPI import tribler_utils


class ChannelsEndpoint(MetadataEndpointBase):

    def __init__(self, _):
        super(ChannelsEndpoint, self).__init__(MockObject())

    def setup_routes(self):
        self.app.add_routes(
            [web.get('', self.get_channels),
             web.get('/popular', self.get_popular_channels),
             web.get(r'/{channel_pk:\w*}/{channel_id:\w*}', self.get_channel_contents),
             web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/commit', self.post_commit),
             web.get(r'/{channel_pk:\w*}/{channel_id:\w*}/commit', self.is_channel_dirty)])

    @classmethod
    def sanitize_parameters(cls, parameters):
        return dict(
            subscribed=None if 'subscribed' not in parameters else bool(int(parameters['subscribed']) > 0),
            **MetadataEndpointBase.sanitize_parameters(parameters)
        )

    # Get list of all channels known to the system
    # TODO: DRY it with SpecificChannel endpoint?
    async def get_channels(self, request):
        sanitized = self.sanitize_parameters(request.query)
        include_total = request.query.get('include_total', '')
        sanitized.update({"origin_id": 0})

        channels_list, total = tribler_utils.tribler_data.get_channels(**sanitized)
        total = total if include_total else None
        response_dict = {
            "results": channels_list,
            "first": sanitized["first"],
            "last": sanitized["last"],
            "sort_by": sanitized["sort_by"],
            "sort_desc": int(sanitized["sort_desc"]),
        }
        if total is not None:
            response_dict.update({"total": total})
        return RESTResponse(response_dict)

    async def get_popular_channels(self, request):
        if request.query.get('limit', 1) <= 0:
            return RESTResponse({"error": "the limit parameter must be a positive number"}, status=HTTP_BAD_REQUEST)

        results = [channel.get_json() for channel in sample(tribler_utils.tribler_data.channels, 20)]
        return RESTResponse({"channels": results})

    # Get the list of the channel's contents (torrents/channels/etc.)
    async def get_channel_contents(self, request):
        sanitized = self.sanitize_parameters(request.query)
        include_total = request.query.get('include_total', '')
        channel_pk = tribler_utils.tribler_data.get_my_channel().public_key \
            if request.match_info['channel_pk'] == 'mychannel' else unhexlify(request.match_info['channel_pk'])
        channel_id = int(request.match_info['channel_id'])
        sanitized.update({"channel_pk": channel_pk, "origin_id": channel_id})

        # FIXME: normalize attribute names everywhere to their respective Pony DB names

        contents_list, total = tribler_utils.tribler_data.get_torrents(**sanitized)
        total = total if include_total else None
        response_dict = {
            "results": contents_list,
            "first": sanitized['first'],
            "last": sanitized['last'],
            "sort_by": sanitized['sort_by'],
            "sort_desc": int(sanitized['sort_desc']),
        }
        if total is not None:
            response_dict.update({"total": total})
        return RESTResponse(response_dict)

    async def post_commit(self, _):
        return RESTResponse({"success": True})

    async def is_channel_dirty(self, _):
        return RESTResponse({"dirty": 1})
