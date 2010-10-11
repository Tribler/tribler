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

from Tribler.Core.simpledefs import INFOHASH_LENGTH
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler

SLEEP_BETWEEN_REQUESTS = 1
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
        
        self.requestedTorrents = Queue.PriorityQueue()
        self.callbacks = {}

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
    
    def download_torrent(self,permid,infohash,usercallback):
        """ The user has selected a torrent referred to by a peer in a query 
        reply. Try to obtain the actual .torrent file from the peer and then 
        start the actual download. 
        """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        
        if infohash not in self.callbacks:
            self.requestedTorrents.put((1, permid, infohash)) #new torrents are requested with prio 1
        else:
            self.requestedTorrents.put((2, permid, infohash)) #request has been made, request with prio 2
        self.callbacks[infohash] = usercallback
        if DEBUG:
            print >>sys.stderr,'rtorrent: download: Requested torrent: %s' % `infohash`
    
    def run(self):
        while True:
            _, permid, infohash = self.requestedTorrents.get()
            
            while not infohash in self.callbacks:
                self.requestedTorrents.task_done()
                _, permid, infohash = self.requestedTorrents.get()
                
            if DEBUG:
                print >>sys.stderr,"rtorrent: requesting %s"%infohash 
            self.metadatahandler.send_metadata_request(permid,infohash,caller="rquery")
            sleep(SLEEP_BETWEEN_REQUESTS)
    
    def metadatahandler_got_torrent(self,infohash,metadata,filename):
        """ Called by MetadataHandler when the requested torrent comes in """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)

        #Called by overlay thread
        if DEBUG:
            print >>sys.stderr,"rtorrent: got requested torrent from peer, wanted", infohash in self.callbacks, `self.callbacks`
            
        if infohash not in self.callbacks:
           return

        usercallback = self.callbacks[infohash]
        del self.callbacks[infohash]
        
        remote_torrent_usercallback_lambda = lambda:usercallback(infohash,metadata,filename)
        self.session.uch.perform_usercallback(remote_torrent_usercallback_lambda)