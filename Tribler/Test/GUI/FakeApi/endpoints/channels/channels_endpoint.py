import json
from random import sample

from twisted.web import http, resource

import tribler_utils
from models.playlist import Playlist


class BaseChannelsEndpoint(resource.Resource):

    @staticmethod
    def return_404(request, message="the channel with the provided cid is not known"):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(http.NOT_FOUND)
        return json.dumps({"error": message})


class ChannelsEndpoint(BaseChannelsEndpoint):

    def __init__(self):
        BaseChannelsEndpoint.__init__(self)

        child_handler_dict = {"subscribed": ChannelsSubscribedEndpoint, "discovered": ChannelsDiscoveredEndpoint,
                              "popular": ChannelsPopularEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls())


class ChannelsSubscribedEndpoint(resource.Resource):

    def getChild(self, path, request):
        return ChannelsModifySubscriptionEndpoint(path)

    def render_GET(self, request):
        subscribed = []
        for channel_id in tribler_utils.tribler_data.subscribed_channels:
            subscribed.append(tribler_utils.tribler_data.channels[channel_id].get_json())
        return json.dumps({"subscribed": subscribed})


class ChannelsModifySubscriptionEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid):
        BaseChannelsEndpoint.__init__(self)
        self.cid = cid

    def render_PUT(self, request):
        request.setHeader('Content-Type', 'text/json')

        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        if channel is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        if channel.subscribed:
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": "you are already subscribed to this channel"})

        tribler_utils.tribler_data.subscribed_channels.add(channel.id)
        channel.subscribed = True

        return json.dumps({"subscribed": True})

    def render_DELETE(self, request):
        request.setHeader('Content-Type', 'text/json')

        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        if channel is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        if not channel.subscribed:
            return ChannelsModifySubscriptionEndpoint.return_404(request,
                                                                 message="you are not subscribed to this channel")

        tribler_utils.tribler_data.subscribed_channels.remove(channel.id)
        channel.subscribed = False

        return json.dumps({"unsubscribed": True})


class ChannelsDiscoveredEndpoint(resource.Resource):

    def getChild(self, path, request):
        return ChannelsDiscoveredSpecificEndpoint(path)

    def render_GET(self, request):
        channels = []
        for channel in tribler_utils.tribler_data.channels:
            channels.append(channel.get_json())
        return json.dumps({"channels": channels}, ensure_ascii=False)


class ChannelsDiscoveredSpecificEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid):
        BaseChannelsEndpoint.__init__(self)

        child_handler_dict = {"torrents": ChannelTorrentsEndpoint, "playlists": ChannelPlaylistsEndpoint,
                              "rssfeeds": ChannelRssFeedsEndpoint, "recheckfeeds": ChannelRecheckFeedsEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(cid))


class ChannelTorrentsEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid):
        BaseChannelsEndpoint.__init__(self)
        self.cid = cid

    def render_GET(self, request):
        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        if channel is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        results_json = []
        for torrent in channel.torrents:
            torrent_json = torrent.get_json()
            if tribler_utils.tribler_data.settings["settings"]["general"]["family_filter"] and torrent_json["category"] == 'xxx':
                continue
            results_json.append(torrent_json)

        return json.dumps({"torrents": results_json})


class ChannelPlaylistsEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid):
        BaseChannelsEndpoint.__init__(self)
        self.cid = cid

    def getChild(self, path, request):
        return ChannelsModifyPlaylistEndpoint(self.cid, path)

    def render_GET(self, request):
        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        if channel is None:
            return BaseChannelsEndpoint.return_404(request)

        playlists = []
        for playlist in channel.playlists:
            playlists.append(playlist.get_json())

        return json.dumps({"playlists": playlists})

    def render_PUT(self, request):
        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        if channel is None:
            return BaseChannelsEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)

        if 'name' not in parameters or len(parameters['name']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "name parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "description parameter missing"})

        channel.create_playlist(parameters['name'][0], parameters['description'][0])

        return json.dumps({"created": True})


class ChannelsModifyPlaylistEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid, playlist_id):
        BaseChannelsEndpoint.__init__(self)
        self.cid = cid
        self.playlist_id = playlist_id

    def getChild(self, path, request):
        return ChannelsModifyPlaylistTorrentsEndpoint(self.cid, self.playlist_id, path)

    def render_DELETE(self, request):
        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        if channel is None:
            return BaseChannelsEndpoint.return_404(request)

        playlist = channel.get_playlist_with_id(self.playlist_id)
        if playlist is None:
            return BaseChannelsEndpoint.return_404(request, message="this playlist cannot be found")

        channel.playlists.remove(playlist)

        return json.dumps({"removed": True})

    def render_POST(self, request):
        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        if channel is None:
            return BaseChannelsEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)

        if 'name' not in parameters or len(parameters['name']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "name parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "description parameter missing"})

        playlist = channel.get_playlist_with_id(self.playlist_id)
        if playlist is None:
            return BaseChannelsEndpoint.return_404(request, message="this playlist cannot be found")

        playlist.name = parameters['name'][0]
        playlist.description = parameters['description'][0]

        return json.dumps({"modified": True})


class ChannelsModifyPlaylistTorrentsEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid, playlist_id, infohash):
        BaseChannelsEndpoint.__init__(self)
        self.cid = cid
        self.playlist_id = playlist_id
        self.infohash = infohash

    def render_PUT(self, request):
        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        playlist = channel.get_playlist_with_id(self.playlist_id)
        playlist.add_torrent(channel.get_torrent_with_infohash(self.infohash))

        return json.dumps({"added": True})

    def render_DELETE(self, request):
        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        playlist = channel.get_playlist_with_id(self.playlist_id)
        playlist.remove_torrent(self.infohash)

        return json.dumps({"removed": True})


class ChannelsPopularEndpoint(BaseChannelsEndpoint):

    def render_GET(self, request):
        results_json = [channel.get_json() for channel in sample(tribler_utils.tribler_data.channels, 20)]
        return json.dumps({"channels": results_json})


class ChannelRssFeedsEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid):
        BaseChannelsEndpoint.__init__(self)
        self.cid = cid

    def getChild(self, path, request):
        return ChannelModifyRssFeedsEndpoint(self.cid, path)

    def render_GET(self, request):
        channel = tribler_utils.tribler_data.get_channel_with_cid(self.cid)
        if channel is None:
            return BaseChannelsEndpoint.return_404(request)

        request.setHeader('Content-Type', 'text/json')
        feeds_list = []
        for url in tribler_utils.tribler_data.rss_feeds:
            feeds_list.append({'url': url})

        return json.dumps({"rssfeeds": feeds_list})


class ChannelModifyRssFeedsEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid, feed_url):
        BaseChannelsEndpoint.__init__(self)
        self.cid = cid
        self.feed_url = feed_url

    def render_PUT(self, request):
        request.setHeader('Content-Type', 'text/json')

        if self.feed_url in tribler_utils.tribler_data.rss_feeds:
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": "this rss feed already exists"})

        tribler_utils.tribler_data.rss_feeds.append(self.feed_url)

        return json.dumps({"added": True})

    def render_DELETE(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return BaseChannelsEndpoint.return_404(request)

        if self.feed_url not in tribler_utils.tribler_data.rss_feeds:
            return BaseChannelsEndpoint.return_404(request, message="this url is not added to your RSS feeds")

        tribler_utils.tribler_data.rss_feeds.remove(self.feed_url)

        request.setHeader('Content-Type', 'text/json')
        return json.dumps({"removed": True})


class ChannelRecheckFeedsEndpoint(BaseChannelsEndpoint):

    def __init__(self, cid):
        BaseChannelsEndpoint.__init__(self)
        self.cid = cid

    def render_POST(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return BaseChannelsEndpoint.return_404(request)

        request.setHeader('Content-Type', 'text/json')
        return json.dumps({"rechecked": True})
