# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Handles the case where the user did a remote query and now selected on of the
# returned torrents for download. 
#

import sys
from sets import Set

try:
    from Tribler.vwxGUI.GuiUtility import GUIUtility
    from Tribler.vwxGUI.torrentManager import TorrentDataManager
except ImportError:
    pass    #support cmdline version without wx

class RemoteTorrentHandler:
    
    __single = None
    
    def __init__(self):
        if RemoteTorrentHandler.__single:
            raise RuntimeError, "RemoteTorrentHandler is singleton"
        RemoteTorrentHandler.__single = self
        #self.torrent_db = SynTorrentDBHandler()
        self.requestedtorrents = Set()

    def getInstance(*args, **kw):
        if RemoteTorrentHandler.__single is None:
            RemoteTorrentHandler(*args, **kw)
        return RemoteTorrentHandler.__single
    getInstance = staticmethod(getInstance)


    def register(self,rawserver,metadatahandler):
        self.rawserver = rawserver
        self.metadatahandler = metadatahandler
    
    def download(self,torrent):
        """ Called by GUI thread """
        # The user has selected a torrent referred to by a peer in a query reply.
        # Try to obtain the actual .torrent file from the peer and then start
        # the actual download.
        #
        # NOTE: torrent not in DB
        #self.data_manager.setBelongsToMyDowloadHistory(torrent['infohash'], True)

        remote_torrent_download_func = lambda:self.downloadNetworkCallback(torrent)
        self.rawserver.add_task(remote_torrent_download_func,0)
        
    def downloadNetworkCallback(self,torrent):
        """ Called by network thread """
    
        permid = torrent['query_permid']
        infohash = torrent['infohash']
       
        #if infohash in self.requestedtorrents:
        #    return    # TODO RS:the previous request could have failed
       
        self.requestedtorrents.add(torrent['infohash'])
        self.metadatahandler.send_metadata_request(permid,infohash,caller="rquery")
       
       
    def got_torrent(self,torrent_hash,metadata):
       """ Called by network thread """
       
       #print "***** got remote, torrent", torrent_hash in self.requestedtorrents, self.requestedtorrents
       if torrent_hash not in self.requestedtorrents:
           return
       
       self.requestedtorrents.remove(torrent_hash)

       # torrent data manager should be initialized somewhere else first, 
       # this class' __init__ or register() would be the first, so we don't
       guiutil = GUIUtility.getInstance()
       data_manager = TorrentDataManager.getInstance()
       
       # It's now a normal torrent
       torrent = data_manager.getTorrent(torrent_hash)
       torrent['infohash'] = torrent_hash

       # Let GUI thread do the normal download stuff now
       stddetails = guiutil.standardDetails
       stddetails.invokeLater(stddetails.download,[torrent])
       