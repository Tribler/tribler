import logging


class TorrentStateManager(object):
    # Code to make this a singleton
    __single = None

    def __init__(self, session):
        if TorrentStateManager.__single:
            raise RuntimeError("TorrentStateManager is singleton")
        TorrentStateManager.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.torrent_manager = None
        self.library_manager = None

    def getInstance(*args, **kw):
        if TorrentStateManager.__single is None:
            TorrentStateManager(*args, **kw)
        return TorrentStateManager.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        TorrentStateManager.__single = None
    delInstance = staticmethod(delInstance)

    def connect(self, torrent_manager, library_manager):
        self.torrent_manager = torrent_manager
        self.library_manager = library_manager

    def torrentFinished(self, infohash):
        torrent = self.torrent_manager.getTorrentByInfohash(infohash)
        self.library_manager.addDownloadState(torrent)
