from twisted.internet.defer import inlineCallbacks
from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTestChannelCommunity(AbstractTestCommunity):

    # We have to initialize Dispersy and the tunnel community on the reactor thread
    @blocking_call_on_reactor_thread
    def setUp(self):
        super(AbstractTestChannelCommunity, self).setUp()
        self.channel_community = ChannelCommunity(self.dispersy, self.master_member, self.member)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        # Don't unload_community() as it never got registered in dispersy on the first place.
        self.channel_community.cancel_all_pending_tasks()
        self.channel_community = None
        yield super(AbstractTestChannelCommunity, self).tearDown(annotate=annotate)
