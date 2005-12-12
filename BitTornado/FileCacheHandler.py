""" My Preference List, All Files list I have seen or import from friends """

import os
import time

from cachedb import TorrentTable, string, friendly_time

class FileCacheHandler:
    def __init__(self):
        self.torrents = TorrentTable.getInstance()
        
    def addTorrent(self, torrent_hash, file_info, have=1):
        torrent = {}
        torrent['torrent_hash'] = torrent_hash
        torrent['torrent_name'] = file_info.get('file', '')
        torrent['torrent_path'] = os.path.abspath(file_info.get('path', '.'))
        torrent['content_name'] = file_info.get('name', '')
        torrent['content_size'] = file_info.get('length', 0)
        torrent['content_path'] = file_info.get('content_path', '')
        torrent['num_files'] = file_info.get('numfiles', 0)
        torrent['others'] = file_info.get('others', {})
        self.torrents.addTorrent(torrent, have)
    
    def updateTorrentRank(self, torrent_id, rank):
        self.torrents.updateTorrentRank(torrent_id, rank)
    
    def size_format(self, s):
        if not s:
            s = 0
        if s < 1024:
            size = s
            text = " Byte"
        elif s < 1048576:
            size = (s/1024.0)
            text = " KB"
        elif s < 1073741824L:
            size = (s/1048576.0)
            text = " MB"
        elif s < 1099511627776L:
            size = (s/1073741824.0)
            text = " GB"
        else:
            size = (s/1099511627776.0)
            text = "TB"
        size = ('%.2f' % size)
        return size + text
    
    # TODO: get pref by permid
    def getPreferences(self, show_friendly_time=True):
        torrents = self.getTorrents(show_friendly_time)
        preferences = []
        for torrent in torrents:
            if int(torrent['have']) == 1:
                preferences.append(torrent)
        return preferences
        
    def addOthersPreferences(self):
        pass
    
    def findTorrent(self, infohash):
        torrents = self.torrents.findTorrent(infohash)
        if torrents:
            return torrents[0]
        return None
                
    def getTorrents(self, show_friendly_time=True):    # only used for 
        torrents = self.torrents.getRecords()
        for torrent in torrents:
            torrent['content_size'] = self.size_format(torrent['content_size'])
            torrent['created_time'] = time.ctime(torrent['created_time'])
            if show_friendly_time:
                torrent['last_seen'] = friendly_time(torrent['last_seen'])
            #string(torrent)
            
        return torrents
    
    
