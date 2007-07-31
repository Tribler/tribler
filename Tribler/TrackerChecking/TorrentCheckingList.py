# written by Yuan Yuan, Arno Bakker
# see LICENSE.txt for license information

# Arno: Removed dumb yet-another in-core version of the database
#

from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler

from threading import Lock
from time import time
from random import shuffle
from copy import copy, deepcopy
import sys
from traceback import print_exc

DEBUG = True

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
            infohash = self.list_good.pop(0)
            torrent = self.torrent_db.getTorrent(infohash)
            if DEBUG:
                print >>sys.stderr,"TorrCheckList: Get first good",`infohash`
            torrent['infohash'] = infohash
            return torrent
        return None                  
        
    def getFirstUnknown(self):
        if (self.list_unknown != []):
            infohash = self.list_unknown.pop(0)
            torrent = self.torrent_db.getTorrent(infohash)
            if DEBUG:
                print >>sys.stderr,"TorrCheckList: Get first unknown",`infohash`
            torrent['infohash'] = infohash
            return torrent
        return None     
    
    def _prepareData(self):
        
        if DEBUG:
            print >>sys.stderr,"TorrentChecking: prepareData"
        
        infohashes = self.torrent_db.getAllTorrents()
        for infohash in infohashes:
            torrent = self.torrent_db.getTorrent(infohash)
            if not torrent:
                continue
            if (torrent["status"] == "good"):
                self.list_good.append(infohash)
            elif (torrent["status"] == "unknown"):
                self.list_unknown.append(infohash)
            elif (torrent["status"] == "dead"):
                self.list_dead.append(infohash)
            else:
                raise Exception, "status of torrent not found"    # error

        del infohashes
        
        shuffle(self.list_good)
        shuffle(self.list_unknown)
        
        
#        print "total len", len(self.list_good) + len(self.list_unknown) + len(self.list_dead)
#        print "good len", len(self.list_good)
#        print "unknown len", len(self.list_unknown)
#        print "dead len", len(self.list_dead)

    
    def addTorrentToList(self, infohash, torrent):
        if torrent["status"] == "good":
            self.list_good.append(infohash)
        elif torrent["status"] == "unknown":
            self.list_unknown.append(infohash)
        elif torrent["status"] == "dead":
            self.list_dead.append(infohash)
        else:
            print "error"
        
    
    def deleteTorrentFromList(self, infohash):
        try:
            self.list_good.remove(infohash)
            self.list_unknown.remove(infohash)
            self.list_dead.remove(infohash)
        except:
            #if DEBUG:
            #    print_exc()
            pass
        
    def updateFun(self, infohash, operate):
        if not self.done_init:
            return
        torrent = self.torrent_db.getTorrent(infohash)
        #print "*** torrentcheckinglist updateFun", operate, torrent
        if not torrent:
            self.deleteTorrentFromList(infohash)
            return
        
        try:
            if operate == "update":
                self.deleteTorrentFromList(infohash)
                self.addTorrentToList(infohash,torrent)
            elif operate == "add":
                self.addTorrentToList(infohash,torrent)
            elif operate == "delete":
                self.deleteTorrentFromList(infohash)
        except Exception, msg:
            print sys.stderr, Exception, msg
            print print_exc()
#        print "total len", len(self.list_good) + len(self.list_unknown) + len(self.list_dead)
#        print "good len", len(self.list_good)
#        print "unknown len", len(self.list_unknown)
#        print "dead len", len(self.list_dead)
        
        
    def acquire(self):
        self.lock.acquire()
        
    def release(self):
        self.lock.release()

if __name__ == "__main__":
    print TorrentCheckingList.getInstance().data

