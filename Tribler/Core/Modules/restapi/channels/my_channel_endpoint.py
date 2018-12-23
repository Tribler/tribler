from __future__ import absolute_import
import os
from binascii import hexlify

from pony.orm import db_session
from twisted.web import http

import Tribler.Core.Utilities.json_util as json
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
        my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id)

            if not my_channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": NO_CHANNEL_CREATED_RESPONSE_MSG})

            my_channel = my_channel.to_dict()
        return json.dumps({
            'mychannel': {
                'identifier': hexlify(str(my_channel["public_key"])),
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
        parameters = http.parse_qs(request.content.read(), 1)

        if not get_parameter(parameters, 'name') and not get_parameter(parameters, 'commit_changes'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": 'channel name cannot be empty'})

        with db_session:
            modified = False
            my_key = self.session.trustchain_keypair
            my_channel_id = my_key.pub().key_to_bin()
            my_channel = self.session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id)

            if not my_channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": NO_CHANNEL_CREATED_RESPONSE_MSG})

            if get_parameter(parameters, 'name'):
                my_channel.update_metadata(update_dict={
                    "tags": str(get_parameter(parameters, 'description')).encode('utf-8'),
                    "title": str(get_parameter(parameters, 'name')).encode('utf-8')
                })
                modified = True

            if get_parameter(parameters, 'commit_changes') and my_channel.staged_entries_list:
                # Update torrent if we have uncommitted content in the channel
                my_channel.commit_channel_torrent()
                torrent_path = os.path.join(self.session.lm.mds.channels_dir, my_channel.dir_name + ".torrent")
                self.session.lm.gigachannel_manager.updated_my_channel(torrent_path)
                modified = True

            return json.dumps({'modified': modified})
