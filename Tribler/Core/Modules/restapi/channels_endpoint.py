import json

from twisted.web import resource
from twisted.web.resource import NoResource

from Tribler.Core.simpledefs import NTFY_CHANNELCAST


class BaseChannelsEndpoint(resource.Resource):
    """
    This class contains some utility methods to work with raw channels from the database.
    All endpoints that are using the database, should derive from this class.
    """

    def convert_db_channel_to_json(self, channel):
        return {"id": channel[0], "dispersy_cid": channel[1].encode('hex'), "name": channel[2], "description": channel[3],
                "votes": channel[5], "torrents": channel[4], "spam": channel[6], "modified": channel[8],
                "subscribed": (channel[7] == 2)}


class ChannelsEndpoint(BaseChannelsEndpoint):
    """
    This endpoint is responsible for handing all requests regarding channels in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

        child_handler_dict = {"subscribed": ChannelsSubscribedEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))


class ChannelsSubscribedEndpoint(BaseChannelsEndpoint):
    """
    A GET request to this endpoint returns all the channels the user is subscribed to.

    Example GET response:
    {
        "subscribed": [{
            "id": 3,
            "dispersy_cid": "da69aaad39ccf468aba2ab9177d5f8d8160135e6",
            "name": "My fancy channel",
            "description": "A description of this fancy channel",
            "subscribed": True,
            "votes": 23,
            "torrents": 3,
            "spam": 5,
            "modified": 14598395,
        }, ...]
    }
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def render_GET(self, request):
        subscribed_channels_db = self.channel_db_handler.getMySubscribedChannels(includeDispsersy=True)
        results_json = []
        for channel in subscribed_channels_db:
            results_json.append(self.convert_db_channel_to_json(channel))

        return json.dumps({"subscribed": results_json})
