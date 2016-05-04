import json
import time

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_VOTECAST
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestChannelsEndpoint(AbstractApiTest):

    def setUp(self, autoload_discovery=True):
        super(TestChannelsEndpoint, self).setUp(autoload_discovery)
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecast_db_handler = self.session.open_dbhandler(NTFY_VOTECAST)
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"

    def insert_channel_in_db(self, dispersy_cid, peer_id, name, description):
        return self.channel_db_handler.on_channel_from_dispersy(dispersy_cid, peer_id, name, description)

    def vote_for_channel(self, cid, vote_time):
        self.votecast_db_handler.on_votes_from_dispersy([[cid, None, 'random', 2, vote_time]])

    @deferred(timeout=10)
    def test_channels_unknown_endpoint(self):
        """
        Testing whether the API returns an error if an unknown endpoint is queried
        """
        self.should_check_equality = False
        return self.do_request('channels/thisendpointdoesnotexist123', expected_code=404)

    @deferred(timeout=10)
    def test_get_subscribed_channels_no_subscriptions(self):
        """
        Testing whether the API returns no channels when you have not subscribed to any channel
        """
        expected_json = {"subscribed": []}
        return self.do_request('channels/subscribed', expected_code=200, expected_json=expected_json)

    @deferred(timeout=10)
    def test_get_subscribed_channels_one_subscription(self):
        """
        Testing whether the API returns the right channel when subscribed to one channel
        """
        expected_json = {u'subscribed': [{u'description': u'This is a description', u'id': 1,
                                          u'dispersy_cid': 'rand'.encode('hex'), u'modified': int(time.time()),
                                          u'name': u'Test Channel', u'spam': 0,
                                          u'subscribed': True, u'torrents': 0, u'votes': 0}]}

        cid = self.insert_channel_in_db('rand', 42, expected_json[u'subscribed'][0][u'name'],
                                        expected_json[u'subscribed'][0][u'description'])
        self.vote_for_channel(cid, expected_json[u'subscribed'][0][u'modified'])
        return self.do_request('channels/subscribed', expected_code=200, expected_json=expected_json)

    @deferred(timeout=10)
    def test_get_discovered_channels_no_channels(self):
        """
        Testing whether the API returns no channels when fetching discovered channels
        and there are no channels in the database
        """
        expected_json = {u'channels': []}
        return self.do_request('channels/discovered', expected_code=200, expected_json=expected_json)

    def verify_channels(self, channels):
        channels_json = json.loads(channels)
        self.assertEqual(len(channels_json['channels']), 10)
        for i in range(len(channels_json['channels'])):
            self.assertEqual(channels_json['channels'][i]['name'], 'Test channel %d' % i)
            self.assertEqual(channels_json['channels'][i]['description'], 'Test description %d' % i)

    @deferred(timeout=10)
    def test_get_discovered_channels(self):
        """
        Testing whether the API returns inserted channels when fetching discovered channels
        """
        self.should_check_equality = False
        for i in range(0, 10):
            self.insert_channel_in_db('rand%d' % i, 42 + i, 'Test channel %d' % i, 'Test description %d' % i)

        return self.do_request('channels/discovered', expected_code=200).addCallback(self.verify_channels)
