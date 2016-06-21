from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTestChannelCommunity(AbstractTestCommunity):

    # We have to initialize Dispersy and the tunnel community on the reactor thread
    @blocking_call_on_reactor_thread
    def setUp(self):
        super(AbstractTestChannelCommunity, self).setUp()
        self.channel_community = ChannelCommunity(self.dispersy, self.master_member, self.member)
