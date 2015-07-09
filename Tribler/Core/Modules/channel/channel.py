from binascii import hexlify
import codecs
import collections
import json
import logging
import os

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import call_on_reactor_thread

from Tribler.Core.simpledefs import SIGNAL_CHANNEL, SIGNAL_ON_CREATED
from Tribler.Core.Modules.channel.channel_rss import ChannelRssParser


class ChannelObject(TaskManager):

    def __init__(self, session, channel_community, is_created=False):
        super(ChannelObject, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self._session = session
        self._channel_community = channel_community
        self._is_created = is_created
        self._rss_feed_dict = collections.OrderedDict()

        rss_name = u"channel_rss_%s.json" % hexlify(self._channel_community.cid)
        self._rss_file_path = os.path.join(self._session.get_state_dir(), rss_name)

    @property
    def name(self):
        return self._channel_community.get_channel_name()

    @call_on_reactor_thread
    def initialize(self):
        # load existing rss_feeds
        if os.path.exists(self._rss_file_path):
            self._logger.debug(u"loading existing channel rss list from %s...", self._rss_file_path)

            with codecs.open(self._rss_file_path, 'rb', encoding='utf8') as f:
                rss_list = json.load(f, encoding='utf8')
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

    @call_on_reactor_thread
    def shutdown(self):
        self.cancel_all_pending_tasks()
        for key, rss_parser in self._rss_feed_dict.iteritems():
            if rss_parser is not None:
                rss_parser.shutdown()
        self._rss_feed_dict = None
        self._channel_community = None
        self._session = None

    @call_on_reactor_thread
    def _on_channel_created(self, subject, change_type, object_id, channel_data):
        if channel_data[u'channel'].cid != self._channel_community.cid:
            return

        # create rss feed parsers
        self._logger.debug(u"channel %s %s created", self.name, hexlify(self._channel_community.cid))
        for rss_feed_url in self._rss_feed_dict:
            assert self._rss_feed_dict[rss_feed_url] is None
            rss_parser = ChannelRssParser(self._session, self._channel_community, rss_feed_url)
            rss_parser.initialize()
            self._rss_feed_dict[rss_feed_url] = rss_parser

    @call_on_reactor_thread
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
