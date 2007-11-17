import sys
import os
#import time
import copy
import sha
import shutil
from traceback import print_exc,print_stack

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import *
from Tribler.Core.exceptions import *
from Tribler.Core.Base import *

DEBUG = True

class DownloadState(Serializable):
    """
    Contains a snapshot of the state of the Download at a specific
    point in time. Using a snapshot instead of providing live data and 
    protecting access via locking should be faster.
    
    cf. libtorrent torrent_status
    """
    def __init__(self,download,status,error,progress,stats=None,filepieceranges=None,logmsgs=None):
        self.download = download
        self.filepieceranges = filepieceranges # NEED CONC CONTROL IF selected_files RUNTIME SETABLE
        self.logmsgs = logmsgs
        if stats is None:
            self.error = error # readonly access
            self.progress = progress
            if self.error is not None:
                self.status = DLSTATUS_STOPPED_ON_ERROR
            else:
                self.status = status
            self.stats = None
        elif error is not None:
            self.error = error # readonly access
            self.progress = 0.0 # really want old progress
            self.status = DLSTATUS_STOPPED_ON_ERROR
            self.stats = None
        elif status is not None:
            # For HASHCHECKING and WAITING4HASHCHECK
            self.error = error
            self.status = status
            if self.status == DLSTATUS_WAITING4HASHCHECK:
                self.progress = 0.0
            else:
                self.progress = stats['frac']
            self.stats = None
        else:
            # Copy info from stats
            self.error = None
            self.progress = stats['frac']
            if stats['frac'] == 1.0:
                self.status = DLSTATUS_SEEDING
            else:
                self.status = DLSTATUS_DOWNLOADING
            #print >>sys.stderr,"STATS IS",stats
            
            # Safe to store the stats dict. The stats dict is created per
            # invocation of the BT1Download returned statsfunc and contains no
            # pointers.
            #
            self.stats = stats
            
            # for pieces complete
            statsobj = self.stats['stats']
            if self.filepieceranges is None:
                self.haveslice = statsobj.have # is copy of network engine list
            else:
                # Show only pieces complete for the selected ranges of files
                totalpieces =0
                for t,tl,f in self.filepieceranges:
                    diff = tl-t
                    totalpieces += diff
                    
                print >>sys.stderr,"DownloadState: get_pieces_complete",totalpieces
                
                haveslice = [False] * totalpieces
                haveall = True
                index = 0
                for t,tl,f in self.filepieceranges:
                    for piece in range(t,tl):
                        haveslice[index] = statsobj.have[piece]
                        if haveall and haveslice[index] == False:
                            haveall = False
                        index += 1 
                self.haveslice = haveslice
                if haveall:
                    # we have all pieces of the selected files
                    self.status = DLSTATUS_SEEDING
                    self.progress = 1.0

    
    def get_download(self):
        """ returns the Download object of which this is the state """
        return self.download
    
    def get_progress(self):
        """
        returns: percentage of torrent downloaded, as float
        """
        return self.progress
        
    def get_status(self):
        """
        returns: status of the torrent, e.g. DLSTATUS_* 
        """
        return self.status

    def get_error(self):
        """ 
        returns: the Exception that caused the download to be moved to 
        DLSTATUS_STOPPED_ON_ERROR status.
        """
        return self.error

    #
    # Details
    # 
    def get_current_speed(self,direct):
        """
        returns: current up or download speed in KB/s, as float
        """
        if self.stats is None:
            return 0.0
        if direct == UPLOAD:
            return self.stats['up']/1024.0
        else:
            return self.stats['down']/1024.0

    def has_active_connections(self):
        """ 
        returns: whether the download has active connections
        """
        if self.stats is None:
            return False

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numSeeds+statsobj.numPeers > 0
        
    def get_pieces_complete(self):
        # Hmm... we currently have the complete overview in statsobj.have,
        # but we want the overview for selected files.
        if self.stats is None:
            return []
        else:
            return self.haveslice

    def get_vod_prebuffering_progress(self):
        if self.stats is None:
            return 0.0
        else:
            return self.stats['vod_prebuf_frac']
    
    def get_vod_playable(self):
        if self.stats is None:
            return False
        else:
            return self.stats['vod_playable']

    def get_vod_playable_after(self):
        if self.stats is None:
            return float(2 ** 31)
        else:
            return self.stats['vod_playable_after']


    def get_log_messages(self):
        """ Returns the last 10 logged non-fatal error messages as a list of 
        (time,msg) tuples """
        if self.logmsgs is None:
            return []
        else:
            return self.logmsgs
    


