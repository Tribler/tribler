# written by Yuan Yuan
# see LICENSE.txt for license information

from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler

from threading import Lock
from time import time
from random import shuffle
from copy import copy, deepcopy
import sys
from traceback import print_exc

class TorrentCheckingList:
    __single = None
    
    def __init__(self):
        if TorrentCheckingList.__single:
            raise RuntimeError, "TorrentCheckingList is singleton"
        TorrentCheckingList.__single = self
        self.done_init = False
        self.lock = Lock()
        self.list_good = []
        self.list_unknown = []
        self.list_dead = []
#        self.torrent_db = TorrentDBHandler()
        self.torrent_db = SynTorrentDBHandler(updateFun=self.updateFun)
        self._readDB()
        self._prepareData()            # prepare the list
        self.done_init = True
        
    def getInstance(*args, **kw):
        if TorrentCheckingList.__single is None:
            TorrentCheckingList(*args, **kw)       
        return TorrentCheckingList.__single
    getInstance = staticmethod(getInstance)
    
    def getGoodLen(self):
        return len(self.list_good)
    
    def getUnknownLen(self):
        return len(self.list_unknown)
    
    def getDeadlen(self):
        return len(self.list_dead)
    
    def getFirstGood(self):
        if (self.list_good != []):
            torrent = self.list_good.pop(0)
            del self.info_dict[torrent["infohash"]]
            return deepcopy(torrent)
        return None                  
        
    def getFirstUnknown(self):
        if (self.list_unknown != []):
            torrent = self.list_unknown.pop(0)
            del self.info_dict[torrent["infohash"]]
            return deepcopy(torrent)
        return None     
    
    def _prepareData(self):
        
        self.info_dict = {}            # used to setTorrent
        
        for idata in self.data:
            self.info_dict[idata["infohash"]] = idata
            if (idata["status"] == "good"):
                self.list_good.append(idata)
            elif (idata["status"] == "unknown"):
                self.list_unknown.append(idata)
            elif (idata["status"] == "dead"):
                self.list_dead.append(idata)
            else:
                raise Exception, "status of torrent not found"    # error

        shuffle(self.list_good)
        shuffle(self.list_unknown)
        
#        print "total len", len(self.list_good) + len(self.list_unknown) + len(self.list_dead)
#        print "good len", len(self.list_good)
#        print "unknown len", len(self.list_unknown)
#        print "dead len", len(self.list_dead)

    
    def addTorrentToList(self, torrent):
        if torrent["status"] == "good":
            self.list_good.append(torrent)
        elif torrent["status"] == "unknown":
            self.list_unknown.append(torrent)
        elif torrent["status"] == "dead":
            self.list_dead.append(torrent)
        else:
            print "error"
        self.info_dict[torrent["infohash"]] = torrent
        
    
    def deleteTorrentFromList(self, infohash):
        try:
            if not self.info_dict.has_key(infohash):
                return
            old = self.info_dict[infohash]
            del self.info_dict[infohash]
            if old["status"] == "good":
                self.list_good.remove(old)
            elif old["status"] == "unknown":
                self.list_unknown.remove(old)
            elif old["status"] == "dead":
                self.list_dead.remove(old)
            else:
                print "error"
        except:
            pass
        
    def updateFun(self, infohash, operate):
        if not self.done_init:
            return
        torrent = self.torrent_db.getTorrent(infohash)
        #print "*** torrentcheckinglist updateFun", operate, torrent
        if not torrent:
            self.deleteTorrentFromList(infohash)
            return
        torrent.update({'infohash':infohash})
        
        try:
            if operate == "update":
                self.deleteTorrentFromList(torrent["infohash"])
                self.addTorrentToList(torrent)
            elif operate == "add":
                self.addTorrentToList(torrent)
            elif operate == "delete":
                self.deleteTorrentFromList(torrent["infohash"])
        except Exception, msg:
            print sys.stderr, Exception, msg
            print print_exc()
#        print "total len", len(self.list_good) + len(self.list_unknown) + len(self.list_dead)
#        print "good len", len(self.list_good)
#        print "unknown len", len(self.list_unknown)
#        print "dead len", len(self.list_dead)
        
    def _readDB(self):
        self.data = self.torrent_db.getRecommendedTorrents(light=True)
        
        
    def acquire(self):
        self.lock.acquire()
        
    def release(self):
        self.lock.release()

if __name__ == "__main__":
    print TorrentCheckingList.getInstance().data

