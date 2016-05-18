import os
from twisted.internet.defer import DeferredList
from Tribler.Core.Modules.channel.cache import SimpleCache
from Tribler.Core.Modules.channel.channel_rss import ChannelRssParser, RSSFeedParser
from Tribler.Test.Core.Modules.Channel.base_test_channel import BaseTestChannel
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.test_as_server import TESTS_DATA_DIR


class TestChannelRss(BaseTestChannel):

    def setUp(self, annotate=True):
        """
        Setup the tests by creating the ChannelRssParser instance.
        """
        super(TestChannelRss, self).setUp(annotate=annotate)
        self.channel_rss = ChannelRssParser(self.fake_session, self.fake_channel_community, 'a')

    def test_task_scrape_no_stop(self):
        self.channel_rss._task_scrape()
        self.assertTrue(self.channel_rss.is_pending_task_active("rss_scrape"))

    def test_task_scrape_stop(self):
        self.channel_rss._to_stop = True
        self.channel_rss._task_scrape()
        self.assertFalse(self.channel_rss.is_pending_task_active("rss_scrape"))

    def test_initialize(self):
        self.channel_rss.initialize()
        self.assertTrue(self.channel_rss.is_pending_task_active("rss_scrape"))

    def test_shutdown(self):
        self.channel_rss.initialize()
        cache_path = self.channel_rss._url_cache._file_path
        self.channel_rss._url_cache.add('a')
        self.channel_rss.shutdown()
        self.assertTrue(os.path.exists(cache_path))
        self.assertFalse(self.channel_rss.is_pending_task_active("rss_scrape"))

    def test_parse_rss_feed(self):
        self.channel_rss.rss_url = os.path.join(TESTS_DATA_DIR, 'test_rss.xml')
        self.channel_rss._url_cache = SimpleCache(os.path.join(self.session_base_dir, 'cache.txt'))
        self.assertIsInstance(self.channel_rss.parse_feed(), DeferredList)

    def test_parse_feed_stopped(self):
        self.channel_rss.rss_url = os.path.join(TESTS_DATA_DIR, 'test_rss.xml')
        self.channel_rss._url_cache = SimpleCache(os.path.join(self.session_base_dir, 'cache.txt'))
        self.channel_rss._to_stop = True
        self.assertIsNone(self.channel_rss.parse_feed())


class TestRssParser(TriblerCoreTest):

    def test_parse_html(self):
        parser = RSSFeedParser()
        self.assertEqual(parser._parse_html("<p>Hi</p>"), set())
        self.assertEqual(parser._parse_html("<a href='abc'></a>"), {'abc'})
        self.assertEqual(parser._parse_html("<a href='abc'><img src='def'/></a>"), {'abc', 'def'})

    def test_html2plaintext(self):
        parser = RSSFeedParser()
        self.assertEqual(parser._html2plaintext("<p>test</p>"), "test\n")
        self.assertEqual(parser._html2plaintext("test"), "test\n")
        self.assertEqual(parser._html2plaintext("<p>test\ntest2</p><p>test3</p>"), "test\ntest2\ntest3\n")

    def test_parse(self):
        parser = RSSFeedParser()
        for rss_item in parser.parse(os.path.join(TESTS_DATA_DIR, 'test_rss.xml'),
                                     SimpleCache(os.path.join(self.session_base_dir, 'cache.txt'))):
            self.assertEqual(len(rss_item['thumbnail_list']), 1)
            self.assertEqual(rss_item['title'], "ubuntu-15.04-desktop-amd64.iso")
            self.assertEqual(rss_item['description'], '')
