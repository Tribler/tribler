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

DEBUG = False

class RemoteTorrentHandler:
    
    __single = None
    
    def __init__(self):
        if RemoteTorrentHandler.__single:
            raise RuntimeError, "RemoteTorrentHandler is singleton"
        RemoteTorrentHandler.__single = self
        
        self.callbacks = {}
        self.requesters = {}
        self.registered = False

    def getInstance(*args, **kw):
        if RemoteTorrentHandler.__single is None:
            RemoteTorrentHandler(*args, **kw)
        return RemoteTorrentHandler.__single
    getInstance = staticmethod(getInstance)

    def register(self,overlay_bridge,metadatahandler,session):
        self.registered = True
        self.overlay_bridge = overlay_bridge
        self.metadatahandler = metadatahandler
        self.session = session
    
    def download_torrent(self,permid,infohash,usercallback, prio = 1):
        if self.registered:
            """ The user has selected a torrent referred to by a peer in a query 
            reply. Try to obtain the actual .torrent file from the peer and then 
            start the actual download. 
            """
            assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
            assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
            
            self.callbacks[infohash] = usercallback
            
            if prio not in self.requesters:
                self.requesters[prio] = TorrentRequester(self, self.metadatahandler, self.overlay_bridge, self.session, prio)
            
            self.requesters[prio].add_source(infohash, permid)
            
            if DEBUG:
                print >>sys.stderr,'rtorrent: adding request:', bin2str(infohash), bin2str(permid), prio
    
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
            
        for requester in self.requesters.values():
            if infohash in requester.sources:
                del requester.sources[infohash]
            if infohash in requester.nr_times_requested:
                del requester.nr_times_requested[infohash]
    
    def getQueueSize(self):
        nr_requests = 0
        nr_sources = 0
        for requester in self.requesters.values():
            nr_sources += len(requester.sources)
            for sources in requester.sources:
                nr_requests += len(sources)
        return nr_sources, nr_requests
            
class TorrentRequester():
    MAGNET_TIMEOUT = 5
    MAGNET_THRESHOLD = 5
    
    REQUEST_INTERVAL = 0.5
    
    def __init__(self, remoteTorrentHandler, metadatahandler, overlay_bridge, session, prio):
        self.magnet_requester = MagnetRequester.getInstance(metadatahandler, remoteTorrentHandler, overlay_bridge, session)
        
        self.remoteTorrentHandler = remoteTorrentHandler
        self.metadatahandler = metadatahandler
        self.overlay_bridge = overlay_bridge
        self.session = session
        self.prio = prio
        
        self.queue = Queue.Queue()
        self.sources = {}
        self.nr_times_requested = {}
    
    def add_source(self, infohash, permid):
        was_empty = self.queue.empty()
        self.queue.put(infohash)
        self.sources.setdefault(infohash, []).append(permid)
        
        if was_empty:
            self.overlay_bridge.add_task(self.doRequest, self.REQUEST_INTERVAL * self.prio, self)
    
    def doRequest(self):
        try:
            #request new infohash from queue
            while True:
                infohash = self.queue.get_nowait()
                
                if infohash in self.sources: #check if still needed
                    break
                else:
                    self.queue.task_done()
            
            try:
                #~load balance sources
                permid = choice(self.sources[infohash])
                self.sources[infohash].remove(permid)
                
                if len(self.sources[infohash]) < 1:
                    del self.sources[infohash]
                    
                self.nr_times_requested[infohash] = self.nr_times_requested.get(infohash, 0) + 1
                
                if DEBUG:
                    print >>sys.stderr,"rtorrent: requesting", bin2str(infohash), bin2str(permid)
                
                #metadatahandler will only do actual request if torrentfile is not on disk
                self.metadatahandler.send_metadata_request(permid, infohash, caller="rquery")
                
                #schedule a magnet lookup after X seconds
                if self.prio <= 1 or (self.nr_times_requested[infohash] > self.MAGNET_THRESHOLD and infohash not in self.sources):
                    self.overlay_bridge.add_task(lambda: self.magnet_requester.add_request(self.prio, infohash), self.MAGNET_TIMEOUT*(self.prio+1), infohash)

            #Make sure exceptions wont crash this requesting thread
            except: 
                if DEBUG:
                    print_exc()
            
            self.queue.task_done()
            self.overlay_bridge.add_task(self.doRequest, self.REQUEST_INTERVAL * self.prio, self)
            
        except Queue.Empty:
            pass

class MagnetRequester():
    MAX_CONCURRENT = 1
    REQUEST_INTERVAL = 1.0
    MAGNET_RETRIEVE_TIMEOUT = 30.0 
    
    __single = None
    
    def __init__(self, metadatahandler, remoteTorrentHandler, overlay_bridge, session):
        if MagnetRequester.__single:
            raise RuntimeError, "MagnetRequester is singleton"
        MagnetRequester.__single = self
        
        self.metadatahandler = metadatahandler
        self.remoteTorrentHandler = remoteTorrentHandler
        self.overlay_bridge = overlay_bridge
        self.session = session
        
        self.listLock = threading.RLock()
        self.list = []
        self.requestedInfohashes = set()
        
        if sys.platform == 'darwin':
            #mac has severe problems with closing connections, add additional time to allow it to close connections
            self.REQUEST_INTERVAL = 15

    def getInstance(*args, **kw):
        if MagnetRequester.__single is None:
            MagnetRequester(*args, **kw)
        return MagnetRequester.__single
    getInstance = staticmethod(getInstance)
    
    def add_request(self, prio, infohash):
        if DEBUG:
            print >> sys.stderr, "magnetrequestor: new magnet request", len(self.requestedInfohashes)
        
        self.listLock.acquire()
        self.list.append((prio, infohash))
        self.list.sort()
        self.listLock.release()
          
        if len(self.requestedInfohashes) < self.MAX_CONCURRENT:
            self.overlay_bridge.add_task(self.__requestMagnet, 0) #do new request now
            
    def __requestMagnet(self):
        self.listLock.acquire()
        try:
            if len(self.requestedInfohashes) < self.MAX_CONCURRENT:
                #request new infohash from queue
                while True:
                    if len(self.list) == 0:
                            return
                    prio, infohash = self.list.pop(0)
                    torrent_filename = os.path.join(self.metadatahandler.torrent_dir, get_collected_torrent_filename(infohash))
                    
                    if infohash in self.requestedInfohashes:
                        if DEBUG:
                            print >> sys.stderr, 'magnetrequester: magnet already requested', bin2str(infohash)
                    elif os.path.isfile(torrent_filename):
                        if DEBUG:
                            print >> sys.stderr, 'magnetrequester: magnet already on disk', bin2str(infohash)
                    else:
                        break
            else: #requesting max_concurrent
                return
        except:
            print_exc()
        finally:
            self.listLock.release()
        
        #try magnet link
        magnetlink = "magnet:?xt=urn:btih:" + hexlify(infohash)
        if DEBUG:
            print >> sys.stderr, 'magnetrequester: requesting magnet', bin2str(infohash), prio, magnetlink
        
        self.requestedInfohashes.add(infohash)
        TorrentDef.retrieve_from_magnet(magnetlink, self.__torrentdef_retrieved, self.MAGNET_RETRIEVE_TIMEOUT)
        self.overlay_bridge.add_task(lambda: self.__torrentdef_failed(infohash), self.MAGNET_RETRIEVE_TIMEOUT, infohash)
        
        if len(self.requestedInfohashes) < self.MAX_CONCURRENT:
            self.overlay_bridge.add_task(self.__requestMagnet, self.REQUEST_INTERVAL)
    
    def __torrentdef_retrieved(self, tdef):
        infohash = tdef.get_infohash()
        if DEBUG:
            print >> sys.stderr, 'magnetrequester: received torrent', bin2str(infohash)
        
        #remove from requested list
        if infohash in self.requestedInfohashes:
            self.requestedInfohashes.remove(infohash)
        
            #save torrent
            torrent_filename = os.path.join(self.metadatahandler.torrent_dir, get_collected_torrent_filename(infohash))
            tdef.save(torrent_filename)
            
            #add this new torrent to db
            torrent_db = self.session.open_dbhandler('torrents')
            torrent_db.addExternalTorrent(tdef)
            
            #notify all
            self.remoteTorrentHandler.metadatahandler_got_torrent(infohash, tdef, torrent_filename)
            self.overlay_bridge.add_task(self.__requestMagnet, self.REQUEST_INTERVAL)
    
    def __torrentdef_failed(self, infohash):
        if infohash in self.requestedInfohashes: #did we retrieve it allready?
            self.requestedInfohashes.remove(infohash)
            self.overlay_bridge.add_task(self.__requestMagnet, self.REQUEST_INTERVAL)