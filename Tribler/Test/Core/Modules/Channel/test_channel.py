from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.channel.channel import ChannelObject
from Tribler.Core.Modules.channel.channel_rss import ChannelRssParser
from Tribler.Test.Core.base_test_channel import BaseTestChannel
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class TestChannel(BaseTestChannel):
    """
    This class contains some tests for the ChannelObject class.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True, autoload_discovery=True):
        """
        Setup the tests by creating the ChannelObject instance.
        """
        yield super(TestChannel, self).setUp(annotate=annotate, autoload_discovery=autoload_discovery)
        self.channel_object = ChannelObject(self.fake_session, self.fake_channel_community)

    def test_get_channel_id(self):
        self.assertEqual(self.channel_object.channel_id, 42)

    def test_get_channel_name(self):
        self.assertEqual(self.channel_object.name, "my fancy channel")

    def test_get_rss_feed_url_list(self):
        rss_parser = ChannelRssParser(self.fake_session, self.fake_channel_community, 'a')
        self.channel_object._rss_feed_dict['a'] = rss_parser
        self.assertEqual(self.channel_object.get_rss_feed_url_list(), ['a'])
