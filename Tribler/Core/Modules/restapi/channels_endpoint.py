import json
import time

from twisted.web import http, resource

from Tribler.Core.Modules.restapi import VOTE_SUBSCRIBE, VOTE_UNSUBSCRIBE
from Tribler.Core.Modules.restapi.util import convert_db_channel_to_json, convert_db_torrent_to_json
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.community.allchannel.community import AllChannelCommunity


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
        .. http:get:: /channels/subscribed

        A GET request to this endpoint returns all the channels the user is subscribed to.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/subscribed

            **Example response**:

            .. sourcecode:: javascript

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
        results_json = [convert_db_channel_to_json(channel) for channel in subscribed_channels_db]
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
        .. http:put:: /channels/subscribed/(string: channelid)

        Subscribe to a specific channel. Returns error 409 if you are already subscribed to this channel.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/channels/subscribed/da69aaad39ccf468aba2ab9177d5f8d8160135e6

            **Example response**:

            .. sourcecode:: javascript

                {
                    "subscribed" : True
                }

            :statuscode 409: (conflict) if you are already subscribed to the specified channel.
        """
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
        .. http:delete:: /channels/subscribed/(string: channelid)

        Unsubscribe from a specific channel. Returns error 404 if you are not subscribed to this channel.

            **Example request**:

            .. sourcecode:: none

                curl -X DELETE http://localhost:8085/channels/subscribed/da69aaad39ccf468aba2ab9177d5f8d8160135e6

            **Example response**:

            .. sourcecode:: javascript

                {
                    "unsubscribed" : True
                }

            :statuscode 404: if you are not subscribed to the specified channel.
        """
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
    This class is responsible for requests regarding discovered channels.
    """
    def getChild(self, path, request):
        return ChannelsDiscoveredSpecificEndpoint(self.session, path)

    def render_GET(self, request):
        """
        .. http:get:: /channels/discovered

        A GET request to this endpoint returns all channels discovered in Tribler.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/discovered

            **Example response**:

            .. sourcecode:: javascript

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
        all_channels_db = self.channel_db_handler.getAllChannels()
        results_json = [convert_db_channel_to_json(channel) for channel in all_channels_db]
        return json.dumps({"channels": results_json})


class ChannelsDiscoveredSpecificEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for dispatching requests to perform operations in a specific discovered channel.
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)

        child_handler_dict = {"torrents": ChannelTorrentsEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session, bytes(cid.decode('hex'))))


class ChannelTorrentsEndpoint(BaseChannelsEndpoint):
    """
    This endpoint is responsible for managing torrents in a channel.
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid

    def render_GET(self, request):
        """
        .. http:get:: /channels/discovered/(string: channelid)/torrents

        A GET request to this endpoint returns all discovered torrents in a specific channel. The size of the torrent is
        in number of bytes. The last_tracker_check value will be 0 if we did not check the tracker state of the torrent
        yet.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/discovered/da69aaad39ccf468aba2ab9177d5f8d8160135e6/torrents

            **Example response**:

            .. sourcecode:: javascript

                {
                    "torrents": [{
                        "id": 4,
                        "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779",
                        "name": "Ubuntu-16.04-desktop-amd64",
                        "size": 8592385,
                        "category": "other",
                        "num_seeders": 42,
                        "num_leechers": 184,
                        "last_tracker_check": 1463176959
                    }, ...]
                }

            :statuscode 404: if the specified channel cannot be found.
        """
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelTorrentsEndpoint.return_404(request)

        torrent_db_columns = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length',
                              'Torrent.category', 'num_seeders', 'num_leechers', 'last_tracker_check']
        results_local_torrents_channel = self.channel_db_handler\
            .getTorrentsFromChannelId(channel_info[0], True, torrent_db_columns)

        results_json = [convert_db_torrent_to_json(torrent_result) for torrent_result in results_local_torrents_channel]
        return json.dumps({"torrents": results_json})
