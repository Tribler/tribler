from __future__ import absolute_import

import logging
from binascii import unhexlify
from random import sample

from twisted.web import http, resource

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.metadata_endpoint_base import MetadataEndpointBase
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.GUI.FakeTriblerAPI import tribler_utils


class ChannelsEndpointBase(MetadataEndpointBase):
    def __init__(self):
        resource.Resource.__init__(self)
        self.session = MockObject()


# /channels
#                   /popular
#                   /<public_key>
class ChannelsEndpoint(ChannelsEndpointBase):
    def getChild(self, path, request):
        if path == b"popular":
            return ChannelsPopularEndpoint()
        return ChannelsPublicKeyEndpoint(self.session, path)

    @classmethod
    def sanitize_parameters(cls, parameters):
        return dict(
            subscribed=None if b'subscribed' not in parameters else bool(int(parameters[b'subscribed'][0]) > 0),
            **ChannelsEndpointBase.sanitize_parameters(parameters)
        )

    # Get list of all channels known to the system
    # TODO: DRY it with SpecificChannel endpoint?
    def render_GET(self, request):
        sanitized = self.sanitize_parameters(request.args)
        include_total = request.args['include_total'][0] if 'include_total' in request.args else ''
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
        return json.twisted_dumps(response_dict)


# /popular
class ChannelsPopularEndpoint(ChannelsEndpointBase):
    def render_GET(self, request):

        if b'limit' in request.args and request.args[b'limit']:
            limit_channels = int(request.args[b'limit'][0])

            if limit_channels <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "the limit parameter must be a positive number"})

        results = [channel.get_json() for channel in sample(tribler_utils.tribler_data.channels, 20)]
        return json.twisted_dumps({"channels": results})


# /<public_key>
#              /<id_>
class ChannelsPublicKeyEndpoint(ChannelsEndpointBase):
    def getChild(self, path, request):
        return SpecificChannelEndpoint(self.session, self.channel_pk, path)

    def __init__(self, session, path):
        ChannelsEndpointBase.__init__(self)
        if path == b"mychannel":
            self.channel_pk = tribler_utils.tribler_data.get_my_channel().public_key
        else:
            self.channel_pk = unhexlify(path)


class SpecificChannelEndpointBase(ChannelsEndpointBase):
    def __init__(self, session, channel_pk, path):
        self._logger = logging.getLogger(self.__class__.__name__)
        ChannelsEndpointBase.__init__(self)
        self.channel_pk = channel_pk
        self.channel_id = int(path)


# /<id>
#      /torrents
#      /commit
class SpecificChannelEndpoint(SpecificChannelEndpointBase):
    def __init__(self, session, channel_pk, path):
        SpecificChannelEndpointBase.__init__(self, session, channel_pk, path)

    # Get the list of the channel's contents (torrents/channels/etc.)
    def render_GET(self, request):
        sanitized = self.sanitize_parameters(request.args)
        include_total = request.args['include_total'][0] if 'include_total' in request.args else ''
        sanitized.update({"channel_pk": self.channel_pk, "origin_id": self.channel_id})

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
        return json.twisted_dumps(response_dict)


# /commit
class SpecificChannelCommitEndpoint(SpecificChannelEndpointBase):
    def render_POST(self, request):
        return json.twisted_dumps({"success": True})

    def render_GET(self, request):
        return json.twisted_dumps({"dirty": 1})
