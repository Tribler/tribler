from Tribler.Test.Community.channel.test_channel_base import AbstractTestChannelCommunity
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestChannelCommunity(AbstractTestChannelCommunity):

    @blocking_call_on_reactor_thread
    def test_initialize(self):
        def raise_runtime():
            raise RuntimeError()
        self.channel_community._get_latest_channel_message = raise_runtime
        self.channel_community.initialize()
        self.assertIsNone(self.channel_community._channelcast_db)

