# Written by George Milescu
# see LICENSE.txt for license information
#
# SecureOverlay message handler for the Proxy
#

import sys, os
import binascii
from threading import Lock
from time import sleep

from Tribler.Core.TorrentDef import *
from Tribler.Core.Session import *
from Tribler.Core.simpledefs import *
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.CacheDB.CacheDBHandler import PeerDBHandler, TorrentDBHandler
from Tribler.Core.BitTornado.BT1.convert import tobinary,toint

from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.ProxyService.ProxyDownloader import ProxyDownloader

DEBUG = False

class ProxyMessageHandler:
    def __init__(self):
        self.metadata_queue = {}
        self.metadata_queue_lock = Lock()
        self.overlay_bridge = OverlayThreadingBridge.getInstance()
        # active_reauests is a dictionary storing al permids asking for relay
        # until the download object is created. The dictionary keys are infohashes,
        # and the values are lists of permids
        self.active_requests = {}
        self.session= None

    def register(self, session, metadata_handler, proxydir, dlconfig):
        """ Called from OverlayApps.py:166
        """
        self.session = session
        self.proxydir = proxydir
        
        # The default DownloadStartupConfig dict as set in the Session
        self.dlconfig = dlconfig

        self.metadata_handler = metadata_handler
        self.torrent_db = TorrentDBHandler.getInstance()


    def handleMessage(self, permid, selversion, message):
        """ Handle the received message and call the appropriate function to solve it.
        
        As there are multiple proxy instances, one for each download/upload, the right
        proxy instance must be found prior to making a call to it's methods.
            
        @param permid: The permid of the peer who sent the message
        @param selversion: selected Overlay protocol version
        @param message: The message received
        """

        t = message[0]
        if DEBUG:
            print >> sys.stderr, "proxy: received the message", getMessageName(t), "from", show_permid_short(permid)

        #if ProxyService is not turned on, ignore message and return
        session_config = self.session.get_current_startup_config_copy()
        if session_config.get_proxyservice_status() == PROXYSERVICE_OFF:
            if DEBUG:
                print >> sys.stderr, "proxy: ProxyService not active, ignoring message"
            return
        
        if t == RELAY_REQUEST:
            return self.got_relay_request(permid, message, selversion)
        elif t == STOP_RELAYING:
            return self.got_stop_relaying(permid, message, selversion)
        elif t == DOWNLOAD_PIECE:
            return self.got_download_piece(permid, message, selversion)
        elif t == CANCEL_DOWNLOADING_PIECE:
            return self.got_cancel_downloading_piece(permid, message, selversion)
        elif t == UPLOAD_PIECE:
            return self.got_upload_piece(permid, message, selversion)
        elif t == CANCEL_UPLOADING_PIECE:
            return self.got_cancel_uploading_piece(permid, message, selversion)


    def got_relay_request(self, permid, message, selversion):
        """ Handle the RELAY_REQUEST message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """
        try:
            infohash = message[1:21]
        except:
            if DEBUG:
                print >> sys.stderr, "proxy: got_relay_request: bad data in RELAY_REQUEST"
            return False

        if len(infohash) != 20:
            if DEBUG:
                print >> sys.stderr, "proxy: got_relay_request: bad infohash in RELAY_REQUEST"
            return False
        
        if DEBUG:
            print >> sys.stderr, "proxy: got_relay_request: received a relay request from", show_permid_short(permid), "for infohash", infohash.encode("HEX") 
        
        # ProxyService 90s Test_
        if infohash.encode("HEX") != "eea87c6d4b3bb067909be7afbba12c525baa5efd":
            if DEBUG:
                print >> sys.stderr, "proxy: Will not relay this infohash"
            return False
        # _ProxyService 90s Test
        
        # Evaluate if there is enough proxy capability. If the current node does not have enough
        # resources to share to the ProxyService, don't start a new download
        if not self.can_relay(infohash):
            return False
        
        # Find the appropriate proxy object. If no proxy object is associated with the requested infohash, than start a new download for it
        proxy_obj = self.session.lm.get_proxyservice_object(infohash, PROXYSERVICE_PROXY_OBJECT)
        if proxy_obj is None:
            if DEBUG:
                print >> sys.stderr, "proxy: got_relay_request: There is no current download for this infohash. A new download will be started."
            
            if infohash in self.active_requests.keys():
                self.active_requests[infohash].append(permid)
            else:
                self.active_requests[infohash]= [permid]
            
            # start_proxy_download will make, indirectly, a call to the network_got_relay_request method of the proxy,
            # in a similar fashion as the one below
            self.start_proxy_download(permid, infohash, selversion)
            return
            
        # Call the proxy object got_relay_request method
        # If the object was created with start_proxy_download, an amount of time is required
        # before the download is fully operational, so the call to the the proxy object got_relay_request method
        # is made using the network thread (the network thread executes tasks sequentially, so the start_download task should
        # be executed before the network_got_relay_request)
        network_got_relay_request_lambda = lambda:self.network_got_relay_request([permid], infohash)
        self.session.lm.rawserver.add_task(network_got_relay_request_lambda, 0)
        
        return True

    def network_got_relay_request(self, permid_list, infohash):
        """ Find the appropriate proxy object and call it's method. If no proxy object is associated with the requested
        infohash, than return
        
        Executed by the network thread.
        
        @param permid_list: A list of permids of the peers who sent the message
        @param infohash: The infohash sent by the remote peer
        """
        
        proxy_obj = self.session.lm.get_proxyservice_object(infohash, PROXYSERVICE_PROXY_OBJECT)
        if proxy_obj is None:
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_relay_request: There is no current download for this infohash. Try again later..."
            return
            
        for permid in permid_list:
            proxy_obj.got_relay_request(permid, infohash)
        
    def start_proxy_download(self, permid, infohash, selversion):
        """ Start a new download, as a proxy, for the requested infohash
        
        @param permid: The permid of the peer who sent the message
        @param infohash: the infohash of the .torrent
        @param selversion: selected Overlay protocol version 
        """
        
        # Getting .torrent information
        torrent_data = self.find_torrent(infohash)
        if torrent_data:
            # The .torrent was already in the local cache
            self.new_download(permid, infohash, torrent_data)
        else:
            # The .torrent needs to be downloaded
            # new_download will be called at the end of get_torrent_metadata
            self.get_torrent_metadata(permid, infohash, selversion)

    # It is very important here that we create safe filenames, i.e., it should
    # not be possible for a doe to send a METADATA message that causes
    # important files to be overwritten
    #
    def new_download(self, permid, infohash, torrent_data):
        """ Start a new download in order to get the pieces that will be requested by the doe.
        After the download is started, find the appropriate proxy object and call it's method.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: the infohash of the torrent for which relay is requested
        @param torrent_data: the content of the .torrent file
        """        

        # Create the name for the .torrent file in the proxy cache
        basename = binascii.hexlify(infohash)+'.torrent'
        torrentfilename = os.path.join(self.proxydir,basename)

        # Write the .torrent information in the .torrent proxy cache file 
        tfile = open(torrentfilename, "wb")
        tfile.write(torrent_data)
        tfile.close()

        if DEBUG:
            print >> sys.stderr, "proxy: new_download: Got metadata required for relaying"
            print >> sys.stderr, "proxy: new_download: torrent: ", torrentfilename

        tdef = TorrentDef.load(torrentfilename)
        if self.dlconfig is None:
            dscfg = DownloadStartupConfig()
        else:
            dscfg = DownloadStartupConfig(self.dlconfig)
        dscfg.set_proxyservice_role(PROXYSERVICE_ROLE_PROXY)
        dscfg.set_dest_dir(self.proxydir)
        dscfg.set_doe_mode(DOE_MODE_OFF) # a proxy does not use other proxies for downloading data in the current stage

        # Start new download
        if DEBUG:
            print >> sys.stderr, "proxy: new_download: Starting a new download"

        self.session.add_observer(self.proxydownloader_started, NTFY_PROXYDOWNLOADER, [NTFY_STARTED])

        d = self.session.start_download(tdef, dscfg)
        d.set_state_callback(self.state_callback, getpeerlist=False)
        

    def proxydownloader_started(self, subject, changeType, objectID, *args):
        """  Handler registered with the session observer
        
        @param subject The subject to observe, one of NTFY_* subjects (see simpledefs).
        @param changeTypes The list of events to be notified of one of NTFY_* events.
        @param objectID The specific object in the subject to monitor (e.g. a specific primary key in a database to monitor for updates.)
        @param args: A list of optional arguments.
        """

        if DEBUG:
            print >>sys.stderr, "proxy: proxydownloader_started"

        # Call the proxy object got_relay_request method
        # If the object was created with start_proxy_download, an amount of time is required
        # before the download is fully operational, so the call to the the proxy object got_relay_request method
        # is made using the network thread (the network thread executes tasks sequentially, so the start_download task should
        # be executed before the network_got_relay_request)
        
        self.session.remove_observer(self.proxydownloader_started)

        infohash=args[0]
        permid_list=self.active_requests[infohash]
        del(self.active_requests[infohash])
        
        network_got_relay_request_lambda = lambda:self.network_got_relay_request(permid_list, infohash)
        self.session.lm.rawserver.add_task(network_got_relay_request_lambda, 0)
        
    def state_callback(self, ds):
        # Print download statistics
        d = ds.get_download()
        print >>sys.stderr, '%s %s %5.2f%% %s up %8.2fKB/s down %8.2fKB/s' % \
                (d.get_def().get_name(), \
                dlstatus_strings[ds.get_status()], \
                ds.get_progress() * 100, \
                ds.get_error(), \
                ds.get_current_speed(UPLOAD), \
                ds.get_current_speed(DOWNLOAD))
    
        return (1.0, False)

    def get_torrent_metadata(self, permid, infohash, selversion):
        """ Get the .torrent file from the doe requesting relaying for it
        
        @param permid: the permid of the doe
        @param infihash: the infohash of the .torrent
        @param selversion: selected Overlay protocol version
        """
        if DEBUG:
            print >> sys.stderr, "proxy: get_torrent_metadata: Asking doe for the .torrent"

        self.metadata_queue_lock.acquire()
        try:
            if not self.metadata_queue.has_key(infohash):
                self.metadata_queue[infohash] = []
            self.metadata_queue[infohash].append(permid)
        finally:
            self.metadata_queue_lock.release()
        
        self.metadata_handler.send_metadata_request(permid, infohash, selversion, caller="proxyservice")

    def metadatahandler_received_torrent(self, infohash, torrent_data):
        """ The doe sent the .torrent file.
        
        Called from MetadataHandler.notify_torrent_is_in()
        """
        if DEBUG:
            print >> sys.stderr, "proxy: metadatahandler_received_torrent: the .torrent is in."
        
        self.metadata_queue_lock.acquire()
        try:
            if not self.metadata_queue.has_key(infohash) or not self.metadata_queue[infohash]:
                if DEBUG:
                    print >> sys.stderr, "proxy: metadatahandler_received_torrent: a .torrent was received that we are not waiting for."
                return
            
            infohash_queue = self.metadata_queue[infohash]
            del self.metadata_queue[infohash]

            for permid in infohash_queue:
                # only ask for metadata once
                self.new_download(permid, infohash, torrent_data)
        finally:
            self.metadata_queue_lock.release()

    def find_torrent(self, infohash):
        """ Find the .torrent for the required infohash.
        
        @param infohash: the infohash of the .torrent that must be returned 
        """
        torrent = self.torrent_db.getTorrent(infohash)
        if torrent is None:
            # The .torrent file is not in the local cache
            if DEBUG:
                print >> sys.stderr, "proxy: find_torrent: The .torrent file is not in the local cache"
            return None
        elif 'torrent_dir' in torrent:
            fn = torrent['torrent_dir']
            if os.path.isfile(fn):
                f = open(fn,"rb")
                data = f.read()
                f.close()
                return data
            else:
                # The .torrent file path does not exist or the path is not for a file
                if DEBUG:
                    print >> sys.stderr, "proxy: find_torrent: The .torrent file path does not exist or the path is not for a file" 
                return None
        else:
            # The torrent dictionary does not contain a torrent_dir field 
            if DEBUG:
                print >> sys.stderr, "proxy: find_torrent: The torrent dictionary does not contain a torrent_dir field" 
            return None

    def can_relay(self, infohash):
        """ Decide if the current node has relay capacity available
        
        @param infohash: the infohash of the torrent for which relay is requested 
        """
        # the session was not completely initialized         
        if self.session is None:
            return False
        
        if self.session.get_proxyservice_status() == PROXYSERVICE_ON:
            return True
        
        # TODO:
        return False


    def got_stop_relaying(self, permid, message, selversion):
        """ Handle the STOP_RELAYING message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """
        try:
            infohash = message[1:21]
        except:
            if DEBUG:
                print >> sys.stderr, "proxy: got_stop_relaying: bad data in STOP_RELAYING"
            return False

        if len(infohash) != 20:
            if DEBUG:
                print >> sys.stderr, "proxy: got_stop_relaying: bad infohash in STOP_RELAYING"
            return False

        network_got_stop_relaying_lambda = lambda:self.network_got_stop_relaying(permid, infohash, selversion)
        self.session.lm.rawserver.add_task(network_got_stop_relaying_lambda, 0)
        
        # If the request is from a unauthorized peer, we close
        # If the request is from an authorized peer (=doe) we close as well. So return False
        return False

    def network_got_stop_relaying(self, permid, infohash, selversion):
        """ Find the appropriate proxy object and call it's method.
        
        Called by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        """
        proxy_obj = self.session.lm.get_proxyservice_object(infohash, PROXYSERVICE_PROXY_OBJECT)
        if proxy_obj is None:
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_stop_relaying: There is no proxy object associated with this infohash"
            return
        
        if not proxy_obj.is_doe(permid): 
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_stop_relaying: The node asking to stop relaying is not the current doe"
            return
        
        proxy_obj.got_stop_relaying(permid, infohash)

        # TODO: if the last doe cancelled the relay, remove the download 
        # Find and remove download
        dlist = self.session.get_downloads()
        for d in dlist:
            if d.get_def().get_infohash() == infohash:
                self.session.remove_download(d)
                break


    def got_download_piece(self, permid, message, selversion):
        """ Handle the DOWNLOAD_PIECE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """
        try:
            infohash = message[1:21]
            piece = toint(message[21:25])
        except:
            print >> sys.stderr, "proxy: got_download_piece: bad data in DOWNLOAD_PIECE"
            return False

        network_got_download_piece_lambda = lambda:self.network_got_download_piece(permid, selversion, infohash, piece)
        self.session.lm.rawserver.add_task(network_got_download_piece_lambda, 0)
        
        return True

    def network_got_download_piece(self, permid, selversion, infohash, piece):
        """ Find the appropriate proxy object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        @param piece: the number of the piece to be downloaded
        """
        proxy_obj = self.session.lm.get_proxyservice_object(infohash, PROXYSERVICE_PROXY_OBJECT)
        if proxy_obj is None:
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_download_piece: There is no proxy object associated with this infohash"
            return

        if not proxy_obj.is_doe(permid): 
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_download_piece: The node asking for relaying is not the current doe"
            return

        proxy_obj.got_download_piece(permid, piece)


    def got_cancel_downloading_piece(self, permid, message, selversion):
        """ Handle the CANCEL_DOWNLOADING_PIECE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """
        try:
            infohash = message[1:21]
            piece = toint(message[21:25])
        except:
            print >> sys.stderr, "proxy: got_cancel_downloading_piece: bad data in CANCEL_DOWNLOADING_PIECE"
            return False

        network_got_cancel_downloading_piece_lambda = lambda:self.network_got_cancel_downloading_piece(permid, selversion, infohash, piece)
        self.session.lm.rawserver.add_task(network_got_cancel_downloading_piece_lambda, 0)
        
        return True

    def network_got_cancel_downloading_piece(self, permid, selversion, infohash, piece):
        """ Find the appropriate proxy object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        @param piece: the number of the piece to be cancelled
        """
        proxy_obj = self.session.lm.get_proxyservice_object(infohash, PROXYSERVICE_PROXY_OBJECT)
        if proxy_obj is None:
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_cancel_downloading_piece: There is no proxy object associated with this infohash"
            return

        if not proxy_obj.is_doe(permid): 
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_cancel_downloading_piece: The node asking for relaying is not the current doe"
            return

        proxy_obj.got_cancel_downloading_piece(permid, piece)
        
        
    def got_upload_piece(self, permid, message, selversion):
        """ Handle the UPLOAD_PIECE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """
        try:
            infohash = message[1:21]
            piece_number = toint(message[21:25])
            piece_data = message[25:]
        except:
            print >> sys.stderr, "proxy: got_upload_piece: bad data in UPLOAD_PIECE"
            return False
        # TODO: rename all piece in piece_number
        network_got_upload_piece_lambda = lambda:self.network_got_upload_piece(permid, selversion, infohash, piece_number, piece_data)
        self.session.lm.rawserver.add_task(network_got_upload_piece_lambda, 0)
        
        return True

    def network_got_upload_piece(self, permid, selversion, infohash, piece_number, piece_data):
        """ Find the appropriate proxy object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        @param piece: the number of the piece to be uploaded
        """
        proxy_obj = self.session.lm.get_proxyservice_object(infohash, PROXYSERVICE_PROXY_OBJECT)
        if proxy_obj is None:
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_upload_piece: There is no proxy object associated with this infohash"
            return

        if not proxy_obj.is_doe(permid): 
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_upload_piece: The node asking for relaying is not the current doe"
            return

        proxy_obj.got_upload_piece(permid, piece_number, piece_data)


    def got_cancel_uploading_piece(self, permid, message, selversion):
        """ Handle the CANCEL_UPLOADING_PIECE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """
        try:
            infohash = message[1:21]
            piece = toint(message[21:25])
        except:
            print >> sys.stderr, "proxy: got_cancel_uploading_piece: bad data in CANCEL_UPLOADING_PIECE"
            return False

        network_got_cancel_uploading_piece_lambda = lambda:self.network_got_cancel_uploading_piece(permid, selversion, infohash, piece)
        self.session.lm.rawserver.add_task(network_got_cancel_uploading_piece_lambda, 0)
        
        return True

    def network_got_cancel_uploading_piece(self, permid, selversion, infohash, piece):
        """ Find the appropriate proxy object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        @param piece: the number of the piece to be cancelled
        """
        proxy_obj = self.session.lm.get_proxyservice_object(infohash, PROXYSERVICE_PROXY_OBJECT)
        if proxy_obj is None:
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_cancel_uploading_piece: There is no proxy object associated with this infohash"
            return

        if not proxy_obj.is_doe(permid): 
            if DEBUG:
                print >> sys.stderr, "proxy: network_got_cancel_uploading_piece: The node asking for relaying is not the current doe"
            return

        proxy_obj.got_cancel_uploading_piece(permid, piece)
