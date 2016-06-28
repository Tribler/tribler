import json
from twisted.web import http
from Tribler.Core.Modules.restapi import VOTE_SUBSCRIBE, VOTE_UNSUBSCRIBE
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_channel_to_json


ALREADY_SUBSCRIBED_RESPONSE_MSG = "you are already subscribed to this channel"
NOT_SUBSCRIBED_RESPONSE_MSG = "you are not subscribed to this channel"


class ChannelsSubscribedEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for requests regarding the subscriptions to channels.
    """
    def getChild(self, path, request):
        return ChannelsModifySubscriptionEndpoint(self.session, path)

    def render_GET(self, _):
        """
        .. http:get:: /channels/subscribed

        Returns all the channels the user is subscribed to.

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
        request.setHeader('Content-Type', 'text/json')
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        if channel_info[7] == VOTE_SUBSCRIBE:
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": ALREADY_SUBSCRIBED_RESPONSE_MSG})

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
        request.setHeader('Content-Type', 'text/json')
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        if channel_info[7] != VOTE_SUBSCRIBE:
            return ChannelsModifySubscriptionEndpoint.return_404(request, message=NOT_SUBSCRIBED_RESPONSE_MSG)

        self.vote_for_channel(self.cid, VOTE_UNSUBSCRIBE)
        return json.dumps({"unsubscribed": True})
