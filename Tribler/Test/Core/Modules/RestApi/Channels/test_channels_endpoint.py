import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.channel.channel import ChannelObject
from Tribler.Core.Modules.channel.channel_manager import ChannelManager
from Tribler.Core.exceptions import DuplicateChannelNameError
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test_channel import BaseTestChannel
from Tribler.Test.twisted_thread import deferred


class ChannelCommunityMock(object):

    def __init__(self, channel_id, name, description, mode):
        self.cid = 'a' * 20
        self._channel_id = channel_id
        self._channel_name = name
        self._channel_description = description
        self._channel_mode = mode

    def get_channel_id(self):
        return self._channel_id

    def get_channel_name(self):
        return self._channel_name

    def get_channel_description(self):
        return self._channel_description

    def get_channel_mode(self):
        return self._channel_mode


class AbstractTestChannelsEndpoint(AbstractApiTest, BaseTestChannel):

    def setUp(self, autoload_discovery=True):
        super(AbstractTestChannelsEndpoint, self).setUp(autoload_discovery)
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"

    def vote_for_channel(self, cid, vote_time):
        self.votecast_db_handler.on_votes_from_dispersy([[cid, None, 'random', 2, vote_time]])

    def create_my_channel(self, name, description):
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"
        self.channel_db_handler.on_channel_from_dispersy('fakedispersyid', None, name, description)
        return self.channel_db_handler.getMyChannelId()

    def create_fake_channel(self, name, description, mode=u'closed'):
        # Use a fake ChannelCommunity object (we don't actually want to create a Dispersy community)
        my_channel_id = self.create_my_channel(name, description)
        self.session.lm.channel_manager = ChannelManager(self.session)

        channel_obj = ChannelObject(self.session, ChannelCommunityMock(my_channel_id, name, description, mode))
        self.session.lm.channel_manager._channel_list.append(channel_obj)
        return my_channel_id

    def create_fake_channel_with_existing_name(self, name, description, mode=u'closed'):
        raise DuplicateChannelNameError(u"Channel name already exists: %s" % name)


class TestChannelsEndpoint(AbstractTestChannelsEndpoint):

    @deferred(timeout=10)
    def test_channels_unknown_endpoint(self):
        """
        Testing whether the API returns an error if an unknown endpoint is queried
        """
        self.should_check_equality = False
        return self.do_request('channels/thisendpointdoesnotexist123', expected_code=404)

    @deferred(timeout=10)
    def test_get_discovered_channels_no_channels(self):
        """
        Testing whether the API returns no channels when fetching discovered channels
        and there are no channels in the database
        """
        expected_json = {u'channels': []}
        return self.do_request('channels/discovered', expected_code=200, expected_json=expected_json)

    @deferred(timeout=10)
    def test_get_discovered_channels(self):
        """
        Testing whether the API returns inserted channels when fetching discovered channels
        """
        self.should_check_equality = False
        for i in xrange(0, 10):
            self.insert_channel_in_db('rand%d' % i, 42 + i, 'Test channel %d' % i, 'Test description %d' % i)
        self.insert_channel_in_db('randbad', 100, 'badterm', 'Test description bad')

        def verify_channels(channels):
            channels_json = json.loads(channels)['channels']
            self.assertEqual(len(channels_json), 10)
            channels_json = sorted(channels_json, key=lambda channel: channel['name'])
            for ind in xrange(len(channels_json)):
                self.assertEqual(channels_json[ind]['name'], 'Test channel %d' % ind)

        return self.do_request('channels/discovered', expected_code=200).addCallback(verify_channels)
