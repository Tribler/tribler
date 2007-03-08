import sys
from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler
from random import randint

DEBUG = False
    
class SimpleTorrentCollecting:
    """
        Simplest torrent collecting policy: randomly collect a torrent when received
        a buddycast message
    """
    
    def __init__(self, metadata_handler):
        self.torrent_db = TorrentDBHandler()
        self.metadata_handler = metadata_handler
        
    def updatePreferences(self, permid, preferences, selversion=-1):
        torrent = self.selecteTorrentToCollect(preferences)
        if torrent:
            self.metadata_handler.send_metadata_request(permid, torrent, selversion)
    
    def closeConnection(self, permid):
        pass
    
    def selecteTorrentToCollect(self, preferences, random=False):
        preferences = list(preferences)
        candidates = []
        for torrent in preferences:
            if not self.torrent_db.hasMetaData(torrent):    # check if the torrent has been downloaded
                candidates.append(torrent)
                
        if not candidates:
            return None
        
        if not random:
            relevances = self.torrent_db.getTorrentsValue(candidates, 'relevance')
            idx = relevances.index(max(relevances))
            return candidates[idx]
        else:
            idx = randint(0, nprefs-1)
            selected = candidates[idx]
            return selected
    