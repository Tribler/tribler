import sys
from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.utilities import show_permid
from random import randint
from time import time

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
            idx = randint(0, len(preferences)-1)
            selected = candidates[idx]
            return selected
    
class TiT4TaTTorrentCollecting(SimpleTorrentCollecting):
    """
    """
    
    def __init__(self, metadata_handler, rawserver):
        SimpleTorrentCollecting.__init__(self, metadata_handler)
        self.rawserver = rawserver
        self.peers = {}
        self.starttime = time()
        self.work()
        
    def work(self):
        interval = self.getCurrrentInterval()
        self.rawserver.add_task(self.work, interval)
        if not self.peers:
            return
        
    def _work(self):
        pass
    
    def getCurrrentInterval(self):
        now = time()
        if now - self.starttime < 5*60:
            return 5
         
    def closeConnection(self, permid):
        try:
            self.peers.pop(permid)
        except KeyError:
            print >> sys.stderr, "tc: close not existed connection", show_permid(permid)
    
