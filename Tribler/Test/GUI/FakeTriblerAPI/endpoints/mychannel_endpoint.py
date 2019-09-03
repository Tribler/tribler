from __future__ import absolute_import

from binascii import unhexlify

from twisted.web import http, resource

import Tribler.Core.Utilities.json_util as json
import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Test.GUI.FakeTriblerAPI.constants import COMMITTED, TODELETE
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.metadata_endpoint import SpecificChannelTorrentsEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.models.channel import Channel


class MyChannelBaseEndpoint(resource.Resource):

    @staticmethod
    def return_404(request, message="your channel has not been created"):
        request.setResponseCode(http.NOT_FOUND)
        return json.twisted_dumps({"error": message})


class MyChannelEndpoint(MyChannelBaseEndpoint):

    def __init__(self):
        MyChannelBaseEndpoint.__init__(self)
        self.putChild(b"torrents", MyChannelTorrentsEndpoint())
        self.putChild(b"commit", MyChannelCommitEndpoint())

    def render_GET(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return MyChannelBaseEndpoint.return_404(request)

        return json.twisted_dumps({
            'mychannel': {
                'public_key': hexlify(my_channel.public_key),
                'name': my_channel.name,
                'description': my_channel.description,
                'dirty': my_channel.is_dirty()
            }
        })

    def render_PUT(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        channel_name = parameters['name'][0]
        channel_description = parameters['description'][0]

        my_channel = Channel(len(tribler_utils.tribler_data.channels) - 1,
                             name=channel_name, description=channel_description)
        tribler_utils.tribler_data.channels.append(my_channel)
        tribler_utils.tribler_data.my_channel = my_channel.id

        return json.twisted_dumps({"added": my_channel.id})

    def render_POST(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return MyChannelBaseEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)
        my_channel.name = parameters['name'][0]
        my_channel.description = parameters['description'][0]

        return json.twisted_dumps({"edited": my_channel.id})


class MyChannelCommitEndpoint(MyChannelBaseEndpoint):

    def render_POST(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            request.setResponseCode(http.NOT_FOUND)
            return "your channel has not been created"

        to_remove = []

        for torrent in my_channel.torrents:
            if torrent.status == TODELETE:
                to_remove.append(torrent)
            else:
                torrent.status = COMMITTED

        for torrent in to_remove:
            my_channel.torrents.remove(torrent)

        return json.twisted_dumps({"success": True})


class MyChannelTorrentsEndpoint(MyChannelBaseEndpoint):

    def getChild(self, path, request):
        if path == b"count":
            return MyChannelTorrentsCountEndpoint()
        return MyChannelSpecificTorrentEndpoint(path)

    def render_GET(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            request.setResponseCode(http.NOT_FOUND)
            return "your channel has not been created"

        request.args[b'channel'] = [hexlify(my_channel.public_key)]
        first, last, sort_by, sort_asc, query_filter, channel = \
            SpecificChannelTorrentsEndpoint.sanitize_parameters(request.args)

        torrents, total = tribler_utils.tribler_data.get_torrents(first, last, sort_by, sort_asc, query_filter, channel,
                                                                  include_status=True)
        return json.twisted_dumps({
            "results": torrents,
            "first": first,
            "last": last,
            "sort_by": sort_by.decode('utf-8') if sort_by else None,
            "sort_asc": int(sort_asc),
            "dirty": my_channel.is_dirty()
        })

    def render_POST(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            request.setResponseCode(http.NOT_FOUND)
            return "your channel has not been created"

        parameters = http.parse_qs(request.content.read(), 1)
        if 'status' not in parameters or 'infohashes' not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "status or infohashes parameter missing"})

        new_status = int(parameters['status'][0])
        infohashes = parameters['infohashes'][0].split(',')
        for infohash in infohashes:
            torrent = my_channel.get_torrent_with_infohash(unhexlify(infohash))
            if torrent:
                torrent.status = new_status

        return json.twisted_dumps({"success": True})

    def render_DELETE(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            request.setResponseCode(http.NOT_FOUND)
            return "your channel has not been created"

        for torrent in my_channel.torrents:
            torrent.status = TODELETE

        return json.twisted_dumps({"success": True})


class MyChannelTorrentsCountEndpoint(MyChannelBaseEndpoint):

    def render_GET(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            request.setResponseCode(http.NOT_FOUND)
            return "your channel has not been created"

        request.args['channel'] = [hexlify(my_channel.public_key)]
        first, last, sort_by, sort_asc, query_filter, channel = \
            SpecificChannelTorrentsEndpoint.sanitize_parameters(request.args)

        _, total = tribler_utils.tribler_data.get_torrents(first, last, sort_by, sort_asc, query_filter, channel,
                                                           include_status=True)
        return json.twisted_dumps({"total": total})


class MyChannelSpecificTorrentEndpoint(MyChannelBaseEndpoint):

    def __init__(self, infohash):
        MyChannelBaseEndpoint.__init__(self)
        self.infohash = infohash

    def render_PATCH(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        if 'status' not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "status parameter missing"})

        my_channel = tribler_utils.tribler_data.get_my_channel()
        torrent = my_channel.get_torrent_with_infohash(unhexlify(self.infohash))
        if not torrent:
            request.setResponseCode(http.NOT_FOUND)
            return json.twisted_dumps({"error": "torrent with the specified infohash could not be found"})

        new_status = int(parameters['status'][0])
        torrent.status = new_status

        return json.twisted_dumps({"success": True, "new_status": new_status, "dirty": my_channel.is_dirty()})
