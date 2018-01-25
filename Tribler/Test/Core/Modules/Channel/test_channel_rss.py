import os
import shutil

from twisted.internet.defer import inlineCallbacks
from Tribler.Core.Modules.channel.cache import SimpleCache
from Tribler.Core.Modules.channel.channel_rss import ChannelRssParser, RSSFeedParser
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.Core.base_test_channel import BaseTestChannel
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.twisted_thread import deferred
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestChannelRss(BaseTestChannel):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True, autoload_discovery=True):
        """
        Setup the tests by creating the ChannelRssParser instance and initializing it.
        """
        yield super(TestChannelRss, self).setUp(annotate=annotate)
        self.channel_rss = ChannelRssParser(self.fake_session, self.fake_channel_community, 'a')
        self.channel_rss.initialize()

        # Setup a test rss file server
        test_rss_file = os.path.join(TESTS_DATA_DIR, 'test_rss.xml')
        files_path = os.path.join(self.session_base_dir, 'files')
        os.mkdir(files_path)
        shutil.copyfile(test_rss_file, os.path.join(files_path, 'test_rss.xml'))
        self.file_server_port = get_random_port()
        self.setUpFileServer(self.file_server_port, files_path)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        if self.channel_rss.running:
            self.channel_rss.shutdown()

        yield super(TestChannelRss, self).tearDown(annotate=annotate)

    @deferred(timeout=10)
    def test_task_scrape_no_stop(self):
        self.channel_rss.rss_url = 'http://localhost:%d/test_rss.xml' % self.file_server_port
        self.channel_rss.cancel_all_pending_tasks()
        test_deferred = self.channel_rss._task_scrape()
        self.assertTrue(self.channel_rss.is_pending_task_active("rss_scrape"))
        return test_deferred

    @deferred(timeout=10)
    def test_task_scrape_stop(self):
        self.channel_rss.rss_url = 'http://localhost:%d/test_rss.xml' % self.file_server_port
        self.channel_rss.cancel_all_pending_tasks()
        self.channel_rss._to_stop = True
        test_deferred = self.channel_rss._task_scrape()
        self.assertFalse(self.channel_rss.is_pending_task_active("rss_scrape"))
        return test_deferred

    def test_initialize(self):
        self.assertTrue(self.channel_rss.is_pending_task_active("rss_scrape"))

    def test_shutdown(self):
        cache_path = self.channel_rss._url_cache._file_path
        self.channel_rss._url_cache.add('a')
        self.channel_rss.shutdown()
        self.assertTrue(os.path.exists(cache_path))
        self.assertFalse(self.channel_rss.is_pending_task_active("rss_scrape"))

    @deferred(timeout=10)
    def test_parse_rss_feed(self):
        """
        Test parsing a rss feed
        """
        self.channel_rss.rss_url = 'http://localhost:%d/test_rss.xml' % self.file_server_port

        def verify_rss(items):
            self.assertEqual(len(items), 2)

        return self.channel_rss.parse_feed().addCallback(verify_rss)

    @deferred(timeout=10)
    def test_parse_no_rss(self):
        """
        Test parsing a non-rss feed
        """
        self.channel_rss.rss_url = 'http://localhost:%d/test_rsszz.xml' % self.file_server_port

        def verify_rss(items):
            self.assertIsNone(items)

        return self.channel_rss.parse_feed().addCallback(verify_rss)

    @deferred(timeout=10)
    def test_parse_feed_stopped(self):
        """
        Test whether items are not parsed anymore when the parse feeder is stopped
        """
        self.channel_rss.rss_url = 'http://localhost:%d/test_rss.xml' % self.file_server_port
        self.channel_rss._url_cache = SimpleCache(os.path.join(self.session_base_dir, 'cache.txt'))
        self.channel_rss._to_stop = True

        def verify_rss(items):
            self.assertEqual(len(items), 0)

        return self.channel_rss.parse_feed().addCallback(verify_rss)


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

    @deferred(timeout=10)
    def test_parse(self):
        test_rss_file = os.path.join(TESTS_DATA_DIR, 'test_rss.xml')
        files_path = os.path.join(self.session_base_dir, 'files')
        os.mkdir(files_path)
        shutil.copyfile(test_rss_file, os.path.join(files_path, 'test_rss.xml'))
        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        parser = RSSFeedParser()
        cache = SimpleCache(os.path.join(self.session_base_dir, 'cache.txt'))
        cache.add('http://localhost:RANDOMPORT/ubuntu.torrent')

        def on_items(rss_items):
            self.assertEqual(len(rss_items), 2)
            self.assertEqual(len(rss_items[0]['thumbnail_list']), 1)

        return parser.parse('http://localhost:%d/test_rss.xml' % file_server_port, cache).addCallback(on_items)
