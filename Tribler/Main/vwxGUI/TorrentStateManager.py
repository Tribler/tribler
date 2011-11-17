from Tribler.community.channel.community import ChannelCommunity
import sys


class TorrentStateManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self, guiUtility):
        if TorrentStateManager.__single:
            raise RuntimeError, "TorrentStateManager is singleton"
        TorrentStateManager.__single = self
        
    def getInstance(*args, **kw):
        if TorrentStateManager.__single is None:
            TorrentStateManager(*args, **kw)       
        return TorrentStateManager.__single
    getInstance = staticmethod(getInstance)
    
    def connect(self, torrent_manager, library_manager, channelsearch_manager):
        self.torrent_manager = torrent_manager
        self.library_manager = library_manager
        self.channelsearch_manager = channelsearch_manager
    
    def torrentFinished(self, infohash):
        _,_, torrents = self.channelsearch_manager.getChannnelTorrents(infohash)
        
        openTorrents = []
        for torrent in torrents:
            state, iamModerator = torrent.channel.getState()
            if state >= ChannelCommunity.CHANNEL_SEMI_OPEN or iamModerator:
                openTorrents.append(torrent)
                
        if len(openTorrents) > 0:  
            torrent = openTorrents[0]
            self.library_manager.addDownloadState(torrent)
            torrent = self.torrent_manager.loadTorrent(torrent)
            
            ds = torrent.ds
            dest_files = ds.get_download().get_dest_files()
            largest_file = torrent.largestvideofile
            
            for filename, destname in dest_files:
                if filename == largest_file:
                    print >> sys.stderr, 'Can run post-download scripts for', torrent, filename, destname