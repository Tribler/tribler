from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.restapi.channels.my_channel_endpoint import NO_CHANNEL_CREATED_RESPONSE_MSG
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint, \
    AbstractTestChantEndpoint
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import trial_timeout


class TestMyChannelEndpoints(AbstractTestChannelsEndpoint):

    @trial_timeout(10)
    def test_my_channel_overview_endpoint_no_my_channel(self):
        """
        Testing whether the API returns response code 404 if no channel has been created
        """
        expected_json = {"error": NO_CHANNEL_CREATED_RESPONSE_MSG}
        return self.do_request('mychannel', expected_json=expected_json, expected_code=404)

    @trial_timeout(10)
    def test_my_channel_overview_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if a channel overview is requested
        """
        channel_json = {u'mychannel': {u'name': u'testname', u'description': u'testdescription',
                                       u'identifier': unicode('fakedispersyid'.encode('hex'))}}
        self.create_my_channel(channel_json[u'mychannel'][u'name'], channel_json[u'mychannel'][u'description'])

        return self.do_request('mychannel', expected_code=200, expected_json=channel_json)

    @trial_timeout(10)
    def test_edit_my_channel_no_channel(self):
        """
        Testing whether an error 404 is returned when trying to edit your non-existing channel
        """
        post_params = {'name': 'test'}
        return self.do_request('mychannel', expected_code=404, request_type='POST', post_data=post_params)

    @trial_timeout(10)
    def test_edit_my_channel_no_cmty(self):
        """
        Testing whether an error 404 is returned when trying to edit your channel without community
        """
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: None
        self.session.get_dispersy_instance = lambda: mock_dispersy

        self.create_my_channel('test', 'test')

        post_params = {'name': 'test'}
        return self.do_request('mychannel', expected_code=404, request_type='POST', post_data=post_params)

    @inlineCallbacks
    def test_edit_channel(self):
        """
        Testing whether a channel is correctly modified
        """
        self.create_my_channel('test', 'test')
        mock_channel_community = MockObject()
        mock_channel_community.called_modify = False

        def verify_channel_modified(_):
            self.assertTrue(mock_channel_community.called_modify)

        def modify_channel_called(modifications):
            self.assertEqual(modifications['name'], 'test1')
            self.assertEqual(modifications['description'], 'test2')
            mock_channel_community.called_modify = True

        mock_channel_community.modifyChannel = modify_channel_called
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        self.should_check_equality = False
        post_params = {'name': '', 'description': 'test2'}
        yield self.do_request('mychannel', expected_code=400, post_data=post_params, request_type='POST')

        self.should_check_equality = True
        post_params = {'name': 'test1', 'description': 'test2'}
        yield self.do_request('mychannel', expected_code=200, expected_json={"modified": True}, post_data=post_params,
                              request_type='POST').addCallback(verify_channel_modified)


class TestMyChannelChantEndpoints(AbstractTestChantEndpoint):

    @trial_timeout(10)
    def test_my_channel_overview_endpoint_no_my_channel(self):
        """
        Testing whether the API returns response code 404 if no chant channel has been created
        """
        expected_json = {"error": NO_CHANNEL_CREATED_RESPONSE_MSG}
        return self.do_request('mychannel', expected_json=expected_json, expected_code=404)

    @trial_timeout(10)
    def test_my_channel_overview_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if an existing chant channel overview is requested
        """
        channel_json = {u'mychannel': {u'name': u'testname', u'description': u'testdescription',
                                       u'identifier': self.session.trustchain_keypair.pub().key_to_bin().encode('hex')}}
        self.create_my_channel(channel_json[u'mychannel'][u'name'], channel_json[u'mychannel'][u'description'])

        return self.do_request('mychannel', expected_code=200, expected_json=channel_json)

    @trial_timeout(10)
    def test_edit_channel_not_exist(self):
        """
        Test whether the API returns error 404 when trying to edit a non-existing channel
        """
        post_params = {'name': 'new channel', 'description': 'new description'}
        self.should_check_equality = False
        return self.do_request('mychannel', request_type='POST', post_data=post_params, expected_code=404)

    @trial_timeout(10)
    def test_edit_channel(self):
        """
        Test editing your chant channel
        """
        self.create_my_channel('my channel', 'fancy description')
        self.add_random_torrent_to_my_channel()
        post_params = {'name': 'new channel', 'description': 'new description'}

        def verify_response(_):
            my_channel = self.get_my_channel()
            self.assertEqual(my_channel.title, 'new channel')
            self.assertEqual(my_channel.tags, 'new description')

        self.should_check_equality = False
        return self.do_request('mychannel', request_type='POST', post_data=post_params, expected_code=200)\
            .addCallback(verify_response)
