import codecs
import collections
import logging
import os
from binascii import hexlify
from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from Tribler.Core.Modules.channel.channel_rss import ChannelRssParser
import Tribler.Core.Utilities.json_util as json
from Tribler.Core.simpledefs import SIGNAL_CHANNEL, SIGNAL_ON_CREATED, SIGNAL_RSS_FEED, SIGNAL_ON_UPDATED
from Tribler.pyipv8.ipv8.taskmanager import TaskManager
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class ChannelObject(TaskManager):

    def __init__(self, session, channel_community, is_created=False):
        super(ChannelObject, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self._session = session
        self._channel_community = channel_community
        self._is_created = is_created
        self._rss_feed_dict = collections.OrderedDict()

        rss_name = u"channel_rss_%s.json" % hexlify(self._channel_community.cid)
        self._rss_file_path = os.path.join(self._session.config.get_state_dir(), rss_name)

    @property
    def channel_id(self):
        return self._channel_community.get_channel_id()

    @property
    def name(self):
        return self._channel_community.get_channel_name()

    @property
    def description(self):
        return self._channel_community.get_channel_description()

    @property
    def mode(self):
        return self._channel_community.get_channel_mode()

    def get_rss_feed_url_list(self):
        return [url for url in self._rss_feed_dict.iterkeys()]

    def refresh_all_feeds(self):
        deferreds = [feed.parse_feed() for feed in self._rss_feed_dict.itervalues()]
        return DeferredList(deferreds, consumeErrors=True)

    def initialize(self):
        # load existing rss_feeds
        if os.path.exists(self._rss_file_path):
            self._logger.debug(u"loading existing channel rss list from %s...", self._rss_file_path)

            with codecs.open(self._rss_file_path, 'rb', encoding='utf8') as f:
                rss_list = json.load(f)
                for rss_url in rss_list:
                    self._rss_feed_dict[rss_url] = None

        if self._is_created:
            # create rss-parsers
            for rss_feed_url in self._rss_feed_dict:
                rss_parser = ChannelRssParser(self._session, self._channel_community, rss_feed_url)
                rss_parser.initialize()
                self._rss_feed_dict[rss_feed_url] = rss_parser
        else:
            # subscribe to the channel creation event
            self._session.add_observer(self._on_channel_created, SIGNAL_CHANNEL, [SIGNAL_ON_CREATED])

    def shutdown(self):
        self.shutdown_task_manager()
        for key, rss_parser in self._rss_feed_dict.iteritems():
            if rss_parser is not None:
                rss_parser.shutdown()
        self._rss_feed_dict = None
        self._channel_community = None
        self._session = None

    def _on_channel_created(self, subject, change_type, object_id, channel_data):
        if channel_data[u'channel'].cid != self._channel_community.cid:
            return

        def _create_rss_feed(channel_date):
            self._is_created = True

            # create rss feed parsers
            self._logger.debug(u"channel %s %s created", self.name, hexlify(self._channel_community.cid))
            for rss_feed_url in self._rss_feed_dict:
                assert self._rss_feed_dict[rss_feed_url] is None
                rss_parser = ChannelRssParser(self._session, self._channel_community, rss_feed_url)
                rss_parser.initialize()
                self._rss_feed_dict[rss_feed_url] = rss_parser

        task_name = u'create_rss_%s' % hexlify(channel_data[u'channel'].cid)
        self.register_task(task_name, reactor.callLater(0, _create_rss_feed, channel_data))

    def create_rss_feed(self, rss_feed_url):
        if rss_feed_url in self._rss_feed_dict:
            self._logger.warn(u"skip existing rss feed: %s", repr(rss_feed_url))
            return

        if not self._is_created:
            # append the rss url if the channel has not been created yet
            self._rss_feed_dict[rss_feed_url] = None
        else:
            # create an rss feed parser for this
            rss_parser = ChannelRssParser(self._session, self._channel_community, rss_feed_url)
            rss_parser.initialize()
            self._rss_feed_dict[rss_feed_url] = rss_parser

        # flush the rss_feed_url to json file
        with codecs.open(self._rss_file_path, 'wb', encoding='utf8') as f:
            rss_list = [rss_url for rss_url in self._rss_feed_dict.iterkeys()]
            json.dump(rss_list, f)

    def remove_rss_feed(self, rss_feed_url):
        if rss_feed_url not in self._rss_feed_dict:
            self._logger.warn(u"skip existing rss feed: %s", repr(rss_feed_url))
            return

        rss_parser = self._rss_feed_dict[rss_feed_url]
        if rss_parser is not None:
            rss_parser.shutdown()
        del self._rss_feed_dict[rss_feed_url]

        rss_feed_data = {u'channel': self._channel_community,
                         u'rss_feed_url': rss_feed_url}
        self._session.notifier.notify(SIGNAL_RSS_FEED, SIGNAL_ON_UPDATED, None, rss_feed_data)
