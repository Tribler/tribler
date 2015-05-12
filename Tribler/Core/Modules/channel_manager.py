import logging

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread

from Tribler.community.channel.community import ChannelCommunity
from Tribler.Core.simpledefs import SIGNAL_CHANNEL, SIGNAL_ON_CREATED
from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.Core.Modules.channel_rss import ChannelRssParser


class ChannelManager(TaskManager):
    """
    (An ongoing work) The Manager class that handles all Channel-related tasks.
    (Lipu): Temporarily for metadata injector only. Supports multiple-Channel creation and RSS feed.
    """

    def __init__(self, session):
        super(ChannelManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.dispersy = None

        self._channel_mode_map = {u'open': ChannelCommunity.CHANNEL_OPEN,
                                  u'semi-open': ChannelCommunity.CHANNEL_SEMI_OPEN,
                                  u'closed': ChannelCommunity.CHANNEL_CLOSED,
                                  }

        self._channel_callback_dict = {}
        self._rss_parser_list = []

    @blocking_call_on_reactor_thread
    def initialize(self):
        self.dispersy = self.session.get_dispersy_instance()

        self.session.add_observer(self._on_my_channel_created, SIGNAL_CHANNEL, [SIGNAL_ON_CREATED])

    @blocking_call_on_reactor_thread
    def shutdown(self):
        self.cancel_all_pending_tasks()
        self._channel_mode_map = None
        self._channel_callback_dict = None
        for rss_parser in self._rss_parser_list:
            rss_parser.shutdown()
        self._rss_parser_list = None

        self.dispersy = None
        self.session = None

    def create_channel(self, name, description, mode, rss_url=None):
        """
        Creates a new Channel.
        :param name: Name of the Channel.
        :param description: Description of the Channel.
        :param mode: Mode of the Channel ('open', 'semi-open', or 'closed').
        :param rss_url: RSS URL for the Channel.
        """
        assert isinstance(name, basestring), u"name is not a basestring: %s" % type(name)
        assert isinstance(description, basestring), u"description is not a basestring: %s" % type(description)
        assert mode in self._channel_mode_map, u"invalid mode: %s" % mode
        assert isinstance(rss_url, basestring), u"rss_url is not a basestring: %s" % type(rss_url)

        # if two channels have the same name, this will not work
        if name in self._channel_callback_dict:
            self._logger.error(u"Channel name already exists: %s", name)
            return

        def _create_channel():
            channel_mode = self._channel_mode_map[mode]
            community = ChannelCommunity.create_community(self.dispersy, self.session.dispersy_member,
                                                          tribler_session=self.session)
            community.set_channel_mode(channel_mode)
            community.create_channel(name, description)

        self._channel_callback_dict[name] = {u'rss_url': rss_url}
        self.register_task(u"create_channel_%s" % name, reactor.callLater(0, _create_channel))

    @call_on_reactor_thread
    def attach_rss_to_channel(self, channel, rss_url):
        """
        Attaches a RSS feed to the given Channel.
        :param channel: The given Channel.
        :param rss_url: The RSS feed URL.
        """
        rss_parser = ChannelRssParser(self.session, channel, rss_url)
        rss_parser.initialize()
        self._rss_parser_list.append(rss_parser)

    @call_on_reactor_thread
    def _on_my_channel_created(self, subject, change_type, object_id, channel_data):
        """
        Callback that is invoked when one of my Channels have been created.
        :param channel_data: Data of the Channel.
        """
        self._logger.info(u"Channel created: %s", channel_data[u'name'])

        callback_dict = self._channel_callback_dict.pop(channel_data[u'name'])
        if callback_dict[u'rss_url'] is not None:
            self._logger.info(u"Creating automatic RSS feed parser for Channel %s", channel_data[u'name'])
            self.attach_rss_to_channel(channel_data[u'channel'], callback_dict[u'rss_url'])
