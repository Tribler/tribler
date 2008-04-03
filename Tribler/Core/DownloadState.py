# Written by Arno Bakker 
# see LICENSE.txt for license information
""" Contains a snapshot of the state of the Download at a specific point in time. """

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
    def __init__(self,download,status,error,progress,stats=None,filepieceranges=None,logmsgs=None,coopdl_helpers=None):
        """ Internal constructor.
        @param download The Download this state belongs too.
        @param status The status of the Download (DLSTATUS_*)
        @param progress The general progress of the Download.
        @param stats The BT engine statistics for the Download.
        @param filepieceranges The range of pieces that we are interested in. 
        The get_pieces_complete() returns only completeness information about 
        this range. This is used for playing a video in a multi-torrent file.
        @param logmsgs A list of messages from the BT engine which may be of 
        interest to the user. E.g. connection to tracker failed.
        """
        
        #print >>sys.stderr,"DownloadState.__init__",`download.get_def().get_name()`,"status",status,"error",error,"progress",progress,"stats",`stats`
        
        self.download = download
        self.filepieceranges = filepieceranges # NEED CONC CONTROL IF selected_files RUNTIME SETABLE
        self.logmsgs = logmsgs
        self.coopdl_helpers = coopdl_helpers
        if stats is None:
            # No info available yet from download engine
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
                    
                #print >>sys.stderr,"DownloadState: get_pieces_complete",totalpieces
                
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
                if haveall and len(self.filepieceranges) > 0:
                    # we have all pieces of the selected files
                    self.status = DLSTATUS_SEEDING
                    self.progress = 1.0

    
    def get_download(self):
        """ Returns the Download object of which this is the state """
        return self.download
    
    def get_progress(self):
        """ The general progress of the Download as a percentage. When status is 
         * DLSTATUS_HASHCHECKING it is the percentage of already downloaded 
           content checked for integrity.
         * DLSTATUS_DOWNLOADING/SEEDING it is the percentage downloaded.
        @return Progress as a float (0..1).
        """
        return self.progress
        
    def get_status(self):
        """ Returns the status of the torrent.
        @return DLSTATUS_* """
        return self.status

    def get_error(self):
        """ Returns the Exception that caused the download to be moved to 
        DLSTATUS_STOPPED_ON_ERROR status.
        @return Exception
        """
        return self.error

    #
    # Details
    # 
    def get_current_speed(self,direct):
        """
        Returns the current up or download speed.
        @return The speed in KB/s, as float.
        """
        if self.stats is None:
            return 0.0
        if direct == UPLOAD:
            return self.stats['up']/1024.0
        else:
            return self.stats['down']/1024.0

    def get_eta(self):
        """
        Returns the estimated time to finish of download.
        @return The time in ?, as ?.
        """
        if self.stats is None:
            return 0.0
        else:
            return self.stats['time']
        
    def get_num_peers(self):
        """ 
        Returns the download's number of active connections. This is used
        to see if there is any progress when non-fatal errors have occured
        (e.g. tracker timeout).
        @return Boolean.
        """
        if self.stats is None:
            return 0

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numSeeds+statsobj.numPeers
        
    def get_num_seeds_peers(self):
        """
        Returns the sum of the number of seeds and peers. This function
        works only if the Download.set_state_callback() / 
        Session.set_download_states_callback() was called with the getpeerlist 
        parameter set to True, otherwise returns (None,None)  
        @return A tuple (num seeds, num peers)
        """
        if self.stats is None or self.stats['spew'] is None:
            return (None,None)
        
        total = len(self.stats['spew'])
        seeds = len([i for i in self.stats['spew'] if i['completed'] == 1.0])
        return seeds, total-seeds
    
    def get_pieces_complete(self):
        """ Returns a list of booleans indicating whether we have completely
        received that piece of the content. The list of pieces for which 
        we provide this info depends on which files were selected for download
        using DownloadStartupConfig.select_files().
        @return A list of booleans
        """
        if self.stats is None:
            return []
        else:
            return self.haveslice

    def get_vod_prebuffering_progress(self):
        """ Returns the percentage of prebuffering for Video-On-Demand already 
        completed.
        @return A float (0..1) """
        if self.stats is None:
            return 0.0
        else:
            return self.stats['vod_prebuf_frac']
    
    def is_vod(self):
        """ Returns if this download is currently in vod mode 
        
        @return A Boolean"""
        if self.stats is None:
            return False
        else:
            return self.stats['vod']
    
    def get_vod_playable(self):
        """ Returns whether or not the Download started in Video-On-Demand
        mode has sufficient prebuffer and download speed to be played out
        to the user. 
        @return Boolean.
        """
        if self.stats is None:
            return False
        else:
            return self.stats['vod_playable']

    def get_vod_playable_after(self):
        """ Returns the estimated time until the Download started in Video-On-Demand
        mode can be started to play out to the user. 
        @return A number of seconds.
        """
        if self.stats is None:
            return float(2 ** 31)
        else:
            return self.stats['vod_playable_after']
        
#    def get_vod_duration(self):
#        """ Returns video total duration if vod system managed to detect it
#        
#        @return int duration in seconds or None if unknown
#        """
#        if self.stats is not None:
#            return self.stats['vod_duration']


    def get_log_messages(self):
        """ Returns the last 10 logged non-fatal error messages.
        @return A list of (time,msg) tuples. Time is Python time() format. """
        if self.logmsgs is None:
            return []
        else:
            return self.logmsgs

    def get_peerlist(self):
        """ Returns a list of dictionaries, one for each connected peer
        containing the statistics for that peer. In particular, the
        dictionary contains the keys:
        <pre>
        'id' = PeerID or 'http seed'
        'ip' = IP address as string or URL of httpseed
        'optimistic' = True/False
        'direction' = 'L'/'R' (outgoing/incoming)
        'uprate' = Upload rate in KB/s
        'uinterested' = Upload Interested: True/False
        'uchoked' = Upload Choked: True/False
        'downrate' = Download rate in KB/s
        'dinterested' = Download interested: True/Flase
        'dchoked' = Download choked: True/False
        'snubbed' = Download snubbed: True/False
        'utotal' = Total uploaded from peer in KB
        'dtotal' = Total downloaded from peer in KB
        'completed' = Fraction of download completed by peer (0-1.0) 
        'speed' = The peer's current total download speed (estimated)
        </pre>
        """
        if self.stats is None or 'spew' not in self.stats:
            return []
        else:
            return self.stats['spew']


    def get_coopdl_helpers(self):
        """ Returns the peers currently helping.
        @return A list of PermIDs.
        """
        if self.coopdl_helpers is None:
            return []
        else:
           return self.coopdl_helpers 
