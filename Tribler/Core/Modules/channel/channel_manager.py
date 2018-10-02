import logging
from binascii import hexlify

from Tribler.Core.Modules.channel.channel import ChannelObject
from Tribler.Core.exceptions import DuplicateChannelNameError
from Tribler.community.channel.community import ChannelCommunity
from Tribler.pyipv8.ipv8.taskmanager import TaskManager


class ChannelManager(TaskManager):
    """
    The Manager class that handles the Channels owned by ourselves.
    It supports multiple-Channel creation and RSS feed.
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

        self._channel_list = []

    def initialize(self):
        self.dispersy = self.session.get_dispersy_instance()

        # get all channels owned by me
        from Tribler.community.channel.community import ChannelCommunity
        for community in self.session.lm.dispersy.get_communities():
            if isinstance(community, ChannelCommunity) and community.master_member and community.master_member.private_key:
                channel_obj = ChannelObject(self.session, community, is_created=True)
                channel_obj.initialize()
                self._channel_list.append(channel_obj)

                self._logger.debug(u"loaded channel '%s', %s", channel_obj.name, hexlify(community.cid))

    def shutdown(self):
        self.shutdown_task_manager()
        self._channel_mode_map = None

        for channel_object in self._channel_list:
            channel_object.shutdown()
        self._channel_list = None

        self.dispersy = None
        self.session = None

    def create_channel(self, name, description, mode, rss_url=None):
        """
        Creates a new Channel.
        :param name: Name of the Channel.
        :param description: Description of the Channel.
        :param mode: Mode of the Channel ('open', 'semi-open', or 'closed').
        :param rss_url: RSS URL for the Channel.
        :return: Channel ID
        :raises DuplicateChannelNameError if name already exists
        """
        assert isinstance(name, basestring), u"name is not a basestring: %s" % type(name)
        assert isinstance(description, basestring), u"description is not a basestring: %s" % type(description)
        assert mode in self._channel_mode_map, u"invalid mode: %s" % mode
        assert isinstance(rss_url, basestring) or rss_url is None, u"rss_url is not a basestring or None: %s" % type(rss_url)

        # if two channels have the same name, this will not work
        for channel_object in self._channel_list:
            if name == channel_object.name:
                raise DuplicateChannelNameError(u"Channel name already exists: %s" % name)

        channel_mode = self._channel_mode_map[mode]
        community = ChannelCommunity.create_community(self.dispersy, self.session.dispersy_member,
                                                      tribler_session=self.session)

        channel_obj = ChannelObject(self.session, community)
        channel_obj.initialize()

        community.set_channel_mode(channel_mode)
        community.create_channel(name, description)

        # create channel object
        self._channel_list.append(channel_obj)

        if rss_url is not None:
            channel_obj.create_rss_feed(rss_url)

        self._logger.debug(u"creating channel '%s', %s", channel_obj.name, hexlify(community.cid))
        return channel_obj.channel_id

    def get_my_channel(self, channel_id):
        """
        Gets the ChannelObject with the given channel id.
        :return: The ChannelObject if exists, otherwise None.
        """
        channel_object = None
        for obj in self._channel_list:
            if obj.channel_id == channel_id:
                channel_object = obj
                break
        return channel_object

    def get_channel(self, name):
        """
        Gets a Channel by name.
        :param name: Channel name.
        :return: The channel object if exists, otherwise None.
        """
        channel_object = None
        for obj in self._channel_list:
            if obj.name == name:
                channel_object = obj
                break
        return channel_object

    def get_channel_list(self):
        """
        Gets a list of all channel objects.
        :return: The list of all channel objects.
        """
        return self._channel_list
