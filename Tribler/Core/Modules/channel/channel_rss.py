from binascii import hexlify
import hashlib
import logging
import tempfile
import time

import feedparser
import os
import re
from twisted.web.client import getPage

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Modules.channel.cache import SimpleCache
from Tribler.Core.Utilities.twisted_thread import reactor

DEFAULT_CHECK_INTERVAL = 1800  # half an hour


class ChannelRssParser(TaskManager):

    def __init__(self, session, channel_community, rss_url, check_interval=DEFAULT_CHECK_INTERVAL):
        super(ChannelRssParser, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.channel_community = channel_community
        self.rss_url = rss_url
        self.check_interval = check_interval

        self._tmp_dir = None
        self._url_cache = None

        self._to_stop = False

    @blocking_call_on_reactor_thread
    def initialize(self):
        # initialize URL cache
        # use the SHA1 of channel cid + rss_url as key
        cache_key = hashlib.sha1(self.channel_community.cid)
        cache_key.update(self.rss_url)
        cache_key_str = hexlify(cache_key.digest())
        self._logger.debug(u"using key %s for channel %s, rss %s",
                           cache_key_str, hexlify(self.channel_community.cid), self.rss_url)

        url_cache_name = u"rss_cache_%s.txt" % cache_key_str
        url_cache_path = os.path.join(self.session.get_state_dir(), url_cache_name)
        self._url_cache = SimpleCache(url_cache_path)
        self._url_cache.load()

        # create temporary directory
        self._tmp_dir = tempfile.mkdtemp()

        # schedule the scraping task
        self.register_task(u"rss_scrape",
                           reactor.callLater(2, self._task_scrape))

    @blocking_call_on_reactor_thread
    def shutdown(self):
        self._to_stop = True
        self.cancel_all_pending_tasks()

        self._tmp_dir = None
        self._url_cache.save()
        self._url_cache = None

        self.channel_community = None
        self.session = None

    def _task_scrape(self):
        rss_parser = RSSFeedParser()

        for rss_item in rss_parser.parse(self.rss_url, self._url_cache):
            if self._to_stop:
                return
            torrent_deferred = getPage(rss_item[u'torrent_url'].encode('utf-8'))
            torrent_deferred.addCallback(lambda t, r=rss_item: self.on_got_torrent(t, rss_item=r))

        if not self._to_stop:
            # schedule the next scraping task
            self._logger.info(u"Finish scraping %s, schedule task after %s", self.rss_url, self.check_interval)
            self.register_task(u'rss_scrape',
                               reactor.callLater(self.check_interval, self._task_scrape))

    def on_got_torrent(self, torrent_data, rss_item=None):
        if self._to_stop:
            return

        # save torrent
        tdef = TorrentDef.load_from_memory(torrent_data)
        self.session.lm.rtorrent_handler.save_torrent(tdef)

        # create channel torrent
        self.channel_community._disp_create_torrent_from_torrentdef(tdef, long(time.time()))

        # update URL cache
        self._url_cache.add(rss_item[u'torrent_url'])
        self._url_cache.save()

        self._logger.info(u"Channel torrent %s created", tdef.get_name_as_unicode())


class RSSFeedParser(object):

    def _parse_html(self, content):
        """Parses an HTML content and find links.
        """
        if content is None:
            return None
        url_set = set()

        a_list = re.findall(r'<a.+href=[\'"]?([^\'" >]+)', content)
        for a_href in a_list:
            url_set.add(a_href)

        img_list = re.findall(r'<img.+src=[\'"]?([^\'" >]+)', content)
        for img_src in img_list:
            url_set.add(img_src)

        return url_set

    def _html2plaintext(self, html_content):
        """Converts an HTML document to plain text.
        """
        content = html_content.replace('\r\n', '\n')

        content = re.sub('<br[ \t\r\n\v\f]*.*/>', '\n', content)
        content = re.sub('<p[ \t\r\n\v\f]*.*/>', '\n', content)

        content = re.sub('<p>', '', content)
        content = re.sub('</p>', '\n', content)

        content = re.sub('<.+/>', '', content)
        content = re.sub('<.+>', '', content)
        content = re.sub('</.+>', '', content)

        content = re.sub('[\n]+', '\n', content)
        content = re.sub('[ \t\v\f]+', ' ', content)

        parsed_html_content = u''
        for line in content.split('\n'):
            trimed_line = line.strip()
            if trimed_line:
                parsed_html_content += trimed_line + u'\n'

        return parsed_html_content

    def parse(self, url, cache):
        """Parses a RSS feed. This methods supports RSS 2.0 and Media RSS.
        """
        feed = feedparser.parse(url)

        for item in feed.entries:
            # ignore the ones that we have seen before
            link = item.get(u'link', None)
            if link is None or cache.has(link):
                continue

            title = self._html2plaintext(item[u'title'])
            description = self._html2plaintext(item.get(u'media:description', u''))
            torrent_url = item[u'link']

            thumbnail_list = item.get(u'media:thumbnail', None)
            if thumbnail_list:
                for thumbnail in thumbnail_list:
                    thumbnail_list.append(thumbnail[u'url'])

            # assemble the information
            parsed_item = {u'title': title,
                           u'description': description,
                           u'torrent_url': torrent_url,
                           u'thumbnail_list': thumbnail_list}

            yield parsed_item
