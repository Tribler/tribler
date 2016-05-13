import json
import time

from twisted.web import http, resource

from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.community.allchannel.community import AllChannelCommunity


VOTE_UNSUBSCRIBE = 0
VOTE_SUBSCRIBE = 2


class BaseChannelsEndpoint(resource.Resource):
    """
    This class contains some utility methods to work with raw channels from the database.
    All endpoints that are using the database, should derive from this class.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    @staticmethod
    def return_404(request, message="the channel with the provided cid is not known"):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(http.NOT_FOUND)
        return json.dumps({"error": message})

    def get_channel_from_db(self, cid):
        """
        Returns information about the channel from the database. Returns None if the channel with given cid
        does not exist.
        """
        channels_list = self.channel_db_handler.getChannelsByCID([cid])
        if not channels_list:
            return None
        return channels_list[0]

    def vote_for_channel(self, cid, vote):
        """
        Make a vote in the channel specified by the cid
        """
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, AllChannelCommunity):
                community.disp_create_votecast(cid, vote, int(time.time()))
                break

    def convert_db_channel_to_json(self, channel):
        return {"id": channel[0], "dispersy_cid": channel[1].encode('hex'), "name": channel[2], "description": channel[3],
                "votes": channel[5], "torrents": channel[4], "spam": channel[6], "modified": channel[8],
                "subscribed": (channel[7] == VOTE_SUBSCRIBE)}


class ChannelsEndpoint(BaseChannelsEndpoint):
    """
    This endpoint is responsible for handing all requests regarding channels in Tribler.
    """

    def __init__(self, session):
        BaseChannelsEndpoint.__init__(self, session)

        child_handler_dict = {"subscribed": ChannelsSubscribedEndpoint, "discovered": ChannelsDiscoveredEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))


class ChannelsSubscribedEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for requests regarding the subscriptions to channels.
    """
    def getChild(self, path, request):
        return ChannelsModifySubscriptionEndpoint(self.session, path)

    def render_GET(self, request):
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
        subscribed_channels_db = self.channel_db_handler.getMySubscribedChannels(include_dispersy=True)
        results_json = [self.convert_db_channel_to_json(channel) for channel in subscribed_channels_db]
        return json.dumps({"subscribed": results_json})


class ChannelsModifySubscriptionEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for methods that modify the list of RSS feed URLs (adding/removing feeds).
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = bytes(cid.decode('hex'))

    def render_PUT(self, request):
        """
        Subscribe to a specific channel. Returns error 409 if you are already subscribed to this channel.

        Example response:
        {
            "subscribed" : True
        }
        """
        request.setHeader('Content-Type', 'text/json')
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        if channel_info[7] == VOTE_SUBSCRIBE:
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": "you are already subscribed to this channel"})

        self.vote_for_channel(self.cid, VOTE_SUBSCRIBE)
        return json.dumps({"subscribed": True})

    def render_DELETE(self, request):
        """
        Unsubscribe from a specific channel. Returns error 404 if you are not subscribed to this channel.

        Example response:
        {
            "unsubscribed" : True
        }
        """
        request.setHeader('Content-Type', 'text/json')
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        if channel_info[7] != VOTE_SUBSCRIBE:
            return ChannelsModifySubscriptionEndpoint.return_404(request,
                                                                 message="you are not subscribed to this channel")

        self.vote_for_channel(self.cid, VOTE_UNSUBSCRIBE)
        return json.dumps({"unsubscribed": True})


class ChannelsDiscoveredEndpoint(BaseChannelsEndpoint):
    """
    A GET request to this endpoint returns all channels discovered in Tribler.

    Example GET response:
    {
        "channels": [{
            "id": 3,
            "dispersy_cid": "da69aaad39ccf468aba2ab9177d5f8d8160135e6",
            "name": "My fancy channel",
            "description": "A description of this fancy channel",
            "subscribed": False,
            "votes": 23,
            "torrents": 3,
            "spam": 5,
            "modified": 14598395,
        }, ...]
    }
    """

    def render_GET(self, request):
        all_channels_db = self.channel_db_handler.getAllChannels()
        results_json = [self.convert_db_channel_to_json(channel) for channel in all_channels_db]
        return json.dumps({"channels": results_json})
