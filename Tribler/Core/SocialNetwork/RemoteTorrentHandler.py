# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Handles the case where the user did a remote query and now selected one of the
# returned torrents for download. 
#

import sys
import Queue
import threading
import os
from traceback import print_exc
from time import sleep, time
from random import choice
from binascii import hexlify

from Tribler.Core.simpledefs import INFOHASH_LENGTH
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Core.TorrentDef import TorrentDef

SLEEP_BETWEEN_REQUESTS = 1
SLEEP_BETWEEN_REQUESTS_TURBO = 0.5
DEBUG = False

class RemoteTorrentHandler:
    
    __single = None
    
    def __init__(self):
        if RemoteTorrentHandler.__single:
            raise RuntimeError, "RemoteTorrentHandler is singleton"
        RemoteTorrentHandler.__single = self
        
        self.callbacks = {}
        self.requestedTorrents = {}
        self.requestingThreads = {}

    def getInstance(*args, **kw):
        if RemoteTorrentHandler.__single is None:
            RemoteTorrentHandler(*args, **kw)
        return RemoteTorrentHandler.__single
    getInstance = staticmethod(getInstance)

    def register(self,overlay_bridge,metadatahandler,session):
        self.overlay_bridge = overlay_bridge
        self.metadatahandler = metadatahandler
        self.session = session
    
    def download_torrent(self,permid,infohash,usercallback, prio = 1):
        """ The user has selected a torrent referred to by a peer in a query 
        reply. Try to obtain the actual .torrent file from the peer and then 
        start the actual download. 
        """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        
        self.callbacks[infohash] = usercallback
        
        if prio not in self.requestedTorrents:
            self.requestedTorrents[prio] = Queue.Queue()
            self.requestingThreads[prio] = TorrentRequester(self.metadatahandler, self.requestedTorrents[prio], 0.5 * prio)
            self.requestingThreads[prio].name = 'RemoteTorrentRequester %d'%prio
            self.requestingThreads[prio].start()
        
        self.requestingThreads[prio].add_source(infohash, permid)
        self.requestedTorrents[prio].put(infohash)
        
        if prio == 1:
            magnetTimer = threading.Timer(10, self.magnetTimeout, [infohash])
            magnetTimer.start()
            
        if DEBUG:
            print >>sys.stderr,'rtorrent: adding request:', bin2str(infohash), bin2str(permid), prio
    
    def magnetTimeout(self, *args):
        infohash = args[0]
        
        torrent_filename = os.path.join(self.metadatahandler.torrent_dir, get_collected_torrent_filename(infohash))
        if not os.path.isfile(torrent_filename):
            #.torrent still not found, try magnet link
            magnetlink = "magnet:?xt=urn:btih:" + hexlify(infohash)
            
            if DEBUG:
                print >> sys.stderr, 'rtorrent: trying magnet alternative', bin2str(infohash), magnetlink
                 
            def torrentdef_retrieved(tdef):
                if DEBUG:
                    print >> sys.stderr, 'rtorrent: received torrent using magnet', bin2str(infohash)

                tdef.save(torrent_filename)
                self.metadatahandler_got_torrent(infohash, tdef, torrent_filename)
                
            TorrentDef.retrieve_from_magnet(magnetlink, torrentdef_retrieved)
    
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
        
            remote_torrent_usercallback_lambda = lambda:usercallback(infohash,metadata,filename)
            self.session.uch.perform_usercallback(remote_torrent_usercallback_lambda)
            
            
class TorrentRequester(threading.Thread):
    
    def __init__(self, metadatahandler, queue, timeout):
        threading.Thread.__init__(self)
        
        self.metadatahandler = metadatahandler
        self.queue = queue
        self.timeout = timeout
        self.sources = {}
        
        self.daemon = True
    
    def add_source(self, infohash, permid):
        self.sources.setdefault(infohash, []).append(permid)
    
    def run(self):
        while True:
            infohash = self.queue.get()
            try:
                #~load balance sources
                permid = choice(self.sources[infohash])
                self.sources[infohash].remove(permid)
                
                if DEBUG:
                    print >>sys.stderr,"rtorrent: requesting", bin2str(infohash), bin2str(permid)
                
                #metadatahandler will only do actual request if torrentfile is not on disk
                self.metadatahandler.send_metadata_request(permid, infohash, caller="rquery")
            
            #Make sure exceptions wont crash this requesting thread
            except: 
                if DEBUG:
                    print_exc()
            
            self.queue.task_done()
            sleep(self.timeout)