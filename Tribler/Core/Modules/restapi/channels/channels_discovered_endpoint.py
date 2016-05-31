import json
from twisted.web import http
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.channels.channels_playlists_endpoint import ChannelsPlaylistsEndpoint
from Tribler.Core.Modules.restapi.channels.channels_rss_endpoint import ChannelsRssFeedsEndpoint, \
    ChannelsRecheckFeedsEndpoint
from Tribler.Core.Modules.restapi.channels.channels_torrents_endpoint import ChannelsTorrentsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_channel_to_json
from Tribler.Core.exceptions import DuplicateChannelNameError


class ChannelsDiscoveredEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for requests regarding the discovered channels.
    """
    def getChild(self, path, request):
        return ChannelsDiscoveredSpecificEndpoint(self.session, path)

    def render_GET(self, request):
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
        all_channels_db = self.channel_db_handler.getAllChannels()
        results_json = [convert_db_channel_to_json(channel) for channel in all_channels_db]
        return json.dumps({"channels": results_json})

    def render_PUT(self, request):
        """
        Create a new channel.

        Example request:
        {
            "name": "John Smit's channel",
            "description": "Video's of my cat",
            "mode": "open" or "semi-open" or "closed" (default)
        }
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if 'name' not in parameters or len(parameters['name']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "name parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "description parameter missing"})

        if 'mode' not in parameters or len(parameters['mode']) == 0:
            mode = u'closed'
        else:
            mode = parameters['mode'][0]

        try:
            channel_id = self.session.create_channel(parameters['name'][0], parameters['description'][0], mode)
        except DuplicateChannelNameError as ex:
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
            return json.dumps({
                u"error": {
                    u"handled": True,
                    u"code": ex.__class__.__name__,
                    u"message": ex.message
                }
            })

        return json.dumps({"added": channel_id})


class ChannelsDiscoveredSpecificEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for dispatching requests to perform operations in a specific discovered channel.
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = bytes(cid.decode('hex'))

        child_handler_dict = {"torrents": ChannelsTorrentsEndpoint, "rssfeeds": ChannelsRssFeedsEndpoint,
                              "playlists": ChannelsPlaylistsEndpoint, "recheckfeeds": ChannelsRecheckFeedsEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session, self.cid))

    def render_GET(self, request):
        """
        Return the name, description and identifier of a channel.

        Example response:
        {
            "overview": {
                "name": "A Tribler channel",
                "description": "A great collection of open-source movies",
                "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
            }
        }
        """
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsDiscoveredSpecificEndpoint.return_404(request)

        return json.dumps({'overview': {'identifier': channel_info[1].encode('hex'), 'name': channel_info[2],
                                        'description': channel_info[3]}})
