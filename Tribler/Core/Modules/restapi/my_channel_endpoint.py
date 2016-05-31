import json
from twisted.web import http, resource
from Tribler.Core.simpledefs import NTFY_CHANNELCAST


NO_CHANNEL_CREATED_RESPONSE_MSG = "your channel has not been created"


class MyChannelEndpoint(resource.Resource):
    """
    A GET request to this endpoint will return information about your own channel in Tribler.

    Example GET response:
    {
        "mychannel": {
            "name": "A Tribler channel",
            "description": "A great collection of open-source movies",
            "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
        }
    }
    """
    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def render_GET(self, request):
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": NO_CHANNEL_CREATED_RESPONSE_MSG})

        my_channel = self.channel_db_handler.getChannel(my_channel_id)
        return json.dumps({'mychannel': {'identifier': my_channel[1].encode('hex'), 'name': my_channel[2],
                                         'description': my_channel[3]}})
