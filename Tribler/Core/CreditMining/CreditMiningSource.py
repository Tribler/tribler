import logging

from binascii import hexlify, unhexlify
from twisted.internet import reactor

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.exception import CommunityNotFoundException
from Tribler.dispersy.util import call_on_reactor_thread
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.Core.simpledefs import NTFY_DISCOVERED, NTFY_TORRENT, NTFY_CHANNELCAST


class BaseSource(TaskManager):
    """
    Base class for credit mining source. For now, it can only be a Dispersy channel
    """

    def __init__(self, session, source, torrent_insert_cb):
        super(BaseSource, self).__init__()
        self._logger = logging.getLogger(BaseSource.__name__)

        self.session = session
        self.source = source
        self.torrent_insert_callback = torrent_insert_cb
        self.ready = False

    def start(self):
        """
        Start operating mining for this source
        """
        self.ready = True
        self._logger.debug('Start mining %s', str(self))

    def stop(self):
        """
        Kill tasks on this source
        """
        self.ready = False
        self.cancel_all_pending_tasks()
        self._logger.debug('Stop mining %s', str(self))

    def _on_err(self, err_msg):
        self._logger.error(err_msg)

    def __str__(self):
        return self.source


class ChannelSource(BaseSource):
    """
    Credit mining source from a channel.
    """

    def __init__(self, session, dispersy_cid, torrent_insert_cb):
        super(ChannelSource, self).__init__(session, dispersy_cid, torrent_insert_cb)
        self.community = None
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)

    @call_on_reactor_thread
    def start(self):
        super(ChannelSource, self).start()

        # Join the community if needed
        dispersy = self.session.get_dispersy_instance()
        try:
            self.community = dispersy.get_community(unhexlify(self.source), True)
        except CommunityNotFoundException:
            allchannelcommunity = None
            for community in dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    allchannelcommunity = community

            if allchannelcommunity:
                self.community = ChannelCommunity.init_community(dispersy,
                                                                 dispersy.get_member(mid=unhexlify(self.source)),
                                                                 allchannelcommunity.my_member, self.session)
                self._logger.info('Joined channel community %s', self.source)
            else:
                self._logger.error('Could not find AllChannelCommunity')
                return

        # Add torrents from database
        channel_id = self.community.get_channel_id()
        torrents = self.channelcast_db.getTorrentsFromChannelId(channel_id, True,
                                                                ['infohash', 'ChannelTorrents.name'])

        for index, (infohash_bin, name) in enumerate(torrents):
            infohash = hexlify(infohash_bin)
            self.register_task('insert_torrent_' + infohash, reactor.callLater(0.05 * index,
                                                                               self.torrent_insert_callback,
                                                                               self.source, infohash, name))

        self.session.add_observer(self.on_torrent_discovered, NTFY_TORRENT, [NTFY_DISCOVERED])

    def stop(self):
        super(ChannelSource, self).stop()
        self.session.remove_observer(self.on_torrent_discovered)

    def on_torrent_discovered(self, subject, changetype, objectID, object_dict):
        # Add newly discovered torrents
        if self.source == object_dict['dispersy_cid']:
            self.torrent_insert_callback(self.source, object_dict['infohash'], object_dict['name'])

    def __str__(self):
        return 'channel:' + self.source
