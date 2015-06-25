import logging


class TorrentStateManager(object):

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.torrent_manager = None
        self.library_manager = None

    def connect(self, torrent_manager, library_manager):
        self.torrent_manager = torrent_manager
        self.library_manager = library_manager

    def torrentFinished(self, infohash):
        torrent = self.torrent_manager.getTorrentByInfohash(infohash)
        self.library_manager.addDownloadState(torrent)
