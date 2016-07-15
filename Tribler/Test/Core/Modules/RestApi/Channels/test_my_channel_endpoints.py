from Tribler.Core.Modules.restapi.channels.my_channel_endpoint import NO_CHANNEL_CREATED_RESPONSE_MSG
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint


class TestMyChannelEndpoints(AbstractTestChannelsEndpoint):

    @deferred(timeout=10)
    def test_my_channel_overview_endpoint_no_my_channel(self):
        """
        Testing whether the API returns response code 404 if no channel has been created
        """
        expected_json = {"error": NO_CHANNEL_CREATED_RESPONSE_MSG}
        return self.do_request('mychannel', expected_json=expected_json, expected_code=404)

    @deferred(timeout=10)
    def test_my_channel_overview_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if a channel overview is requested
        """
        channel_json = {u'mychannel': {u'name': u'testname', u'description': u'testdescription',
                                       u'identifier': unicode('fakedispersyid'.encode('hex'))}}
        self.create_my_channel(channel_json[u'mychannel'][u'name'], channel_json[u'mychannel'][u'description'])

        return self.do_request('mychannel', expected_code=200, expected_json=channel_json)
