from threading import Thread, Event
import shutil
import sys
import os
import time
from Tribler.Core.TorrentDef import TorrentDef
DIR_CHECK_FREQUENCY = 10  # Check directories every 10 seconds


class DirectoryFeedThread(Thread):
    __single = None

    def __init__(self):
        if DirectoryFeedThread.__single:
            raise RuntimeError("DirectoryFeedThread is singleton")
        DirectoryFeedThread.__single = self

        Thread.__init__(self)
        self.setName("DirectoryFeed" + self.getName())
        self.setDaemon(True)

        self.paths = {}
        self.feeds = []

        self.done = Event()

    def getInstance(*args, **kw):
        if DirectoryFeedThread.__single is None:
            DirectoryFeedThread(*args, **kw)
        return DirectoryFeedThread.__single
    getInstance = staticmethod(getInstance)

    def _on_torrent_found(self, dirpath, torrentpath, infohash, torrent_data):
        print >>sys.stderr, 'DirectoryFeedThread: Adding', torrentpath
        imported_dir = os.path.join(dirpath, 'imported')
        if not os.path.exists(imported_dir):
            os.makedirs(imported_dir)
        shutil.move(torrentpath, os.path.join(imported_dir, os.path.basename(torrentpath)))

    def addDir(self, dirpath, callback=None):
        # callback(dirpath, infohash, torrent_data)

        if dirpath not in self.paths:
            self.paths[dirpath] = 'active'
            feed = DirectoryFeedReader(dirpath)
            self.feeds.append([feed, callback])

        elif callback:  # replace callback
            for tup in self.feeds:
                if tup[0].path == dirpath:
                    tup[2] = callback

    def deleteDir(self, path):
        raise NotImplementedError('TODO')

    def refresh(self):
        for (feed, callback) in self.feeds:
            if self.paths[feed.path] == 'active':
                for torrentpath, infohash, torrent_data in feed.read_torrents():
                    self._on_torrent_found(feed.path, torrentpath, infohash, torrent_data)
                    if callback:
                        callback(feed.path, infohash, torrent_data)

    def run(self):
        time.sleep(60)  # Let other Tribler components, in particular, Session startup

        print >>sys.stderr, '*** DirectoryFeedThread: Starting first refresh round'
        while not self.done.isSet():
            self.refresh()
            time.sleep(DIR_CHECK_FREQUENCY)

    def shutdown(self):
        self.done.set()


class DirectoryFeedReader:

    def __init__(self, path):
        self.path = path

    def read_torrents(self):
        files = os.listdir(self.path)
        for file in files:
            full_path = os.path.join(self.path, file)

            tdef = None
            try:
                tdef = TorrentDef.load(full_path)
                yield full_path, tdef.infohash, tdef.get_metainfo()

            except:
                pass
