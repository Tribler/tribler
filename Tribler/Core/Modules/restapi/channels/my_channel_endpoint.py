from twisted.web import http

from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import get_parameter
import Tribler.Core.Utilities.json_util as json
from Tribler.community.chant import chant

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

        my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
        my_channel = chant.get_channel_dict(my_channel_id)

        if my_channel is None:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": NO_CHANNEL_CREATED_RESPONSE_MSG})

        return json.dumps({'mychannel': {'identifier': my_channel["public_key"].encode('hex'),
                                         'name': my_channel["title"],
                                         'description': my_channel["tags"]}})

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
        key = self.session.trustchain_keypair
        my_channel_id = key.pub().key_to_bin()
        my_channel = chant.get_channel_dict(my_channel_id)

        channels_seeding_dir = os.path.join(self.session.config.get_state_dir(), "channels")

        #my_channel_id = self.channel_db_handler.getMyChannelId()
        #if my_channel_id is None:
        #    request.setResponseCode(http.NOT_FOUND)
        #   return json.dumps({"error": NO_CHANNEL_CREATED_RESPONSE_MSG})

        parameters = http.parse_qs(request.content.read(), 1)

        if not get_parameter(parameters, 'name'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": 'channel name cannot be empty'})

        changes = {}
        if my_channel[2] != get_parameter(parameters, 'name'):
            changes['name'] = unicode(get_parameter(parameters, 'name'), 'utf-8')
        if my_channel[3] != get_parameter(parameters, 'description'):
            changes['description'] = unicode(get_parameter(parameters, 'description'), 'utf-8')

        md_list = chant.get

        chant.create_channel(key, my_channel["title"], channels_seeding_dir,   )
        #channel_community.modifyChannel(changes)

        return json.dumps({'modified': True})
