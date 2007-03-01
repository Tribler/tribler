# Written by Yuan Yuan
# see LICENSE.txt for license information

from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.CacheDB.DBObserver import DBObserver

from cachedb import *
from copy import deepcopy
from sets import Set
from traceback import print_exc
from threading import Lock
import sys

class SynTorrentDBHandler(TorrentDBHandler):
    """ This is a variant of TorrentDBHandler, which is used to notice 
        multiple modules when one module updated the torrent db.
        For example, when torrent collecting module received a new torrent,
        it will call this instance and therefore update ABC GUI.
        To use it, a moulde must register updateFun() 
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
        
    def addTorrent(self, infohash, torrent, new_metadata=False, updateFlag=True):
        TorrentDBHandler.addTorrent(self, infohash, torrent, new_metadata)  
        if (updateFlag == True):
            self.notifyObserver(infohash, "add")

    def updateTorrent(self, infohash, updateFlag=True, **kw):
        TorrentDBHandler.updateTorrent(self, infohash, **kw)
        torrent = TorrentDBHandler.getTorrent(self, infohash)
        if (updateFlag == True):
            self.notifyObserver(infohash, "update")
        
    def deleteTorrent(self, infohash, delete_file=False, updateFlag=True):
        TorrentDBHandler.deleteTorrent(self, infohash, delete_file)
        if (updateFlag == True):
            self.notifyObserver(infohash, "delete")
            
            