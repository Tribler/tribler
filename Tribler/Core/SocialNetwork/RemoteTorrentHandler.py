# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Handles the case where the user did a remote query and now selected one of the
# returned torrents for download. 
#

import sys
import Queue
import threading
from time import sleep
from random import choice

from Tribler.Core.simpledefs import INFOHASH_LENGTH
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler

SLEEP_BETWEEN_REQUESTS = 1
SLEEP_BETWEEN_REQUESTS_TURBO = 0.2
DEBUG = False

class RemoteTorrentHandler(threading.Thread):
    
    __single = None
    
    def __init__(self):
        if RemoteTorrentHandler.__single:
            raise RuntimeError, "RemoteTorrentHandler is singleton"
        RemoteTorrentHandler.__single = self
        
        threading.Thread.__init__(self)
        
        self.torrent_db = TorrentDBHandler.getInstance()
        self.name = 'RemoteTorrentHandler'
        self.daemon = True
        
        self.callbacks = {}
        self.sources = {}
        self.requestedTorrents = Queue.PriorityQueue()

    def getInstance(*args, **kw):
        if RemoteTorrentHandler.__single is None:
            RemoteTorrentHandler(*args, **kw)
        return RemoteTorrentHandler.__single
    getInstance = staticmethod(getInstance)

    def register(self,overlay_bridge,metadatahandler,session):
        self.overlay_bridge = overlay_bridge
        self.metadatahandler = metadatahandler
        self.session = session
        
        self.start()
    
    def download_torrent(self,permid,infohash,usercallback, prio = 1):
        """ The user has selected a torrent referred to by a peer in a query 
        reply. Try to obtain the actual .torrent file from the peer and then 
        start the actual download. 
        """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        
        
        self.callbacks[infohash] = usercallback
        self.sources.setdefault(infohash,[]).append(permid)
        self.requestedTorrents.put((prio, infohash))
        if DEBUG:
            print >>sys.stderr,'rtorrent: adding request:', infohash, permid
    
    def run(self):
        while True:
            try:
                prio, infohash = self.requestedTorrents.get()
                #do we still needs this infohash?
                while not infohash in self.callbacks: 
                    self.requestedTorrents.task_done()
                    prio, infohash = self.requestedTorrents.get()
                
                #CAUTION self.sources not threadsafe
                #Adding more than 1 thread would be unwise without adding locks
                
                #~load balance sources
                permid = choice(self.sources[infohash])
                self.sources[infohash].remove(permid)
                
                if DEBUG:
                    print >>sys.stderr,"rtorrent: requesting", infohash, permid 
                self.metadatahandler.send_metadata_request(permid, infohash, caller="rquery")
            
            except: #Make sure exceptions wont crash this requesting thread
                if DEBUG:
                    print_exc()
            
            if self.requestedTorrents.qsize() < 10 and prio > 1:
                sleep(SLEEP_BETWEEN_REQUESTS)
            else:
                sleep(SLEEP_BETWEEN_REQUESTS_TURBO)
    
    def metadatahandler_got_torrent(self,infohash,metadata,filename):
        """ Called by MetadataHandler when the requested torrent comes in """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)

        #Called by overlay thread
        if DEBUG:
            print >>sys.stderr,"rtorrent: got requested torrent from peer, wanted", infohash in self.callbacks
            
        if infohash in self.callbacks:
            usercallback = self.callbacks[infohash]
            del self.callbacks[infohash]
            del self.sources[infohash]
        
            remote_torrent_usercallback_lambda = lambda:usercallback(infohash,metadata,filename)
            self.session.uch.perform_usercallback(remote_torrent_usercallback_lambda)