from __future__ import absolute_import

from binascii import hexlify
import time

from pony.orm import db_session
import six
from six.moves import xrange
from twisted.internet.defer import succeed, fail, inlineCallbacks
from twisted.python.failure import Failure

from Tribler.Core.Modules.restapi import VOTE_SUBSCRIBE, VOTE_UNSUBSCRIBE
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import UNKNOWN_CHANNEL_RESPONSE_MSG
from Tribler.Core.Modules.restapi.channels.channels_subscription_endpoint import ALREADY_SUBSCRIBED_RESPONSE_MSG, \
    NOT_SUBSCRIBED_RESPONSE_MSG, ChannelsModifySubscriptionEndpoint
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint, \
    AbstractTestChantEndpoint
from Tribler.Test.tools import trial_timeout


class TestChannelsSubscriptionEndpoint(AbstractTestChannelsEndpoint):

    @inlineCallbacks
    def setUp(self):
        """
        The startup method of this class creates a fake Dispersy instance with a fake AllChannel community. It also
        inserts some random channels so we have some data to work with.
        """
        yield super(TestChannelsSubscriptionEndpoint, self).setUp()
        self.expected_votecast_cid = None
        self.expected_votecast_vote = None
        self.create_votecast_called = False

        fake_community = self.create_fake_allchannel_community()
        fake_community.disp_create_votecast = self.on_dispersy_create_votecast
        self.session.config.get_dispersy_enabled = lambda: True
        self.session.lm.dispersy.attach_community(fake_community)
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

    @trial_timeout(10)
    def test_subscribe_channel_already_subscribed(self):
        """
        Testing whether the API returns error 409 when subscribing to an already subscribed channel
        """
        cid = self.insert_channel_in_db('rand1', 42, 'Test channel', 'Test description')
        self.vote_for_channel(cid, int(time.time()))
        expected_json = {"error": ALREADY_SUBSCRIBED_RESPONSE_MSG}

        return self.do_request('channels/subscribed/%s' % hexlify(b'rand1'),
                               expected_code=409, expected_json=expected_json, request_type='PUT')

    @trial_timeout(10)
    def test_subscribe_channel(self):
        """
        Testing whether the API creates a request in the AllChannel community when subscribing to a channel
        """

        def verify_votecast_made(_):
            self.assertTrue(self.create_votecast_called)

        expected_json = {"subscribed": True}
        self.expected_votecast_cid = 'rand1'
        self.expected_votecast_vote = VOTE_SUBSCRIBE
        return self.do_request('channels/subscribed/%s' % hexlify(b'rand1'), expected_code=200,
                               expected_json=expected_json, request_type='PUT').addCallback(verify_votecast_made)

    @trial_timeout(10)
    def test_sub_channel_throw_error(self):
        """
        Testing whether an error is returned when we subscribe to a channel and an error pops up
        """

        def mocked_vote(*_):
            return fail(Failure(RuntimeError("error")))

        mod_sub_endpoint = ChannelsModifySubscriptionEndpoint(self.session, '')
        mod_sub_endpoint.vote_for_channel = mocked_vote
        subscribed_endpoint = self.session.lm.api_manager.root_endpoint.children['channels'].children["subscribed"]
        subscribed_endpoint.getChild = lambda *_: mod_sub_endpoint

        self.should_check_equality = False
        return self.do_request('channels/subscribed/', expected_code=500, request_type='PUT')

    @trial_timeout(10)
    def test_unsubscribe_channel_not_exist(self):
        """
        Testing whether the API returns an error when unsubscribing if the channel with the specified CID does not exist
        """
        expected_json = {"error": UNKNOWN_CHANNEL_RESPONSE_MSG}
        return self.do_request('channels/subscribed/abcdef', expected_code=404, expected_json=expected_json,
                               request_type='DELETE')

    @trial_timeout(10)
    def test_unsubscribe_channel_not_subscribed(self):
        """
        Testing whether the API returns error 404 when unsubscribing from an already unsubscribed channel
        """
        expected_json = {"error": NOT_SUBSCRIBED_RESPONSE_MSG}
        self.insert_channel_in_db('rand1', 42, 'Test channel', 'Test description')
        return self.do_request('channels/subscribed/%s' % hexlify(b'rand1'),
                               expected_code=404, expected_json=expected_json, request_type='DELETE')

    @trial_timeout(10)
    def test_get_subscribed_channels_no_subscriptions(self):
        """
        Testing whether the API returns no channels when you have not subscribed to any channel
        """
        expected_json = {"subscribed": []}
        return self.do_request('channels/subscribed', expected_code=200, expected_json=expected_json)

    @trial_timeout(10)
    def test_get_subscribed_channels_one_subscription(self):
        """
        Testing whether the API returns the right channel when subscribed to one channel
        """
        expected_json = {u'subscribed': [{u'description': u'This is a description', u'id': -1,
                                          u'dispersy_cid': six.text_type(hexlify(b'rand')),
                                          u'modified': int(time.time()),
                                          u'name': u'Test Channel', u'spam': 0,
                                          u'subscribed': True, u'torrents': 0, u'votes': 0}]}

        cid = self.insert_channel_in_db('rand', 42, expected_json[u'subscribed'][0][u'name'],
                                        expected_json[u'subscribed'][0][u'description'])
        expected_json[u'subscribed'][0][u'id'] = cid
        self.vote_for_channel(cid, expected_json[u'subscribed'][0][u'modified'])
        return self.do_request('channels/subscribed', expected_code=200, expected_json=expected_json)

    @trial_timeout(10)
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
        return self.do_request('channels/subscribed/%s' % hexlify(b'rand1'), expected_code=200,
                               expected_json=expected_json, request_type='DELETE').addCallback(verify_votecast_made)

    @trial_timeout(10)
    def test_is_channel_subscribed(self):
        """
        Testing the subscription status of channel
        """
        cid = self.insert_channel_in_db('rand1', 42, 'Test channel', 'Test description')
        self.vote_for_channel(cid, int(time.time()))

        expected_json = {"subscribed": True, "votes": 0}  # here votes represent previous dispersy votes which is zero
        return self.do_request('channels/subscribed/%s' % hexlify(b'rand1'), expected_code=200,
                               expected_json=expected_json, request_type='GET')

    @trial_timeout(10)
    def test_subscribed_status_of_non_existing_channel(self):
        """
        Testing the subscription status of non-existing channel
        """
        expected_json = {"error": UNKNOWN_CHANNEL_RESPONSE_MSG}
        return self.do_request('channels/subscribed/deadbeef', expected_code=404, expected_json=expected_json,
                               request_type='GET')


class TestChannelsSubscriptionChantEndpoint(AbstractTestChantEndpoint):

    @trial_timeout(10)
    def test_subscribe(self):
        """
        Test subscribing to a (random) chant channel with the API
        """
        random_channel = self.add_random_channel()
        random_channel_id = hexlify(random_channel.public_key)

        def verify_response(_):
            updated_channel = self.session.lm.mds.ChannelMetadata.get_channel_with_id(random_channel.public_key)
            self.assertTrue(updated_channel.subscribed)

        self.should_check_equality = False
        return self.do_request('channels/subscribed/%s' % random_channel_id, expected_code=200, request_type='PUT') \
            .addCallback(verify_response)

    @trial_timeout(10)
    def test_subscribe_twice(self):
        """
        Test whether an error is raised when subscribing to a channel we are already subscribed to
        """
        with db_session:
            random_channel = self.add_random_channel()
            random_channel.subscribed = True
            random_channel_id = hexlify(random_channel.public_key)

        self.should_check_equality = False
        return self.do_request('channels/subscribed/%s' % random_channel_id, expected_code=409, request_type='PUT')

    @trial_timeout(10)
    def test_subscribe_unknown_channel(self):
        """
        Test whether an error is raised when subscribing to an unknown channel
        """
        self.should_check_equality = False
        return self.do_request('channels/subscribed/aaaa', expected_code=404, request_type='PUT')

    @trial_timeout(10)
    def test_get_subscribed_channels_no_subscriptions(self):
        """
        Testing whether the API returns no channels when you have not subscribed to any channel
        """
        expected_json = {"subscribed": []}
        return self.do_request('channels/subscribed', expected_code=200, expected_json=expected_json)

    @trial_timeout(10)
    def test_get_subscribed_channels_one_subscription(self):
        """
        Testing whether the API returns the right channel when subscribed to one channel
        """
        with db_session:
            md = self.session.lm.mds.ChannelMetadata(title="Test channel", subscribed=True)
            title = md.title
            cid = hexlify(md.public_key)
            version = md.version
            subscribed = md.subscribed
            torrents = md.size
            votes = md.votes
            tags = md.tags
        expected_json = {u'subscribed': [{u'description': six.text_type(tags), u'id': 0,
                                          u'dispersy_cid': six.text_type(cid),
                                          u'modified': version,
                                          u'name': six.text_type(title), u'spam': 0,
                                          u'subscribed': subscribed, u'torrents': torrents, u'votes': votes}]}

        return self.do_request('channels/subscribed', expected_code=200, expected_json=expected_json)
