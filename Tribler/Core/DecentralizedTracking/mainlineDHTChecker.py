# written by Arno Bakker, Yuan Yuan
# Modified by Raul Jimenez to integrate KTH DHT
# see LICENSE.txt for license information

import sys
from threading import currentThread
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler

DEBUG = False

class mainlineDHTChecker:
    __single = None

    def __init__(self):

        if DEBUG:
            print >>sys.stderr,'mainlineDHTChecker: initialization'
        if mainlineDHTChecker.__single:
            raise RuntimeError, "mainlineDHTChecker is Singleton"
        mainlineDHTChecker.__single = self
        
        self.dht = None
        self.torrent_db = TorrentDBHandler.getInstance()

    def getInstance(*args, **kw):
        if mainlineDHTChecker.__single is None:
            mainlineDHTChecker(*args, **kw)
        return mainlineDHTChecker.__single
    getInstance = staticmethod(getInstance)

    def register(self,dht):
        self.dht = dht
        
    def lookup(self,infohash):
        if DEBUG:
            print >>sys.stderr,"mainlineDHTChecker: Lookup",`infohash`

        if self.dht is not None:
            from Tribler.Core.DecentralizedTracking.kadtracker.identifier import Id, IdError
            try:
                infohash_id = Id(infohash)
                func = lambda p:self.got_peers_callback(infohash,p)
                self.dht.get_peers(infohash_id,func)
            except (IdError):
                print >>sys.stderr,"Rerequester: _dht_rerequest: self.info_hash is not a valid identifier"
                return
        elif DEBUG:
            print >>sys.stderr,"mainlineDHTChecker: No lookup, no DHT support loaded"

        
    def got_peers_callback(self,infohash,peers):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"mainlineDHTChecker: Got",len(peers),"peers for torrent",`infohash`,currentThread().getName()
            
        alive = len(peers) > 0
        if alive:
            status = "good"
            kw = {'status': status}
            self.torrent_db.updateTorrent(infohash, updateFlag=True, **kw)
    
