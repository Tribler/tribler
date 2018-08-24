from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import UNKNOWN_CHANNEL_RESPONSE_MSG
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint
from Tribler.Test.tools import trial_timeout


class TestChannelsDiscoveredEndpoints(AbstractTestChannelsEndpoint):

    @trial_timeout(10)
    def test_get_channel_info_non_existent(self):
        """
        Testing whether the API returns error 404 if an unknown channel is queried
        """
        self.should_check_equality = True
        expected_json = {"error": UNKNOWN_CHANNEL_RESPONSE_MSG}
        return self.do_request('channels/discovered/aabb', expected_code=404, expected_json=expected_json)

    @trial_timeout(10)
    def test_get_channel_info(self):
        """
        Testing whether the API returns the right JSON data if a channel overview is requested
        """
        channel_json = {u'overview': {u'name': u'testname', u'description': u'testdescription',
                                      u'identifier': unicode('fake'.encode('hex'))}}
        self.insert_channel_in_db('fake', 3, channel_json[u'overview'][u'name'],
                                  channel_json[u'overview'][u'description'])

        return self.do_request('channels/discovered/%s' % 'fake'.encode('hex'), expected_code=200,
                               expected_json=channel_json)
