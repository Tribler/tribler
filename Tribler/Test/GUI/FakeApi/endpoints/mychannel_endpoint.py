import json

from twisted.web import http, resource
from models.channel import Channel

import tribler_utils


class MyChannelBaseEndpoint(resource.Resource):

    @staticmethod
    def return_404(request, message="your channel has not been created"):
        request.setResponseCode(http.NOT_FOUND)
        return json.dumps({"error": message})


class MyChannelEndpoint(MyChannelBaseEndpoint):

    def getChild(self, path, request):
        if path == "torrents":
            return MyChannelTorrentsEndpoint()
        elif path == "rssfeeds":
            return MyChannelRssFeedsEndpoint()
        elif path == "recheckfeeds":
            return MyChannelRecheckFeedsEndpoint()
        elif path == "playlists":
            return MyChannelPlaylistsEndpoint()

    def render_GET(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return MyChannelBaseEndpoint.return_404(request)

        request.setHeader('Content-Type', 'text/json')
        return json.dumps({'mychannel': {'identifier': my_channel.cid, 'name': my_channel.name,
                                         'description': my_channel.description}})

    def render_PUT(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        print parameters
        channel_name = parameters['name'][0]
        channel_description = parameters['description'][0]

        my_channel = Channel(len(tribler_utils.tribler_data.channels) - 1,
                             name=channel_name, description=channel_description)
        tribler_utils.tribler_data.channels.append(my_channel)
        tribler_utils.tribler_data.my_channel = my_channel.id

        return json.dumps({"added": my_channel.id})

    def render_POST(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return MyChannelBaseEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)
        my_channel.name = parameters['name'][0]
        my_channel.description = parameters['description'][0]

        return json.dumps({"edited": my_channel.id})


class MyChannelTorrentsEndpoint(resource.Resource):

    def render_GET(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            request.setResponseCode(http.NOT_FOUND)
            return "your channel has not been created"

        request.setHeader('Content-Type', 'text/json')
        torrent_list = []
        for torrent in my_channel.torrents:
            torrent_list.append({'name': torrent.name, 'infohash': torrent.infohash, 'added': torrent.time_added})

        return json.dumps({"torrents": torrent_list})
