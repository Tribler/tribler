import json
from twisted.web import server, resource
from Tribler.Core.simpledefs import NTFY_CHANNELCAST


class MyChannelEndpoint(resource.Resource):
    """
    This endpoint is reponsible for handing all requests regarding your channel such as getting and updating
    torrents, playlists and rss-feeds.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def getChild(self, path, request):
        if path == "overview":
            return MyChannelOverviewEndpoint(self.session)


class MyChannelOverviewEndpoint(resource.Resource):
    """
    This endpoint returns a 404 HTTP response if you have not created a channel (yet).
    Otherwise, it returns the name, description and identifier of your channel.

    Example response:
    {
        "overview": {
            "name": "My Tribler channel",
            "description": "A great collection of open-source movies",
            "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
        }
    }
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def return_404(self, request):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(404)
        request.finish()

    def render_GET(self, request):
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            self.return_404(request)
            return server.NOT_DONE_YET

        my_channel = self.channel_db_handler.getChannel(my_channel_id)
        request.setHeader('Content-Type', 'text/json')
        return json.dumps({'overview': {'identifier': my_channel[1].encode('hex'), 'name': my_channel[2],
                                        'description': my_channel[3]}})
