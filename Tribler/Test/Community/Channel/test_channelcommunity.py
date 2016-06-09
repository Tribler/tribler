from Tribler.Test.Community.Channel.test_channel_base import AbstractTestChannelCommunity
from Tribler.dispersy.exception import MetaNotFoundException
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTunnelCommunity(AbstractTestChannelCommunity):

    def raiseRuntimeErorr(self):
        raise RuntimeError("Unit-testing")

    def raiseMetaNotFoundException(self):
        raise MetaNotFoundException("Unit-testing")

    @blocking_call_on_reactor_thread
    def test_initialize_error_runtimeError(self):
        """
        Tests whether the channel community can handle the _get_latest_channel_message throwing
        a RuntimeError.
        """
        self.channel_community._get_latest_channel_message = self.raiseRuntimeErorr
        self.channel_community.initialize()

    @blocking_call_on_reactor_thread
    def test_initialize_error_metanotfoundexception(self):
        """
        Tests whether the channel community can handle the _get_latest_channel_message throwing
        a raiseMetaNotFoundException
        """
        self.channel_community._get_latest_channel_message = self.raiseMetaNotFoundException
        self.channel_community.initialize()

    @blocking_call_on_reactor_thread
    def test_initialize_runs_ok(self):
        """
        Tests whether the channel community can initialize fine without a Tribler session.
        """
        self.channel_community.initialize()


    def test_dispersy_sync_response_limit(self):
        self.assertEqual(self.channel_community.dispersy_sync_response_limit, 25 * 1024)

    def test_get_channel_id_none(self):
        self.assertIsNone(self.channel_community.get_channel_id())
