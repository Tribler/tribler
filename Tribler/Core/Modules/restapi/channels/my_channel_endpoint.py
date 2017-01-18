import json
from twisted.web import http
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import get_parameter


NO_CHANNEL_CREATED_RESPONSE_MSG = "your channel has not been created"


class MyChannelEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for managing requests regarding your channel.
    """

    def render_GET(self, request):
        """
        .. http:get:: /mychannel

        Return the name, description and identifier of your channel.
        This endpoint returns a 404 HTTP response if you have not created a channel (yet).

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/mychannel

            **Example response**:

            .. sourcecode:: javascript

                {
                    "overview": {
                        "name": "My Tribler channel",
                        "description": "A great collection of open-source movies",
                        "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
                    }
                }

            :statuscode 404: if your channel has not been created (yet).
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": NO_CHANNEL_CREATED_RESPONSE_MSG})

        my_channel = self.channel_db_handler.getChannel(my_channel_id)

        return json.dumps({'mychannel': {'identifier': my_channel[1].encode('hex'), 'name': my_channel[2],
                                         'description': my_channel[3]}})

    def render_POST(self, request):
        """
        .. http:post:: /mychannel

        Modify the name and/or the description of your channel.
        This endpoint returns a 404 HTTP response if you have not created a channel (yet).

            **Example request**:

            .. sourcecode:: none

                curl -X POST http://localhost:8085/mychannel
                --data "name=My fancy playlist&description=This playlist contains some random movies"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "modified": True
                }

            :statuscode 404: if your channel has not been created (yet).
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": NO_CHANNEL_CREATED_RESPONSE_MSG})

        channel_community = self.get_community_for_channel_id(my_channel_id)
        if channel_community is None:
            return BaseChannelsEndpoint.return_404(request,
                                                   message="the community for the your channel cannot be found")

        parameters = http.parse_qs(request.content.read(), 1)
        my_channel = self.channel_db_handler.getChannel(my_channel_id)

        if not get_parameter(parameters, 'name'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": 'channel name cannot be empty'})

        changes = {}
        if my_channel[2] != get_parameter(parameters, 'name'):
            changes['name'] = unicode(get_parameter(parameters, 'name'), 'utf-8')
        if my_channel[3] != get_parameter(parameters, 'description'):
            changes['description'] = unicode(get_parameter(parameters, 'description'), 'utf-8')

        channel_community.modifyChannel(changes)

        return json.dumps({'modified': True})
