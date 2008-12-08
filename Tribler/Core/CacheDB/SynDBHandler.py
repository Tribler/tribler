# Written by Yuan Yuan
# see LICENSE.txt for license information

from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler, PeerDBHandler
from Tribler.Core.CacheDB.DBObserver import DBObserver

from cachedb import *
from copy import deepcopy
from sets import Set
from traceback import print_exc
import sys

class SynTorrentDBHandler(TorrentDBHandler):
    """ This is a variant of TorrentDBHandler, which is used to notice 
        multiple modules when one module updated the torrent db.
        For example, when torrent collecting module received a new torrent,
        it will call this instance and therefore update ABC GUI.
        To use it, a module must register updateFun() 
    """

    def __init__(self, db_dir='', updateFun = None):        
        TorrentDBHandler.__init__(self, db_dir)        
        self.observer = DBObserver.getInstance()
        self.key = "TorrentDB"
        self.updateFun = updateFun
        if (self.updateFun != None):
            self.observer.register(self.updateFun, self.key)
            
    def __del__(self):
        if (self.updateFun!= None):
            self.observer.unregister(self.updateFun, self.key)
        
    def notifyObserver(self, *parameter):
        self.observer.update(self.key, *parameter)
        
    def addTorrent(self, infohash, torrent={}, new_metadata=False, updateFlag=True):
        # Be ware: the torrent could already be in DB, so it is an update actually
        TorrentDBHandler.addTorrent(self, infohash, torrent, new_metadata)  
        if (updateFlag == True):
            self.notifyObserver(infohash, "add")

    def updateTorrent(self, infohash, updateFlag=True, **kw):
        TorrentDBHandler.updateTorrent(self, infohash, **kw)
        if (updateFlag == True):
            self.notifyObserver(infohash, "update")
        
    def updateTorrentRelevance(self, infohash, relevance, updateFlag=True):
        TorrentDBHandler.updateTorrentRelevance(self, infohash, relevance)
        if (updateFlag == True):
            self.notifyObserver(infohash, "update")
        
    def deleteTorrent(self, infohash, delete_file=False, updateFlag=True):
        deleted = TorrentDBHandler.deleteTorrent(self, infohash, delete_file)
        if (deleted and updateFlag == True):
            self.notifyObserver(infohash, "delete")
        return deleted

    def addAllTorrents(self):
        """ send an 'add' message for each torrent in db. """
        for infohash, data in self.iteritems():
            if not data or not data['info']:
                continue
            #print >> sys.stderr, "*********** add torrent", data['torrent_name'] 
            self.notifyObserver(infohash, "add")


class SynPeerDBHandler(PeerDBHandler):
    """ This is a variant of PeerDBHandler, which is used to notice 
        multiple modules when one module updated the peer db.
        For example, when peer collecting module received a new peer,
        it will call this instance and therefore update ABC GUI.
        To use it, a moulde must register updateFun() 
    """

    def __init__(self, db_dir='', updateFun = None):        
        PeerDBHandler.__init__(self, db_dir)        
        self.observer = DBObserver.getInstance()
        self.key = "PeerDB"
        self.updateFun = updateFun
        if (self.updateFun != None):
            self.observer.register(self.updateFun, self.key)
            
    def __del__(self):
        if (self.updateFun!= None):
            self.observer.unregister(self.updateFun, self.key)
        
    def notifyObserver(self, *parameter):
        self.observer.update(self.key, *parameter)
        
    def addPeer(self, permid, value, update_dns=True, updateFlag=True):
        # Be ware: the peer could already be in DB, so it is an update actually
        existed = PeerDBHandler.getPeer(self, permid)
        PeerDBHandler.addPeer(self, permid, value, update_dns)  
        if (updateFlag == True):
            if existed:
                self.notifyObserver(permid, "update")
            else:
                self.notifyObserver(permid, "add")

    def updatePeer(self, permid, key, value, updateFlag=True):
        PeerDBHandler.updatePeer(self, permid, key, value)
        if (updateFlag == True):
            self.notifyObserver(permid, "update")
            
    def updateTimes(self, permid, key, change, updateFlag=True):
        PeerDBHandler.updateTimes(self, permid, key, change)
        if (updateFlag == True):
            self.notifyObserver(permid, "update")
        
    def deletePeer(self, permid, updateFlag=True):
        deleted = PeerDBHandler.deletePeer(self, permid)
        if (deleted and updateFlag == True):
            self.notifyObserver(permid, "delete")
            
    def hidePeer(self, permid, updateFlag=True):
        # this func is currently only used by buddycast & peer view
        if (updateFlag == True):
            self.notifyObserver(permid, "hide")
            
