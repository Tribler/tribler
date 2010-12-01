# Written by Pawel Garbacki, Arno Bakker, George Milescu
# see LICENSE.txt for license information
#
# SecureOverlay message handler for a Helper
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

from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge

DEBUG = False

class HelperMessageHandler:
    def __init__(self):
        self.metadata_queue = {}
        self.metadata_queue_lock = Lock()
        self.overlay_bridge = OverlayThreadingBridge.getInstance()
        self.received_challenges = {}

    def register(self,session,metadata_handler,helpdir,dlconfig):
        self.session = session
        self.helpdir = helpdir
        # The default DownloadStartupConfig dict as set in the Session
        self.dlconfig = dlconfig

        self.metadata_handler = metadata_handler
        self.torrent_db = TorrentDBHandler.getInstance()

    def handleMessage(self,permid,selversion,message):
        """ Handle the received message and call the appropriate function to solve it.
        
        As there are multiple helper instances, one for each download/upload, the right helper instance must be found prior to making a call to it's methods.
            
        @param permid: The permid of the peer who sent the message
        @param selversion:
        @param message: The message received
        """

        t = message[0]
        if DEBUG:
            print >> sys.stderr, "helper: received the message", getMessageName(t), "from", show_permid_short(permid)

        #if ProxyService is not turned on, return
        session_config = self.session.get_current_startup_config_copy()
        if session_config.get_proxyservice_status() == PROXYSERVICE_OFF:
            if DEBUG:
                print >> sys.stderr, "helper: ProxyService not active, ignoring message"

            return
        
        if t == ASK_FOR_HELP:
            return self.got_ask_for_help(permid, message, selversion)
        elif t == STOP_HELPING:
            return self.got_stop_helping(permid, message, selversion)
        elif t == REQUEST_PIECES:
            return self.got_request_pieces(permid, message, selversion)





    def got_ask_for_help(self, permid, message, selversion):
        """ Handle the ASK_FOR_HELP message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion:
        """
        try:
            infohash = message[1:21]
            challenge = bdecode(message[21:])
        except:
            if DEBUG:
                print >> sys.stderr, "helper: got_ask_for_help: bad data in ask_for_help"
            return False

        if len(infohash) != 20:
            if DEBUG:
                print >> sys.stderr, "helper: got_ask_for_help: bad infohash in ask_for_help"
            return False
        
        if DEBUG:
            print >> sys.stderr, "helper: got_ask_for_help: received a help request from",show_permid_short(permid)

        
        # Save the challenge
        self.received_challenges[permid] = challenge
        
        # Find the appropriate Helper object. If no helper object is associated with the requested infohash, than start a new download for it
        helper_obj = self.session.lm.get_coopdl_role_object(infohash, COOPDL_ROLE_HELPER)
        if helper_obj is None:
            if DEBUG:
                print >> sys.stderr, "helper: got_ask_for_help: There is no current download for this infohash. A new download must be started."
            
            self.start_helper_download(permid, infohash, selversion)
            # start_helper_download will make, indirectly, a call to the network_got_ask_for_help method of the helper,
            # in a similar fashion as the one below
            return
            
        # Call the helper object got_ask_for_help method
        # If the object was created with start_helepr_download, an amount of time is required
        # before the download is fully operational, so the call to the the helper object got_ask_for_help method
        # is made using the network thread (the network thread executes tasks sequentially, so the start_download task should
        # be executed before the network_got_ask_for_help)
        network_got_ask_for_help_lambda = lambda:self.network_got_ask_for_help(permid, infohash)
        self.session.lm.rawserver.add_task(network_got_ask_for_help_lambda, 0)
        
        return True


    def network_got_ask_for_help(self, permid, infohash):
        """ Find the appropriate Helper object and call it's method. If no helper object is associated with the requested
        infohash, than start a new download for it
        
        Called by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param challenge: The challenge sent by the coordinator
        """
        
        helper_obj = self.session.lm.get_coopdl_role_object(infohash, COOPDL_ROLE_HELPER)
        if helper_obj is None:
            if DEBUG:
                print >> sys.stderr, "helper: network_got_ask_for_help: There is no current download for this infohash. Try again later..."
            return
            
        # At this point, a previous download existed
        # A node can not be a helper and a coordinator at the same time
        if not helper_obj.is_coordinator(permid):
            if DEBUG:
                print >> sys.stderr, "helper: network_got_ask_for_help: The node asking for help is not the current coordinator"
            #return

        # Retrieve challenge
        challenge = self.received_challenges[permid]
        helper_obj.got_ask_for_help(permid, infohash, challenge)
        # Wake up download thread
        helper_obj.notify()
        

    def start_helper_download(self, permid, infohash, selversion):
        """ Start a new download, as a helper, for the requested infohash
        
        @param permid: the coordinator permid requesting help
        @param infohash: the infohash of the .torrent
        @param selversion: 
        @param challenge: The challenge sent by the coordinator
        """
        
        # Getting .torrent information
        torrent_data = self.find_torrent(infohash)
        if torrent_data:
            # The .torrent was already in the local cache
            self.new_download(infohash, torrent_data, permid)
        else:
            # The .torrent needs to be downloaded
            # new_download will be called at the end of get_torrent_metadata
            self.get_torrent_metadata(permid, infohash, selversion)


    # It is very important here that we create safe filenames, i.e., it should
    # not be possible for a coordinator to send a METADATA message that causes
    # important files to be overwritten
    #
    def new_download(self, infohash, torrent_data, permid):
        """ Start a new download in order to get the pieces that will be requested by the coordinator.
        After the download is started, find the appropriate Helper object and call it's method.
        
        @param infohash: the infohash of the torrent for which help is requested
        @param torrent_data: the content of the .torrent file
        @param permid: the permid of the coordonator
        @param challenge: The challenge sent by the coordinator
        """        

        # Create the name for the .torrent file in the helper cache
        basename = binascii.hexlify(infohash)+'.torrent' # ignore .tribe stuff, not vital
        torrentfilename = os.path.join(self.helpdir,basename)

        # Write the .torrent information in the .torrent helper cache file 
        tfile = open(torrentfilename, "wb")
        tfile.write(torrent_data)
        tfile.close()

        if DEBUG:
            print >> sys.stderr, "helper: new_download: Got metadata required for helping",show_permid_short(permid)
            print >> sys.stderr, "helper: new_download: torrent: ",torrentfilename

        tdef = TorrentDef.load(torrentfilename)
        if self.dlconfig is None:
            dscfg = DownloadStartupConfig()
        else:
            dscfg = DownloadStartupConfig(self.dlconfig)
        dscfg.set_coopdl_coordinator_permid(permid)
        dscfg.set_dest_dir(self.helpdir)
        dscfg.set_proxy_mode(PROXY_MODE_OFF) # a helper does not use other helpers for downloading data

        # Start new download
        if DEBUG:
            print >> sys.stderr, "helper: new_download: Starting a new download"
        d=self.session.start_download(tdef,dscfg)
        d.set_state_callback(self.state_callback, getpeerlist=False)
        
        # Call the helper object got_ask_for_help method
        # If the object was created with start_helepr_download, an amount of time is required
        # before the download is fully operational, so the call to the the helper object got_ask_for_help method
        # is made using the network thread (the network thread executes tasks sequentially, so the start_download task should
        # be executed before the network_got_ask_for_help)
        network_got_ask_for_help_lambda = lambda:self.network_got_ask_for_help(permid, infohash)
        self.session.lm.rawserver.add_task(network_got_ask_for_help_lambda, 0)

    # Print torrent statistics
    def state_callback(self, ds):
        d = ds.get_download()
    #    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)
        print >>sys.stderr, '%s %s %5.2f%% %s up %8.2fKB/s down %8.2fKB/s' % \
                (d.get_def().get_name(), \
                dlstatus_strings[ds.get_status()], \
                ds.get_progress() * 100, \
                ds.get_error(), \
                ds.get_current_speed(UPLOAD), \
                ds.get_current_speed(DOWNLOAD))
    
        return (1.0, False)




    def get_torrent_metadata(self, permid, infohash, selversion):
        """ Get the .torrent file from the coordinator requesting help for it
        
        @param permid: the permid of the coordinator
        @param infihash: the infohash of the .torrent
        @param selversion:
        """
        if DEBUG:
            print >> sys.stderr, "helper: get_torrent_metadata: Asking coordinator for the .torrent"
        self.metadata_queue_lock.acquire()
        try:
            if not self.metadata_queue.has_key(infohash):
                self.metadata_queue[infohash] = []
            self.metadata_queue[infohash].append(permid)
        finally:
            self.metadata_queue_lock.release()
        
        self.metadata_handler.send_metadata_request(permid, infohash, selversion, caller="dlhelp")


    def metadatahandler_received_torrent(self, infohash, torrent_data):
        """ The coordinator sent the .torrent file.
        """
        # TODO: Where is this handler registered ?
        # TODO: Is this handler actually called by the network thread ?
        if DEBUG:
            print >> sys.stderr, "helper: metadatahandler_received_torrent: the .torrent is in."
        
        self.metadata_queue_lock.acquire()
        try:
            if not self.metadata_queue.has_key(infohash) or not self.metadata_queue[infohash]:
                if DEBUG:
                    print >> sys.stderr, "helper: metadatahandler_received_torrent: a .torrent was received that we are not waiting for."
                return
            
            infohash_queue = self.metadata_queue[infohash]
            del self.metadata_queue[infohash]

            for permid in infohash_queue:
                # only ask for metadata once
                self.new_download(infohash, torrent_data, permid)
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
                print >> sys.stderr, "helper: find_torrent: The .torrent file is not in the local cache"
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
                    print >> sys.stderr, "helper: find_torrent: The .torrent file path does not exist or the path is not for a file" 
                return None
        else:
            # The torrent dictionary does not contain a torrent_dir field 
            if DEBUG:
                print >> sys.stderr, "helper: find_torrent: The torrent dictionary does not contain a torrent_dir field" 
            return None





    def got_stop_helping(self, permid, message, selversion):
        """ Handle the STOP_HELPING message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion:
        """
        try:
            infohash = message[1:]
        except:
            if DEBUG:
                print >> sys.stderr, "helper: got_stop_helping: bad data in STOP_HELPING"
            return False

        if len(infohash) != 20:
            if DEBUG:
                print >> sys.stderr, "helper: got_stop_helping: bad infohash in STOP_HELPING"
            return False

        network_got_stop_helping_lambda = lambda:self.network_got_stop_helping(permid, infohash, selversion)
        self.session.lm.rawserver.add_task(network_got_stop_helping_lambda, 0)
        
        # If the request is from a unauthorized peer, we close
        # If the request is from an authorized peer (=coordinator) we close as well. So return False
        return False


    def network_got_stop_helping(self, permid, infohash, selversion):
        """ Find the appropriate Helper object and call it's method.
        
        Called by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion:
        """
        helper_obj = self.session.lm.get_coopdl_role_object(infohash, COOPDL_ROLE_HELPER)
        if helper_obj is None:
            if DEBUG:
                print >> sys.stderr, "helper: network_got_stop_helping: There is no helper object associated with this infohash"
            return
        
        if not helper_obj.is_coordinator(permid): 
            if DEBUG:
                print >> sys.stderr, "helper: network_got_stop_helping: The node asking for help is not the current coordinator"
            return
        
#        helper_obj.got_stop_helping(permid, infohash)
#        # Wake up download thread
#        helper_obj.notify()
        # Find and remove download
        dlist = self.session.get_downloads()
        for d in dlist:
            if d.get_def().get_infohash() == infohash:
                self.session.remove_download(d)
                break





    def got_request_pieces(self,permid, message, selversion):
        """ Handle the REQUEST_PIECES message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion:
        """
        try:
            infohash = message[1:21]
            pieces = bdecode(message[21:])
        except:
            print >> sys.stderr, "helper: got_request_pieces: bad data in REQUEST_PIECES"
            return False

        network_got_request_pieces_lambda = lambda:self.network_got_request_pieces(permid, message, selversion, infohash, pieces)
        self.session.lm.rawserver.add_task(network_got_request_pieces_lambda, 0)
        
        return True

    def network_got_request_pieces(self, permid, message, selversion, infohash, pieces):
        """ Find the appropriate Helper object and call it's method.
        
        Called by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion:
        """
        helper_obj = self.session.lm.get_coopdl_role_object(infohash, COOPDL_ROLE_HELPER)
        if helper_obj is None:
            if DEBUG:
                print >> sys.stderr, "helper: network_got_request_pieces: There is no helper object associated with this infohash"
            return

        if not helper_obj.is_coordinator(permid): 
            if DEBUG:
                print >> sys.stderr, "helper: network_got_request_pieces: The node asking for help is not the current coordinator"
            return

        helper_obj.got_request_pieces(permid, pieces)
        # Wake up download thread
        helper_obj.notify()
