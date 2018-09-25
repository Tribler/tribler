import json

from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import UNKNOWN_CHANNEL_RESPONSE_MSG
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint, \
    AbstractTestChantEndpoint
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


class TestChannelsDiscoveredChantEndpoints(AbstractTestChantEndpoint):

    @trial_timeout(10)
    def test_get_discovered_chant_channel(self):
        """
        Test whether we successfully retrieve a discovered chant channel
        """
        def verify_response(response):
            json_response = json.loads(response)
            self.assertTrue(json_response['channels'])

        self.create_my_channel('test', 'test')
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=200).addCallback(verify_response)

    @trial_timeout(10)
    def test_create_my_channel(self):
        """
        Test whether we can create a new chant channel using the API
        """
        def verify_created(_):
            my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
            self.assertTrue(self.session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id))

        post_params = {'name': 'test1', 'description': 'test'}
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=200, expected_json={},
                               post_data=post_params, request_type='PUT').addCallback(verify_created)

    @trial_timeout(10)
    def test_create_my_channel_twice(self):
        """
        Test whether the API returns error 500 when we try to add a channel twice
        """
        self.create_my_channel('test', 'test2')
        post_params = {'name': 'test1', 'description': 'test'}
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=500, expected_json={},
                               post_data=post_params, request_type='PUT')
