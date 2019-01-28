from __future__ import absolute_import

from pony.orm import db_session
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi import VOTE_SUBSCRIBE, VOTE_UNSUBSCRIBE
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_channel_to_json, convert_chant_channel_to_json
from Tribler.pyipv8.ipv8.database import database_blob

ALREADY_SUBSCRIBED_RESPONSE_MSG = "you are already subscribed to this channel"
NOT_SUBSCRIBED_RESPONSE_MSG = "you are not subscribed to this channel"
CHANNEL_NOT_FOUND = "this channel is not found"


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
                        "can_edit": True,
                    }, ...]
                }
        """
        subscribed_channels_db = self.channel_db_handler.getMySubscribedChannels(include_dispersy=True)
        results_json = [convert_db_channel_to_json(channel) for channel in subscribed_channels_db]
        if self.session.config.get_chant_enabled():
            with db_session:
                channels_list = list(self.session.lm.mds.ChannelMetadata.select(lambda g: g.subscribed))
            results_json.extend([convert_chant_channel_to_json(channel) for channel in channels_list])
        return json.dumps({"subscribed": results_json})


class ChannelsModifySubscriptionEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for methods that modify the list of RSS feed URLs (adding/removing feeds).
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = bytes(cid.decode('hex'))

    def render_GET(self, request):
        """
        .. http:get:: /channels/subscribed/(string: channelid)

        Shows the status of subscription to a specific channel along with number of existing votes in the channel

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/subscribed/da69aaad39ccf468aba2ab9177d5f8d8160135e6

            **Example response**:

            .. sourcecode:: javascript

                {
                    "subscribed" : True, "votes": 111
                }
        """
        request.setHeader('Content-Type', 'text/json')
        channel_info = self.get_channel_from_db(self.cid)

        if channel_info is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        response = dict()
        response[u'subscribed'] = channel_info[7] == VOTE_SUBSCRIBE
        response[u'votes'] = channel_info[5]

        return json.dumps(response)

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

        if len(self.cid) == 74:
            with db_session:
                channel = self.session.lm.mds.ChannelMetadata.get(public_key=database_blob(self.cid))
                if not channel:
                    request.setResponseCode(http.NOT_FOUND)
                    return json.dumps({"error": CHANNEL_NOT_FOUND})

                if channel.subscribed:
                    request.setResponseCode(http.CONFLICT)
                    return json.dumps({"error": ALREADY_SUBSCRIBED_RESPONSE_MSG})
                channel.subscribed = True

            return json.dumps({"subscribed": True})

        channel_info = self.get_channel_from_db(self.cid)

        if channel_info is not None and channel_info[7] == VOTE_SUBSCRIBE:
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": ALREADY_SUBSCRIBED_RESPONSE_MSG})

        def on_vote_done(_):
            request.write(json.dumps({"subscribed": True}))
            request.finish()

        def on_vote_error(failure):
            request.processingFailed(failure)

        self.vote_for_channel(self.cid, VOTE_SUBSCRIBE).addCallback(on_vote_done).addErrback(on_vote_error)

        return NOT_DONE_YET

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

        if len(self.cid) == 74:
            with db_session:
                channel = self.session.lm.mds.ChannelMetadata.get(public_key=buffer(self.cid))
                if not channel:
                    return ChannelsModifySubscriptionEndpoint.return_404(request)
                elif not channel.subscribed:
                    return ChannelsModifySubscriptionEndpoint.return_404(request, message=NOT_SUBSCRIBED_RESPONSE_MSG)
                self.session.lm.remove_channel(channel)
            return json.dumps({"unsubscribed": True})

        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsModifySubscriptionEndpoint.return_404(request)

        if channel_info[7] != VOTE_SUBSCRIBE:
            return ChannelsModifySubscriptionEndpoint.return_404(request, message=NOT_SUBSCRIBED_RESPONSE_MSG)

        def on_vote_done(_):
            request.write(json.dumps({"unsubscribed": True}))
            request.finish()

        self.vote_for_channel(self.cid, VOTE_UNSUBSCRIBE).addCallback(on_vote_done)

        return NOT_DONE_YET
