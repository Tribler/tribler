import hashlib
import logging
import os
import re
import time
from binascii import hexlify

import feedparser
from twisted.internet import reactor
from twisted.internet.defer import DeferredList, succeed
from twisted.web.client import getPage

from Tribler.Core.Modules.channel.cache import SimpleCache
from Tribler.Core.TorrentDef import TorrentDef
import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Utilities.utilities import http_get
from Tribler.Core.simpledefs import (SIGNAL_CHANNEL_COMMUNITY, SIGNAL_ON_TORRENT_UPDATED, SIGNAL_RSS_FEED,
                                     SIGNAL_ON_UPDATED)
from Tribler.pyipv8.ipv8.taskmanager import TaskManager
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread

DEFAULT_CHECK_INTERVAL = 1800  # half an hour


class ChannelRssParser(TaskManager):

    def __init__(self, session, channel_community, rss_url, check_interval=DEFAULT_CHECK_INTERVAL):
        super(ChannelRssParser, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.channel_community = channel_community
        self.rss_url = rss_url
        self.check_interval = check_interval

        self._url_cache = None

        self._pending_metadata_requests = {}

        self._to_stop = False

        self.running = False

    def initialize(self):
        # initialize URL cache
        # use the SHA1 of channel cid + rss_url as key
        cache_key = hashlib.sha1(self.channel_community.cid)
        cache_key.update(self.rss_url)
        cache_key_str = hexlify(cache_key.digest())
        self._logger.debug(u"using key %s for channel %s, rss %s",
                           cache_key_str, hexlify(self.channel_community.cid), self.rss_url)

        url_cache_name = u"rss_cache_%s.txt" % cache_key_str
        url_cache_path = os.path.join(self.session.config.get_state_dir(), url_cache_name)
        self._url_cache = SimpleCache(url_cache_path)
        self._url_cache.load()

        # schedule the scraping task
        self.register_task(u"rss_scrape",
                           reactor.callLater(2, self._task_scrape))

        # subscribe to channel torrent creation
        self.session.notifier.add_observer(self.on_channel_torrent_created, SIGNAL_CHANNEL_COMMUNITY,
                                           [SIGNAL_ON_TORRENT_UPDATED], self.channel_community.get_channel_id())

        # notify that a RSS feed has been created
        rss_feed_data = {u'channel': self.channel_community,
                         u'rss_feed_url': self.rss_url}
        self.session.notifier.notify(SIGNAL_RSS_FEED, SIGNAL_ON_UPDATED, None, rss_feed_data)
        self.running = True

    def shutdown(self):
        self._to_stop = True
        self.shutdown_task_manager()

        self._url_cache.save()
        self._url_cache = None

        self.channel_community = None
        self.session = None
        self.running = False

    def parse_feed(self):
        rss_parser = RSSFeedParser()

        def on_rss_items(rss_items):
            if not rss_items:
                self._logger.warning(u"No RSS items found.")
                return succeed(None)

            def_list = []
            for rss_item in rss_items:
                if self._to_stop:
                    continue

                torrent_url = rss_item[u'torrent_url'].encode('utf-8')
                if torrent_url.startswith('magnet:'):
                    self._logger.warning(u"Tribler does not support adding magnet links to a channel from a RSS feed.")
                    continue

                torrent_deferred = getPage(torrent_url)
                torrent_deferred.addCallbacks(lambda t, r=rss_item: self.on_got_torrent(t, rss_item=r),
                                              self.on_got_torrent_error)
                def_list.append(torrent_deferred)

            return DeferredList(def_list, consumeErrors=True)

        return rss_parser.parse(self.rss_url, self._url_cache).addCallback(on_rss_items)

    def _task_scrape(self):
        deferred = self.parse_feed()

        if not self._to_stop:
            # schedule the next scraping task
            self._logger.info(u"Finish scraping %s, schedule task after %s", self.rss_url, self.check_interval)
            self.register_task(u'rss_scrape',
                               reactor.callLater(self.check_interval, self._task_scrape))

        return deferred

    def on_got_torrent(self, torrent_data, rss_item=None):
        if self._to_stop:
            return

        # save torrent
        tdef = TorrentDef.load_from_memory(torrent_data)
        self.session.lm.rtorrent_handler.save_torrent(tdef)

        # add metadata pending request
        info_hash = tdef.get_infohash()
        if u'thumbnail_list' in rss_item and rss_item[u'thumbnail_list']:
            # only use the first thumbnail
            rss_item[u'thumbnail_url'] = rss_item[u'thumbnail_list'][0]
            if info_hash not in self._pending_metadata_requests:
                self._pending_metadata_requests[info_hash] = rss_item

        # create channel torrent
        self.channel_community._disp_create_torrent_from_torrentdef(tdef, long(time.time()))

        # update URL cache
        self._url_cache.add(rss_item[u'torrent_url'])
        self._url_cache.save()

        self._logger.info(u"Channel torrent %s created", tdef.get_name_as_unicode())

    def on_got_torrent_error(self, failure):
        """
        This callback is invoked when the lookup for a specific torrent failed.
        """
        self._logger.warning(u"Failed to fetch torrent info from RSS feed: %s", failure)

    def on_channel_torrent_created(self, subject, events, object_id, data_list):
        if self._to_stop:
            return

        for data in data_list:
            if data[u'info_hash'] in self._pending_metadata_requests:
                rss_item = self._pending_metadata_requests.pop(data[u'info_hash'])
                rss_item[u'info_hash'] = data[u'info_hash']
                rss_item[u'channel_torrent_id'] = data[u'channel_torrent_id']

                metadata_deferred = getPage(rss_item[u'thumbnail_url'].encode('utf-8'))
                metadata_deferred.addCallback(lambda md, r=rss_item: self.on_got_metadata(md, rss_item=r))

    def on_got_metadata(self, metadata_data, rss_item=None):
        # save metadata
        thumb_hash = hashlib.sha1(metadata_data).digest()
        self.session.lm.rtorrent_handler.save_metadata(thumb_hash, metadata_data)

        # create modification message for channel
        modifications = {u'metadata-json': json.dumps({u'title': rss_item['title'][:64],
                                                       u'description': rss_item['description'][:768],
                                                       u'thumb_hash': thumb_hash.encode('hex')})}
        self.channel_community.modifyTorrent(rss_item[u'channel_torrent_id'], modifications)


class RSSFeedParser(object):

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    def _parse_html(self, content):
        """
        Parses an HTML content and find links.
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
        """
        Converts an HTML document to plain text.
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
            trimmed_line = line.strip()
            if trimmed_line:
                parsed_html_content += trimmed_line + u'\n'

        return parsed_html_content

    def parse(self, url, cache):
        """
        Parses a RSS feed. This methods supports RSS 2.0 and Media RSS.
        """
        def on_rss_response(response):
            feed = feedparser.parse(response)
            feed_items = []

            for item in feed.entries:
                # ignore the ones that we have seen before
                link = item.get(u'link', None)
                if link is None or cache.has(link):
                    continue

                title = self._html2plaintext(item[u'title']).strip()
                description = self._html2plaintext(item.get(u'media_description', u'')).strip()
                torrent_url = item[u'link']

                thumbnail_list = []
                media_thumbnail_list = item.get(u'media_thumbnail', None)
                if media_thumbnail_list:
                    for thumbnail in media_thumbnail_list:
                        thumbnail_list.append(thumbnail[u'url'])

                # assemble the information
                parsed_item = {u'title': title,
                               u'description': description,
                               u'torrent_url': torrent_url,
                               u'thumbnail_list': thumbnail_list}

                feed_items.append(parsed_item)

            return feed_items

        def on_rss_error(failure):
            self._logger.error("Error when fetching RSS feed: %s", failure)

        return http_get(str(url)).addCallbacks(on_rss_response, on_rss_error)
