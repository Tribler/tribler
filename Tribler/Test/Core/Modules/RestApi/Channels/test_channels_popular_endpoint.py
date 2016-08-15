import json

from nose.twistedtools import deferred

from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint


class TestChannelsPlaylistEndpoints(AbstractTestChannelsEndpoint):

    @deferred(timeout=10)
    def test_popular_channels_endpoint(self):
        """
        Testing whether the API returns some popular channels if the are queried
        """
        def verify_channels(results):
            json_results = json.loads(results)
            self.assertEqual(len(json_results['channels']), 5)

        for i in xrange(0, 10):
            self.insert_channel_in_db('rand%d' % i, 42 + i, 'Test channel %d' % i, 'Test description %d' % i)

        self.should_check_equality = False
        return self.do_request('channels/popular?limit=5', expected_code=200).addCallback(verify_channels)

    @deferred(timeout=10)
    def test_popular_channels_limit_neg(self):
        """
        Testing whether error 400 is returned when a negative limit is passed to the request to fetch popular channels
        """
        expected_json = {"error": "the limit parameter must be a positive number"}
        return self.do_request('channels/popular?limit=-5', expected_code=400, expected_json=expected_json)
