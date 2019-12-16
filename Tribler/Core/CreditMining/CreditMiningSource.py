import logging

from ipv8.taskmanager import TaskManager

from Tribler.Core.Utilities.unicode import hexlify


class BaseSource(TaskManager):
    """
    Base class for a credit mining source.
    The source specifies where to get torrents from.
    """

    def __init__(self, session, source, torrent_insert_cb):
        super(BaseSource, self).__init__()
        self._logger = logging.getLogger(BaseSource.__name__)

        self.session = session
        self.source = source
        self.torrent_insert_callback = torrent_insert_cb

    def start(self):
        """
        Start operating mining for this source
        """
        self._logger.debug('Start mining %s', str(self))

    async def stop(self):
        """
        Kill tasks on this source
        """
        await self.shutdown_task_manager()
        self._logger.debug('Stop mining %s', str(self))

    def __str__(self):
        return self.source


class ChannelSource(BaseSource):
    """
    Credit mining source from a (giga)channel.
    """

    def start(self):
        super(ChannelSource, self).start()

        channel = self.session.mds.ChannelMetadata.get_recent_channel_with_public_key(self.source)
        if not channel:
            self._logger.error("Could not find channel!")
            return

        # Add torrents from database
        for torrent in channel.contents_list:
            self.torrent_insert_callback(hexlify(self.source),
                                         hexlify(torrent.infohash),
                                         torrent.title)

    def __str__(self):
        return 'channel:' + hexlify(self.source)
