import json
from twisted.web import http
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_channel_to_json


class ChannelsPopularEndpoint(BaseChannelsEndpoint):

    def render_GET(self, request):
        """
        .. http:get:: /channels/popular?limit=(int:max nr of channels)

        A GET request to this endpoint will return the most popular discovered channels in Tribler.
        You can optionally pass a limit parameter to limit the number of results.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/popular?limit=1

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
                        "can_edit": True,
                    }]
                }
        """
        limit_channels = 10

        if 'limit' in request.args and len(request.args['limit']) > 0:
            limit_channels = int(request.args['limit'][0])

            if limit_channels <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "the limit parameter must be a positive number"})

        popular_channels = self.channel_db_handler.getMostPopularChannels(max_nr=limit_channels)
        results_json = []
        for channel in popular_channels:
            channel_json = convert_db_channel_to_json(channel)
            if self.session.tribler_config.get_family_filter_enabled() and \
                    self.session.lm.category.xxx_filter.isXXX(channel_json['name']):
                continue

            results_json.append(channel_json)

        return json.dumps({"channels": results_json})
