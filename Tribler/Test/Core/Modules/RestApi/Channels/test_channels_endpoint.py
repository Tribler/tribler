from __future__ import absolute_import

import random

from pony.orm import db_session
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.metadata import NEW
from Tribler.Core.Modules.channel.channel import ChannelObject
from Tribler.Core.Modules.channel.channel_manager import ChannelManager
from Tribler.Core.exceptions import DuplicateChannelNameError
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test_channel import BaseTestChannel
from Tribler.Test.tools import trial_timeout
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


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


class AbstractTestChantEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(AbstractTestChantEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_chant_enabled(True)

    @db_session
    def create_my_channel(self, name, description):
        """
        Create your channel, with a given name and description.
        """
        return self.session.lm.mds.ChannelMetadata.create_channel(name, description)

    @db_session
    def add_random_torrent_to_my_channel(self, name=None):
        """
        Add a random torrent to your channel.
        """
        return self.session.lm.mds.TorrentMetadata(status=NEW, title='test' if not name else name,
                                                   infohash=database_blob(
                                                       bytearray(random.getrandbits(8) for _ in xrange(20))))

    @db_session
    def add_random_channel(self):
        """
        Add a random channel to the metadata store.
        :return: The metadata of the added channel.
        """
        rand_key = default_eccrypto.generate_key('low')
        new_channel = self.session.lm.mds.ChannelMetadata(
            sign_with=rand_key,
            public_key=database_blob(rand_key.pub().key_to_bin()), title='test', tags='test')
        new_channel.sign(rand_key)
        return new_channel

    @db_session
    def get_my_channel(self):
        """
        Return the metadata object of your channel, or None if it does not exist yet.
        """
        my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
        return self.session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id)


class AbstractTestChannelsEndpoint(AbstractApiTest, BaseTestChannel):

    @inlineCallbacks
    def setUp(self):
        yield super(AbstractTestChannelsEndpoint, self).setUp()
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

    @trial_timeout(10)
    def test_channels_unknown_endpoint(self):
        """
        Testing whether the API returns an error if an unknown endpoint is queried
        """
        self.should_check_equality = False
        return self.do_request('channels/thisendpointdoesnotexist123', expected_code=404)
