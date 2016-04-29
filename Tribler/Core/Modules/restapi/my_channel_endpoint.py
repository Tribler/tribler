import json
from twisted.web import http, server, resource
from Tribler.Core.simpledefs import NTFY_CHANNELCAST


class MyChannelBaseEndpoint(resource.Resource):
    """
    Base class for all endpoints related to fetching information about my channel.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    @staticmethod
    def return_404(request):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(http.NOT_FOUND)
        return "your channel has not been created"


class MyChannelEndpoint(MyChannelBaseEndpoint):
    """
    This endpoint is reponsible for handing all requests regarding your channel such as getting and updating
    torrents, playlists and rss-feeds.
    """

    def getChild(self, path, request):
        child_handler_dict = {"overview": MyChannelOverviewEndpoint, "torrents": MyChannelTorrentsEndpoint}
        if path not in child_handler_dict:
            return None

        return child_handler_dict[path](self.session)


class MyChannelOverviewEndpoint(MyChannelBaseEndpoint):
    """
    Return the name, description and identifier of your channel.
    This endpoint returns a 404 HTTP response if you have not created a channel (yet).

    Example response:
    {
        "overview": {
            "name": "My Tribler channel",
            "description": "A great collection of open-source movies",
            "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
        }
    }
    """

    def render_GET(self, request):
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        my_channel = self.channel_db_handler.getChannel(my_channel_id)
        request.setHeader('Content-Type', 'text/json')
        return json.dumps({'overview': {'identifier': my_channel[1].encode('hex'), 'name': my_channel[2],
                                        'description': my_channel[3]}})


class MyChannelTorrentsEndpoint(MyChannelBaseEndpoint):
    """
    Return the torrents in your channel. For each torrent item, the infohash, name and timestamp added is included.
    This endpoint returns a 404 HTTP response if you have not created a channel (yet).

    Example response:
    {
        "torrents": [{
            "name": "ubuntu-15.04.iso",
            "added": 1461840601,
            "infohash": "e940a7a57294e4c98f62514b32611e38181b6cae"
        }, ...]
    }
    """

    def render_GET(self, request):
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        req_columns = ['ChannelTorrents.name', 'infohash', 'ChannelTorrents.inserted']
        torrents = self.channel_db_handler.getTorrentsFromChannelId(my_channel_id, True, req_columns)

        request.setHeader('Content-Type', 'text/json')
        torrent_list = []
        for torrent in torrents:
            torrent_list.append({'name': torrent[0], 'infohash': torrent[1].encode('hex'), 'added': torrent[2]})
        return json.dumps({'torrents': torrent_list})
