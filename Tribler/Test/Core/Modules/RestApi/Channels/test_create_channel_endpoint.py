import Tribler.Core.Utilities.json_util as json
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint
from Tribler.Test.tools import trial_timeout


class TestCreateChannelEndpoint(AbstractTestChannelsEndpoint):

    @trial_timeout(10)
    def test_my_channel_endpoint_create(self):
        """
        Testing whether the API returns the right JSON data if a channel is created
        """

        def verify_channel_created(body):
            channel_obj = self.session.lm.channel_manager._channel_list[0]
            self.assertEqual(channel_obj.name, post_data["name"])
            self.assertEqual(channel_obj.description, post_data["description"])
            self.assertEqual(channel_obj.mode, post_data["mode"])
            self.assertDictEqual(json.loads(body), {"added": channel_obj.channel_id})

        post_data = {
            "name": "John Smit's channel",
            "description": "Video's of my cat",
            "mode": "semi-open"
        }
        self.session.create_channel = self.create_fake_channel
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=200, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_channel_created)

    @trial_timeout(10)
    def test_my_channel_endpoint_create_default_mode(self):
        """
        Testing whether the API returns the right JSON data if a channel is created
         """

        def verify_channel_created(body):
            channel_obj = self.session.lm.channel_manager._channel_list[0]
            self.assertEqual(channel_obj.name, post_data["name"])
            self.assertEqual(channel_obj.description, post_data["description"])
            self.assertEqual(channel_obj.mode, u'closed')
            self.assertDictEqual(json.loads(body), {"added": channel_obj.channel_id})

        post_data = {
            "name": "John Smit's channel",
            "description": "Video's of my cat"
        }
        self.session.create_channel = self.create_fake_channel
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=200, expected_json=None,
                               request_type='PUT', post_data=post_data).addCallback(verify_channel_created)

    @trial_timeout(10)
    def test_my_channel_endpoint_create_duplicate_name_error(self):
        """
        Testing whether the API returns a formatted 500 error if DuplicateChannelNameError is raised
        """

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": True,
                    u"code": u"DuplicateChannelNameError",
                    u"message": u"Channel name already exists: %s" % post_data["name"]
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        post_data = {
            "name": "John Smit's channel",
            "description": "Video's of my cat",
            "mode": "semi-open"
        }
        self.session.create_channel = self.create_fake_channel_with_existing_name
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=500, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_error_message)

    @trial_timeout(10)
    def test_my_channel_endpoint_create_no_name_param(self):
        """
        Testing whether the API returns a 400 and error if the name parameter is not passed
        """
        post_data = {
            "description": "Video's of my cat",
            "mode": "semi-open"
        }
        expected_json = {"error": "channel name cannot be empty"}
        return self.do_request('channels/discovered', expected_code=400, expected_json=expected_json,
                               request_type='PUT', post_data=post_data)

    @trial_timeout(10)
    def test_my_channel_endpoint_create_no_description_param(self):
        """
        Testing whether the API returns the right JSON data if description parameter is not passed
        """
        def verify_channel_created(body):
            channel_obj = self.session.lm.channel_manager._channel_list[0]
            self.assertEqual(channel_obj.name, post_data["name"])
            self.assertEqual(channel_obj.description, u'')
            self.assertEqual(channel_obj.mode, post_data["mode"])
            self.assertDictEqual(json.loads(body), {"added": channel_obj.channel_id})

        post_data = {
            "name": "John Smit's channel",
            "mode": "semi-open"
        }
        self.session.create_channel = self.create_fake_channel
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=200, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_channel_created)
