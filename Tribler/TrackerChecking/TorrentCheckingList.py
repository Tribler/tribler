# written by Yuan Yuan, Arno Bakker
# see LICENSE.txt for license information

# Arno: Removed dumb yet-another in-core version of the database
#

from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler

from threading import RLock, Lock
from time import time
from random import shuffle
from copy import copy, deepcopy
import sys
from traceback import print_exc, print_stack

DEBUG = True

class TorrentCheckingList:
    __single = None    # used for multithreaded singletons pattern
    lock = Lock()
    
    def __init__(self):
        if TorrentCheckingList.__single is not None:
            raise RuntimeError, "TorrentCheckingList is singleton"
        TorrentCheckingList.__single = self
        self.done_init = False
        self.lock = RLock()
        self.list_good = None
        self.list_unknown = NOne
#        self.list_dead = []
        self.torrent_db = TorrentDBHandler.getInstance()
        self.good_id = self.torrent_db._getStatusID("good")
        self.unknown_id = self.torrent_db._getStatusID("unknown")
        #self.dead_id = self.torrent_db._getStatusID("dead")
        
        self._prepareData()            # prepare the list
        self.done_init = True
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if TorrentCheckingList.__single is None:
            TorrentCheckingList.lock.acquire()   
            try:
                if TorrentCheckingList.__single is None:
                    TorrentCheckingList(*args, **kw)
            finally:
                TorrentCheckingList.lock.release()
        return TorrentCheckingList.__single
    getInstance = staticmethod(getInstance)
    
    def getGoodLen(self):
        try:
            self.lock.acquire()
            return len(self.list_good)
        finally:
            self.lock.release()
    
    def getUnknownLen(self):
        try:
            self.lock.acquire()
            return len(self.list_unknown)
        finally:
            self.lock.release()
    
#    def getDeadlen(self):
#        return len(self.list_dead)
    
    def getFirstGood(self):
        try:
            self.lock.acquire()
            if (self.list_good != []):
                torrent_id = self.list_good.pop(0)
            else:
                return None
        finally:
            self.lock.release()
        
    def getFirstUnknown(self):
        try:
            self.lock.acquire()
            if (self.list_unknown != []):
                torrent_id = self.list_good.pop(0)
            else:
                return None
        finally:
            self.lock.release()
    
    def _prepareData(self):
        try:
            self.lock.acquire()
            if DEBUG:
                print >>sys.stderr,"TorrentChecking: prepareData"
            
            if self.list_good is None and self.list_unknown is None:                
                self.list_good = [t[0] for t in self.torrent_db.getAll('torrent_id',status_id=self.good_id)]
                self.list_unknown = [t[0] for t in self.torrent_db.getAll('torrent_id',status_id=self.unknown_id)]
        #        self.list_dead = [t[0] for t in self.torrent_db.getAll('torrent_id',status_id=dead_id)]
        
                shuffle(self.list_good)
                shuffle(self.list_unknown)
        finally:
            self.lock.release()
    
    def _addTorrentToList(self, torrent_id, status_id):
        if status_id == self.good_id:
            self.list_good.append(torrent_id)
        elif status_id == self.unknown_id:
            self.list_unknown.append(torrent_id)
#        elif torrent["status"] == self.dead_id:
#            self.list_dead.append(torrent_id)

    def _deleteTorrentFromList(self, torrent_id):
        if torrent_id in self.list_good:
            self.list_good.remove(torrent_id)
        if torrent_id in self.list_unknown:
            self.list_unknown.remove(torrent_id)
        
    def updateFun(self, infohash, operate):
        try:
            self.lock.acquire()
            if not self.done_init:
                return
            torrent = self.torrent_db.getOne(('torrent_id', 'status_id'),infohash=infohash)
            #print "*** torrentcheckinglist updateFun", operate, torrent
            if not torrent:
                return
            torrent_id, status_id = torrent
            
            if operate == "update":
                self._deleteTorrentFromList(torrent_id)
                self._addTorrentToList(torrent_id,status_id)
            elif operate == "add":
                self._addTorrentToList(torrent_id,status_id)
            elif operate == "delete":
                self._deleteTorrentFromList(torrent_id)
        finally:
            self.lock.release()


if __name__ == "__main__":
    print TorrentCheckingList.getInstance().data

