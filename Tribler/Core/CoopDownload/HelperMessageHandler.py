# Written by Pawel Garbacki, Arno Bakker
# see LICENSE.txt for license information
#
# SecureOverlay message handler for a Helper
#


from sha import sha
import sys, os
from random import randint
import binascii

from Tribler.Core.TorrentDef import *
from Tribler.Core.Session import *
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

DEBUG = True

class HelperMessageHandler:
    def __init__(self):
        self.metadata_queue = {}

    def register(self,session,metadata_handler,helpdir,dlconfig):
        self.session = session
        self.helpdir = helpdir
        # The default DownloadStartupConfig dict as set in the Session
        self.dlconfig = dlconfig
        self.torrent_db = TorrentDBHandler.getInstance()
        self.metadata_handler = metadata_handler

    def handleMessage(self,permid,selversion,message):
        t = message[0]
        #if DEBUG:
        #    print >> sys.stderr,"helper: Got",getMessageName(t)

        if t == DOWNLOAD_HELP:
            return self.got_dlhelp_request(permid, message, selversion)
        elif t == STOP_DOWNLOAD_HELP:
            return self.got_stop_dlhelp_request(permid, message, selversion)
        elif t == PIECES_RESERVED:
            return self.got_pieces_reserved(permid, message, selversion)


    def got_dlhelp_request(self, permid, message,selversion):
        try:
            infohash = message[1:]
        except:
            print >> sys.stderr,"helper: warning: bad data in dlhelp_request"
            return False
        
        if len(infohash) != 20:
            return False
        
        if not self.can_help(infohash):
            return False
        torrent_data = self.find_torrent(infohash)
        if torrent_data:
            self.do_help(infohash, torrent_data, permid)
        else:
            self.get_metadata(permid, infohash,selversion)
        return True


    # It is very important here that we create safe filenames, i.e., it should
    # not be possible for a coordinator to send a METADATA message that causes
    # important files to be overwritten
    #
    def do_help(self, infohash, torrent_data, permid):

        basename = binascii.hexlify(infohash)+'.torrent' # ignore .tribe stuff, not vital
        torrentfilename = os.path.join(self.helpdir,basename)

        tfile = open(torrentfilename, "wb")
        tfile.write(torrent_data)
        tfile.close()

        if DEBUG:
            print >> sys.stderr,"helpmsg: Got metadata required for helping",show_permid_short(permid)
            print >> sys.stderr,"helpmsg: torrent: ",torrentfilename

        tdef = TorrentDef.load(torrentfilename)
        if self.dlconfig is None:
            dscfg = DownloadStartupConfig()
        else:
            dscfg = DownloadStartupConfig(self.dlconfig)
        dscfg.set_coopdl_coordinator_permid(permid)
        dscfg.set_dest_dir(self.helpdir)

        # Start new download
        self.session.start_download(tdef,dscfg)

    def get_metadata(self, permid, infohash, selversion):
        if DEBUG:
            print >> sys.stderr,"helpmsg: Don't have torrent yet, ask coordinator"
        if not self.metadata_queue.has_key(infohash):
            self.metadata_queue[infohash] = []
        self.metadata_queue[infohash].append(permid)
        self.metadata_handler.send_metadata_request(permid, infohash, selversion,caller="dlhelp")

    def metadatahandler_received_torrent(self, infohash, torrent_data):
        if DEBUG:
            print >> sys.stderr,"helpmsg: Metadata handler reports torrent is in."
        if not self.metadata_queue.has_key(infohash) or not self.metadata_queue[infohash]:
            if DEBUG:
                print >> sys.stderr,"helpmsg: Metadata handler reported a torrent we are not waiting for."
            return
        
        for permid in self.metadata_queue[infohash]:
            # only ask for metadata once
            self.do_help(infohash, torrent_data, permid)
        del self.metadata_queue[infohash]

    def can_help(self, infohash):    #TODO: test if I can help the cordinator to download this file
        return True                      #Future support: make the decision based on my preference

    def find_torrent(self, infohash):
        torrent = self.torrent_db.getTorrent(infohash)
        if torrent is None:
            return None
        elif 'torrent_dir' in torrent:
            fn = torrent['torrent_dir']
            if os.path.isfile(fn):
                f = open(fn,"rb")
                data = f.read()
                f.close()
                return data
            else:
                return None
        else:
            return None


    def got_stop_dlhelp_request(self, permid, message, selversion):
        try:
            infohash = message[1:]
        except:
            print >> sys.stderr,"helper: warning: bad data in STOP_DOWNLOAD_HELP"
            return False

        network_got_stop_dlhelp_lambda = lambda:self.network_got_stop_dlhelp(permid,message,selversion,infohash)
        self.session.lm.rawserver.add_task(network_got_stop_dlhelp_lambda,0)
        
        # If the request is from a unauthorized peer, we close
        # If the request is from an authorized peer (=coordinator) we close as 
        # well. So return False
        return False 
    

    def network_got_stop_dlhelp(self,permid,message,selversion,infohash):
        # Called by network thread
        
        h = self.session.lm.get_coopdl_role_object(infohash,COOPDL_ROLE_HELPER)
        if h is None:
            return

        if not h.is_coordinator(permid): 
            if DEBUG:
                print >> sys.stderr,"helpmsg: Got a STOP_DOWNLOAD_HELP message from non-coordinator",show_permid_short(permid)
            return

        # Find and remove download
        dlist = self.session.get_downloads()
        for d in dlist:
            if d.get_def().get_infohash() == infohash:
                self.session.remove_download(d)
                break

    def got_pieces_reserved(self,permid, message, selversion):
        try:
            infohash = message[1:21]
            pieces = bdecode(message[21:])
        except:
            print >> sys.stderr,"helper: warning: bad data in PIECES_RESERVED"
            return False

        network_got_pieces_reserved_lambda = lambda:self.network_got_pieces_reserved(permid,message,selversion,infohash,pieces)
        self.session.lm.rawserver.add_task(network_got_pieces_reserved_lambda,0)
        
        return True

    def network_got_pieces_reserved(self,permid,message,selversion,infohash,pieces):
       # Called by network thread
       
        h = self.session.lm.get_coopdl_role_object(infohash,COOPDL_ROLE_HELPER)
        if h is None:
            return

        if not h.is_coordinator(permid): 
            return

        h.got_pieces_reserved(permid, pieces)
        # Wake up download thread
        h.notify()
        
