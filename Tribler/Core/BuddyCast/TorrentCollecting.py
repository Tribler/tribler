# Written by Jie Yang
# see LICENSE.txt for license information

import sys
from Tribler.Core.Utilities.utilities import show_permid, bin2str
from random import randint
from time import time
from sets import Set

DEBUG = False
    
class SimpleTorrentCollecting:
    """
        Simplest torrent collecting policy: randomly collect a torrent when received
        a buddycast message
    """
    
    def __init__(self, metadata_handler, data_handler):
        self.metadata_handler = metadata_handler
        self.data_handler = data_handler
        self.torrent_db = data_handler.torrent_db
        self.pref_db = data_handler.pref_db
        self.cache_pool = {}
        
#        self.cooccurrence = {}
        
#    def updateAllCooccurrence(self):
#        self.cooccurrence = self.mypref_db.getAllTorrentCoccurrence()
        
#    def getInfohashRelevance(self, infohash):
#        return self.torrent_db.getOne('relevance', infohash=bin2str(infohash))
        
    def trigger(self, permid, selversion, collect_candidate=None):
        infohash = self.torrent_db.selectTorrentToCollect(permid, collect_candidate)
        #infohash = self.selectTorrentToCollect(permid, torrents2down)
        #print >> sys.stderr, '************* trigger', `infohash`, `collect_candidate`
        #if collect_candidate and infohash:
        #    assert infohash in collect_candidate, (infohash,collect_candidate)
        if infohash and self.metadata_handler:
            self.metadata_handler.send_metadata_request(permid, infohash, selversion)
        
#    def updatePreferences(self, permid, preferences, selversion=-1):
#        # called by overlay thread
#        #TODO
#        torrent = self.selectTorrentToCollect(preferences)
#        if torrent and self.metadata_handler:
#            self.metadata_handler.send_metadata_request(permid, torrent, selversion)
#        return torrent
#    
#    def addConnection(self, permid, selversion):
#        #TODO: read preference and send a requtest
#        pass
    
#    def closeConnection(self, permid):
#        pass
    
#    def selectTorrentToCollect(self, permid, collect_candidate=None):
#        candidate = self.torrent_db.selectTorrentToCollect(permid, collect_candidate)
#        return candidate
#        
#        
#        for torrent in collect_candidate:
#            if not self.torrent_db.hasMetaData(torrent):    # check if the torrent has been downloaded
#                candidates.append(torrent)
#                
#        if not candidates:
#            return None
#        
#        if not random:
#            relevances = []
#            for infohash in candidates:
#                #TODO
#                rel = self.torrent_db.getOne('relevance', infohash=bin2str(infohash))
#                if rel is None:
#                    rel = 0
#                #rel = self.getInfohashRelevance(infohash)
#                relevances.append(rel)
#            idx = relevances.index(max(relevances))
#            return candidates[idx]
#        else:
#            idx = randint(0, len(candidates)-1)
#            selected = candidates[idx]
#            return selected
    

