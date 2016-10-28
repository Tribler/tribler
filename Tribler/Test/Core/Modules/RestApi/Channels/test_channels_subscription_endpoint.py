import time

from twisted.internet.defer import inlineCallbacks, succeed

from Tribler.Core.Modules.restapi import VOTE_SUBSCRIBE, VOTE_UNSUBSCRIBE
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import UNKNOWN_CHANNEL_RESPONSE_MSG
from Tribler.Core.Modules.restapi.channels.channels_subscription_endpoint import ALREADY_SUBSCRIBED_RESPONSE_MSG, \
    NOT_SUBSCRIBED_RESPONSE_MSG
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread


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
        return succeed(None)

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

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.session.lm.dispersy = None
        yield super(TestChannelsSubscriptionEndpoint, self).tearDown(annotate=annotate)

    @deferred(timeout=10)
    def test_subscribe_channel_already_subscribed(self):
        """
        Testing whether the API returns error 409 when subscribing to an already subscribed channel
        """
        cid = self.insert_channel_in_db('rand1', 42, 'Test channel', 'Test description')
        self.vote_for_channel(cid, int(time.time()))
        expected_json = {"error": ALREADY_SUBSCRIBED_RESPONSE_MSG}

        return self.do_request('channels/subscribed/%s' % 'rand1'.encode('hex'),
                               expected_code=409, expected_json=expected_json, request_type='PUT')

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
        expected_json = {"error": UNKNOWN_CHANNEL_RESPONSE_MSG}
        return self.do_request('channels/subscribed/abcdef', expected_code=404, expected_json=expected_json,
                               request_type='DELETE')

    @deferred(timeout=10)
    def test_unsubscribe_channel_not_subscribed(self):
        """
        Testing whether the API returns error 404 when unsubscribing from an already unsubscribed channel
        """
        expected_json = {"error": NOT_SUBSCRIBED_RESPONSE_MSG}
        self.insert_channel_in_db('rand1', 42, 'Test channel', 'Test description')
        return self.do_request('channels/subscribed/%s' % 'rand1'.encode('hex'),
                               expected_code=404, expected_json=expected_json, request_type='DELETE')

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
        expected_json = {u'subscribed': [{u'description': u'This is a description', u'id': -1,
                                          u'dispersy_cid': unicode('rand'.encode('hex')),
                                          u'modified': int(time.time()),
                                          u'name': u'Test Channel', u'spam': 0,
                                          u'subscribed': True, u'torrents': 0, u'votes': 0}]}

        cid = self.insert_channel_in_db('rand', 42, expected_json[u'subscribed'][0][u'name'],
                                        expected_json[u'subscribed'][0][u'description'])
        expected_json[u'subscribed'][0][u'id'] = cid
        self.vote_for_channel(cid, expected_json[u'subscribed'][0][u'modified'])
        return self.do_request('channels/subscribed', expected_code=200, expected_json=expected_json)

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
