# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Handles the case where the user did a remote query and now selected one of the
# returned torrents for download. 
#

import sys

from Tribler.Core.simpledefs import INFOHASH_LENGTH
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler

DEBUG = False

class RemoteTorrentHandler:
    
    __single = None
    
    def __init__(self):
        if RemoteTorrentHandler.__single:
            raise RuntimeError, "RemoteTorrentHandler is singleton"
        RemoteTorrentHandler.__single = self
        self.torrent_db = TorrentDBHandler.getInstance()
        self.requestedtorrents = {}

    def getInstance(*args, **kw):
        if RemoteTorrentHandler.__single is None:
            RemoteTorrentHandler(*args, **kw)
        return RemoteTorrentHandler.__single
    getInstance = staticmethod(getInstance)


    def register(self,overlay_bridge,metadatahandler,session):
        self.overlay_bridge = overlay_bridge
        self.metadatahandler = metadatahandler
        self.session = session
    
    def download_torrent(self,permid,infohash,usercallback):
        """ The user has selected a torrent referred to by a peer in a query 
        reply. Try to obtain the actual .torrent file from the peer and then 
        start the actual download. 
        """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        # Called by GUI thread 

        olthread_remote_torrent_download_lambda = lambda:self.olthread_download_torrent_callback(permid,infohash,usercallback)
        self.overlay_bridge.add_task(olthread_remote_torrent_download_lambda,0)
        
    def olthread_download_torrent_callback(self,permid,infohash,usercallback):
        """ Called by overlay thread """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
    
        #if infohash in self.requestedtorrents:
        #    return    # TODO RS:the previous request could have failed
              
        self.requestedtorrents[infohash] = usercallback
        
        self.metadatahandler.send_metadata_request(permid,infohash,caller="rquery")
        if DEBUG:
            print >>sys.stderr,'rtorrent: download: Requested torrent: %s' % `infohash`
       
    def metadatahandler_got_torrent(self,infohash,metadata,filename):
        """ Called by MetadataHandler when the requested torrent comes in """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)

        #Called by overlay thread

        if DEBUG:
            print >>sys.stderr,"rtorrent: got requested torrent from peer, wanted", infohash in self.requestedtorrents, `self.requestedtorrents`
        if infohash not in self.requestedtorrents:
           return

        usercallback = self.requestedtorrents[infohash]
        del self.requestedtorrents[infohash]
        
        remote_torrent_usercallback_lambda = lambda:usercallback(infohash,metadata,filename)
        self.session.uch.perform_usercallback(remote_torrent_usercallback_lambda)
