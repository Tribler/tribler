# written by Arno Bakker, Yuan Yuan
# Modified by Raul Jimenez to integrate KTH DHT
# see LICENSE.txt for license information

import sys
from threading import currentThread
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread

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
            from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id, IdError
            try:
                infohash_id = Id(infohash)
                self.dht.get_peers(infohash, infohash_id, self.got_peers_callback)
            except (IdError):
                print >>sys.stderr,"Rerequester: _dht_rerequest: self.info_hash is not a valid identifier"
                return
        elif DEBUG:
            print >>sys.stderr,"mainlineDHTChecker: No lookup, no DHT support loaded"

    
    def got_peers_callback(self, infohash, peers, node=None):
        """ Called by network thread """
        if DEBUG:
            if peers:
                print >>sys.stderr,"mainlineDHTChecker: Got",len(peers),"peers for torrent",`infohash`,currentThread().getName()
            else:
                print >>sys.stderr,"mainlineDHTChecker: Got no peers for torrent",`infohash`,currentThread().getName()

        if peers:
            # Arno, 2010-02-19: this can be called frequently with the new DHT,
            # so first check before doing commit.
            @forceDBThread
            def do_db():
                torrent = self.torrent_db.getTorrent(infohash) # ,keys=('torrent_id','status_id') don't work, st*pid code
                if torrent['status'] != "good":
                    status = "good"
                    kw = {'status': status}
                    self.torrent_db.updateTorrent(infohash, commit=True, **kw)
            do_db()