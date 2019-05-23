from __future__ import absolute_import

import logging
from binascii import hexlify

from ipv8.taskmanager import TaskManager


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
        self.shutdown_task_manager()
        self._logger.debug('Stop mining %s', str(self))

    def _on_err(self, err_msg):
        self._logger.error(err_msg)

    def __str__(self):
        return self.source


class ChannelSource(BaseSource):
    """
    Credit mining source from a (giga)channel.
    """

    def start(self):
        super(ChannelSource, self).start()

        channel = self.session.lm.mds.ChannelMetadata.get_channel_with_id(self.source)
        if not channel:
            self._logger.error("Could not find channel!")
            return

        # Add torrents from database
        for torrent in channel.contents_list:
            self.torrent_insert_callback(hexlify(self.source), hexlify(torrent.infohash), torrent.title)

    def __str__(self):
        return 'channel:' + self.source
