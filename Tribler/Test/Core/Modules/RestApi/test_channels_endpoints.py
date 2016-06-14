import json
import time
from Tribler.Core.Modules.restapi.channels_endpoint import VOTE_SUBSCRIBE, VOTE_UNSUBSCRIBE

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_VOTECAST
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTestChannelsEndpoint(AbstractApiTest):

    def setUp(self, autoload_discovery=True):
        super(AbstractTestChannelsEndpoint, self).setUp(autoload_discovery)
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecast_db_handler = self.session.open_dbhandler(NTFY_VOTECAST)
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"

    def insert_channel_in_db(self, dispersy_cid, peer_id, name, description):
        return self.channel_db_handler.on_channel_from_dispersy(dispersy_cid, peer_id, name, description)

    def vote_for_channel(self, cid, vote_time):
        self.votecast_db_handler.on_votes_from_dispersy([[cid, None, 'random', 2, vote_time]])

    def insert_torrents_into_channel(self, torrent_list):
        self.channel_db_handler.on_torrents_from_dispersy(torrent_list)


class TestChannelsEndpoint(AbstractTestChannelsEndpoint):

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


class TestChannelTorrentsEndpoint(AbstractTestChannelsEndpoint):

    @deferred(timeout=10)
    def test_get_torrents_in_channel_invalid_cid(self):
        """
        Testing whether the API returns error 404 if a non-existent channel is queried for torrents
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/abcd/torrents', expected_code=404)

    @deferred(timeout=10)
    def test_get_torrents_in_channel(self):
        """
        Testing whether the API returns inserted torrents when fetching discovered channels
        """
        def verify_torrents(torrents):
            torrents_json = json.loads(torrents)
            self.assertEqual(len(torrents_json['torrents']), 1)
            self.assertEqual(torrents_json['torrents'][0]['infohash'], 'a' * 40)

        self.should_check_equality = False
        channel_id = self.insert_channel_in_db('rand', 42, 'Test channel', 'Test description')

        torrent_list = [[channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)

        return self.do_request('channels/discovered/%s/torrents' % 'rand'.encode('hex'), expected_code=200)\
            .addCallback(verify_torrents)


class TestChannelsSubscriptionEndpoint(AbstractTestChannelsEndpoint):

    def setUp(self, autoload_discovery=True):
        """
        The startup method of this class creates a fake Dispersy instance with a fake AllChannel community. It also
        inserts some random channels so we have some data to work with.
        """
        super(TestChannelsSubscriptionEndpoint, self).setUp(autoload_discovery)
        self.expected_votecast_cid = None
        self.expected_votecast_vote = None
        self.create_votecast_called = False

        self.session.get_dispersy = lambda: True
        self.session.lm.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.create_fake_allchannel_community()

        for i in xrange(0, 10):
            self.insert_channel_in_db('rand%d' % i, 42 + i, 'Test channel %d' % i, 'Test description %d' % i)

    def on_dispersy_create_votecast(self, cid, vote, _):
        """
        Check whether we have the expected parameters when this method is called.
        """
        self.assertEqual(cid, self.expected_votecast_cid)
        self.assertEqual(vote, self.expected_votecast_vote)
        self.create_votecast_called = True

    @blocking_call_on_reactor_thread
    def create_fake_allchannel_community(self):
        """
        This method creates a fake AllChannel community so we can check whether a request is made in the community
        when doing stuff with a channel.
        """
        self.session.lm.dispersy._database.open()
        fake_member = DummyMember(self.session.lm.dispersy, 1, "a" * 20)
        member = self.session.lm.dispersy.get_new_member(u"curve25519")
        fake_community = AllChannelCommunity(self.session.lm.dispersy, fake_member, member)
        fake_community.disp_create_votecast = self.on_dispersy_create_votecast
        self.session.lm.dispersy._communities = {"allchannel": fake_community}

    def tearDown(self):
        self.session.lm.dispersy = None
        super(TestChannelsSubscriptionEndpoint, self).tearDown()

    @deferred(timeout=10)
    def test_subscribe_channel_not_exist(self):
        """
        Testing whether the API returns an error when subscribing if the channel with the specified CID does not exist
        """
        return self.do_request('channels/subscribed/abcdef', expected_code=404, request_type='PUT')

    @deferred(timeout=10)
    def test_subscribe_channel_already_subscribed(self):
        """
        Testing whether the API returns error 409 when subscribing to an already subscribed channel
        """
        cid = self.insert_channel_in_db('rand1', 42, 'Test channel', 'Test description')
        self.vote_for_channel(cid, int(time.time()))

        return self.do_request('channels/subscribed/%s' % 'rand1'.encode('hex'), expected_code=409, request_type='PUT')

    @deferred(timeout=10)
    def test_subscribe_channel(self):
        """
        Testing whether the API creates a request in the AllChannel community when subscribing to a channel
        """
        def verify_votecast_made(_):
            self.assertTrue(self.create_votecast_called)

        expected_json = {"subscribed": True}
        self.expected_votecast_cid = 'rand1'
        self.expected_votecast_vote = VOTE_SUBSCRIBE
        return self.do_request('channels/subscribed/%s' % 'rand1'.encode('hex'), expected_code=200,
                               expected_json=expected_json, request_type='PUT').addCallback(verify_votecast_made)

    @deferred(timeout=10)
    def test_unsubscribe_channel_not_exist(self):
        """
        Testing whether the API returns an error when unsubscribing if the channel with the specified CID does not exist
        """
        return self.do_request('channels/subscribed/abcdef', expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_unsubscribe_channel_not_subscribed(self):
        """
        Testing whether the API returns error 404 when unsubscribing from an already unsubscribed channel
        """
        self.insert_channel_in_db('rand1', 42, 'Test channel', 'Test description')
        return self.do_request('channels/subscribed/%s' % 'rand1'.encode('hex'),
                               expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_unsubscribe_channel(self):
        """
        Testing whether the API creates a request in the AllChannel community when unsubscribing from a channel
        """
        def verify_votecast_made(_):
            self.assertTrue(self.create_votecast_called)

        cid = self.insert_channel_in_db('rand1', 42, 'Test channel', 'Test description')
        self.vote_for_channel(cid, int(time.time()))

        expected_json = {"unsubscribed": True}
        self.expected_votecast_cid = 'rand1'
        self.expected_votecast_vote = VOTE_UNSUBSCRIBE
        return self.do_request('channels/subscribed/%s' % 'rand1'.encode('hex'), expected_code=200,
                               expected_json=expected_json, request_type='DELETE').addCallback(verify_votecast_made)
