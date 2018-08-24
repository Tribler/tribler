from Tribler.Test.tools import trial_timeout
from twisted.internet.defer import inlineCallbacks

from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.message import Message
from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity


class TestAllChannelCommunity(AbstractTestCommunity):

    @inlineCallbacks
    def setUp(self):
        yield super(TestAllChannelCommunity, self).setUp()
        self.community = AllChannelCommunity(self.dispersy, self.master_member, self.member)
        self.dispersy._communities['a' * 20] = self.community
        self.community.initialize(auto_join_channel=True)

    @trial_timeout(10)
    def test_create_votecast(self):
        """
        Testing whether a votecast can be created in the community
        """
        def verify(message):
            self.assertTrue(isinstance(message, Message.Implementation))

        return self.community.disp_create_votecast("c" * 20, 2, 300).addCallback(verify)

    @trial_timeout(10)
    def test_unload_preview(self):
        """
        Test the unloading of the preview community
        """
        def verify_unloaded(_):
            self.assertEqual(len(self.dispersy.get_communities()), 1)

        preview_member = DummyMember(self.dispersy, 2, "c" * 20)
        preview_community = PreviewChannelCommunity(self.dispersy, preview_member, self.member)
        preview_community.initialize()
        preview_community.init_timestamp = -500
        self.dispersy._communities['c' * 20] = preview_community
        return self.community.unload_preview().addCallback(verify_unloaded)
