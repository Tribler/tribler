# Written by Arno Bakker
# Updated by George Milescu 
# see LICENSE.txt for license information
""" Contains a snapshot of the state of the Download at a specific point in time. """
import time

import sys
from traceback import print_exc,print_stack

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import *
from Tribler.Core.exceptions import *
from Tribler.Core.Base import *
from Tribler.Core.DecentralizedTracking.repex import REPEX_SWARMCACHE_SIZE

DEBUG = False

class DownloadState(Serializable):
    """
    Contains a snapshot of the state of the Download at a specific
    point in time. Using a snapshot instead of providing live data and 
    protecting access via locking should be faster.
    
    cf. libtorrent torrent_status
    """
    def __init__(self,download,status,error,progress,stats=None,filepieceranges=None,logmsgs=None,proxyservice_proxy_list=[],proxyservice_doe_list=[],peerid=None,videoinfo=None,swarmcache=None):
        """ Internal constructor.
        @param download The Download this state belongs too.
        @param status The status of the Download (DLSTATUS_*)
        @param progress The general progress of the Download.
        @param stats The BT engine statistics for the Download.
        @param filepieceranges The range of pieces that we are interested in. 
        The get_pieces_complete() returns only completeness information about 
        this range. This is used for playing a video in a multi-torrent file.
        @param logmsgs A list of messages from the BT engine which may be of 
        """
        # Raynor Vliegendhart, TODO: documentation of DownloadState seems incomplete?
        # RePEX: @param swarmcache The latest SwarmCache known by Download. This
        #        cache will be used when the download is not running.
        # RePEX TODO: instead of being passed the latest SwarmCache, DownloadState could
        # also query it from Download? Perhaps add get_swarmcache to Download(Impl)?
        
        self.download = download
        self.filepieceranges = filepieceranges # NEED CONC CONTROL IF selected_files RUNTIME SETABLE
        self.logmsgs = logmsgs
        self.vod_status_msg = None
        self.proxyservice_proxy_list = proxyservice_proxy_list
        self.proxyservice_doe_list = proxyservice_doe_list
        self.seedingstats = None #SeedingManager will update downloadstate with seedings stats (version, total_up, total_down, time_seeding)
        
        # RePEX: stored swarmcache from Download and store current time
        if swarmcache is not None:
            self.swarmcache = dict(swarmcache)
        else:
            self.swarmcache = None
        self.time = time.time()
        
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
        elif status is not None and status != DLSTATUS_REPEXING:
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
            
            # RePEX: REPEXING status overrides SEEDING/DOWNLOADING status.
            if status is not None and status == DLSTATUS_REPEXING:
                self.status = DLSTATUS_REPEXING
            

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

    def get_total_transferred(self,direct):
        """
        Returns the total amount of up or downloaded bytes.
        @return The amount in bytes.
        """
        if self.stats is None:
            return 0L
        # self.stats:          BitTornado.BT1.DownloaderFeedback.py (return from gather method)
        # self.stats["stats"]: BitTornado.BT1.Statistics.py (Statistics_Response instance)
        if direct == UPLOAD:
            return self.stats['stats'].upTotal
        else:
            return self.stats['stats'].downTotal
        
    def set_seeding_statistics(self, seedingstats):
        self.seedingstats = seedingstats
        
    def get_seeding_statistics(self):
        """
        Returns the seedings stats for this download. Will only be availible after
        SeedingManager update_download_state is called. 
        Contains if not null, version, total_up, total_down, time_seeding
        All values are stored by the seedingmanager, thus will not only contain current download session values
        """
        return self.seedingstats
    
    def get_eta(self):
        """
        Returns the estimated time to finish of download.
        @return The time in ?, as ?.
        """
        if self.stats is None:
            return 0.0
        else:
            return self.stats['time']
        
    def get_num_con_candidates(self):
        """ 
        Returns the download's number of possible connections. This is used
        to see if there is any progress when non-fatal errors have occured
        (e.g. tracker timeout).
        @return An integer.
        """
        if self.stats is None:
            return 0

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numConCandidates

    def get_num_con_initiated(self):
        """ 
        Returns the download's number of initiated connections. This is used
        to see if there is any progress when non-fatal errors have occured
        (e.g. tracker timeout).
        @return An integer.
        """
        if self.stats is None:
            return 0

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numConInitiated
        
    def get_num_peers(self):
        """ 
        Returns the download's number of active connections. This is used
        to see if there is any progress when non-fatal errors have occured
        (e.g. tracker timeout).
        @return An integer.
        """
        if self.stats is None:
            return 0

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numSeeds+statsobj.numPeers
        
    def get_num_nonseeds(self):
        """ 
        Returns the download's number of non-seeders. 
        @return An integer.
        """
        if self.stats is None:
            return 0

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numPeers
        
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
        using DownloadStartupConfig.set_selected_files().
        @return A list of booleans
        """
        if self.stats is None:
            return []
        else:
            return self.haveslice
        
    def get_files_completion(self):
        """ Returns a list of filename, progress tuples indicating the progress 
        for every file selected using set_selected_files. Progress is a float
        between 0 and 1
        """
        completion = []
        if self.progress == 1.0:
            for file_in_torrent, _ in self.download.get_dest_files():
                for t,tl,f in self.filepieceranges:
                    completion.append((f, 1.0))
        else:
            if self.filepieceranges:
                index = 0
                for t,tl,f in self.filepieceranges:
                    #niels: ranges are from-to (inclusive ie if a file consists one piece t and tl will be the same)
                    total_pieces = tl - t
                    if total_pieces and getattr(self, 'haveslice', False):
                        completed = 0
                        for i in range(total_pieces):
                            if self.haveslice[index]:
                                completed += 1
                            index += 1
                        
                        completion.append((f, completed/(total_pieces*1.0)))
                    else:
                        completion.append((f, 0.0))
        return completion
    
    def gef_selected_files(self):
        if self.filepieceranges:
            files = []
            for _, _, f in self.filepieceranges:
                files.append(f)
            return files
        
        
    def get_availability(self):
        """ Return overall the availability of all pieces, using connected peers
        Availability is defined as the number of complete copies of a piece, thus seeders
        increment the availability by 1. Leechers provide a subset of piece thus we count the
        overall availability of all pieces provided by the connected peers and use the minimum
        of this + the average of all additional pieces.
        """
        nr_seeders_complete = 0
        merged_bitfields = None
        
        peers = self.get_peerlist()
        for peer in peers:
            if peer['completed'] == 1 or peer['have'].complete():
                nr_seeders_complete += 1
            else:
                boollist = peer['have'].toboollist()
                if merged_bitfields == None:
                    merged_bitfields = [0]*len(boollist)
                
                for i in range(len(boollist)):
                    if boollist[i]:
                        merged_bitfields[i] += 1
        
        if merged_bitfields:
            #count the number of complete copies due to overlapping leecher bitfields 
            nr_leechers_complete = min(merged_bitfields)
            
            #detect remainder of bitfields which are > 0
            nr_more_than_min = len([x for x in merged_bitfields if x > nr_leechers_complete])
            fraction_additonal = float(nr_more_than_min) / len(merged_bitfields)
            
            return nr_seeders_complete + nr_leechers_complete + fraction_additonal
        return nr_seeders_complete
        
    def get_vod_prebuffering_progress(self):
        """ Returns the percentage of prebuffering for Video-On-Demand already 
        completed.
        @return A float (0..1) """
        if self.stats is None:
            if self.status == DLSTATUS_STOPPED and self.progress == 1.0:
                return 1.0
            else:
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
        
    def get_vod_stats(self):
        """ Returns a dictionary of collected VOD statistics. The keys contained are:
        <pre>
        'played' = number of pieces played. With seeking this may be more than npieces
        'late' = number of pieces arrived after they were due
        'dropped' = number of pieces lost
        'stall' = estimation of time the player stalled, waiting for pieces (seconds)
        'pos' = playback position, as an absolute piece number
        'prebuf' = amount of prebuffering time that was needed (seconds,
                   set when playback starts)
        'firstpiece' = starting absolute piece number of selected file
        'npieces' = number of pieces in selected file
        </pre>, or no keys if no VOD is in progress.
        @return Dict.
        """
        if self.stats is None:
            return {}
        else:
            return self.stats['vod_stats']



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
        'extended_version' = Peer client version
        'ip' = IP address as string or URL of httpseed
        'port' = Port
        'pex_received' = True/False
        'g2g' = True/False (Tribler peer yes/no)
        'g2g_score' = List
        'optimistic' = True/False
        'direction' = 'L'/'R' (outgoing/incoming)
        'uprate' = Upload rate in KB/s
        'uinterested' = Upload Interested: True/False
        'uchoked' = Upload Choked: True/False
        'uhasqueries' = Upload has requests in buffer and not choked
        'downrate' = Download rate in KB/s
        'dinterested' = Download interested: True/Flase
        'dchoked' = Download choked: True/False
        'snubbed' = Download snubbed: True/False
        'utotal' = Total uploaded from peer in KB
        'dtotal' = Total downloaded from peer in KB
        'completed' = Fraction of download completed by peer (0-1.0) 
        'have' = Bitfield object for this peer if not complete
        'speed' = The peer's current total download speed (estimated)
        </pre>
        """
        if self.stats is None or 'spew' not in self.stats:
            return []
        else:
            return self.stats['spew']

    # ProxyService_
    #
    def get_proxy_list(self):
        """ Returns the peers currently proxying.
        @return A list of PermIDs.
        """
        if self.proxyservice_proxy_list is None:
            return []
        else:
            return self.proxyservice_proxy_list 

    def get_doe_list(self):
        """ Returns the current list of doe nodes.
        @return A list od PermIDs.
        """
        return self.proxyservice_doe_list
    #
    # _ProxyService

    #
    # RePEX: get swarmcache
    #
    def get_swarmcache(self):
        """
        Gets the SwarmCache of the Download. If the Download was RePEXing,
        the latest SwarmCache is returned. If the Download was running 
        normally, a sample of the peerlist is merged with the last
        known SwarmCache. If the Download was stopped, the last known
        SwarmCache is returned.
        
        @return The latest SwarmCache for this Download, which is a dict 
        mapping dns to a dict with at least 'last_seen' and 'pex' keys.
        """
        swarmcache = {}
        if self.status == DLSTATUS_REPEXING and self.swarmcache is not None:
            # the swarmcache given at construction comes from RePEXer 
            swarmcache = self.swarmcache
        elif self.status in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING]:
            # get local PEX peers from peerlist and fill swarmcache
            peerlist = [p for p in self.get_peerlist() if p['direction']=='L' and p.get('pex_received',0)][:REPEX_SWARMCACHE_SIZE]
            swarmcache = {}
            for peer in peerlist:
                dns = (peer['ip'], peer['port'])
                swarmcache[dns] = {'last_seen':self.time,'pex':[]}
            # fill remainder with peers from old swarmcache
            if self.swarmcache is not None:
                for dns in self.swarmcache.keys()[:REPEX_SWARMCACHE_SIZE-len(swarmcache)]:
                    swarmcache[dns] = self.swarmcache[dns]
            
            # TODO: move peerlist sampling to a different module?
            # TODO: perform swarmcache computation only once?
        elif self.swarmcache is not None:
            # In all other cases, use the old swarmcache
            swarmcache = self.swarmcache
            # TODO: rearrange if statement to merge 1st and 3rd case?
            
        return swarmcache
        
