import sys
import os
from time import time, clock

#from traceback import print_exc
#from cStringIO import StringIO

from Utility.constants import * #IGNORE:W0611
from Utility.helpers import union, difference
from safeguiupdate import DelayedEventHandler

################################################################
#
# Class: RateManger
#
# Keep the upload and download rates for torrents within
# the defined local and global limits. Adopted for Tribler API 
# by Arno Bakker
#
################################################################
class RateManager:
    def __init__(self,max_upload_rate,max_seed_upload_rate,max_download_rate)

        self.urm_enabled = True
        self.max_upload_rate = max_upload_rate 
        self.max_seed_upload_rate = max_seed_upload_rate
        self.max_download_rate = max_download_rate

        self.lock = RLock()
        
        # For Upload Rate Maximizer
        # Time when the upload rate is lower than the URM threshold for the first time
        self.urm_time = { 'under' : 0.0, 
                          'checking'  : 0.0 }
                
        # bandwidth between reserved rate and measured rate
        # above which a torrent will have its reserved rate lowered
        self.calcupth1 = 2.3
        
        # bandwidth between reserved rate and measured rate
        # under which a torrent will have its reserved rate raised
        self.calcupth2 = 0.7
        
        self.meancalcupth = (self.calcupth1 + self.calcupth2) / 2
        
        self.lastmaxrate = -1

        # Minimum rate setting
        # 3 KB/s for uploads, 0.01KB/s for downloads
        # (effectively, no real limit for downloads)
        self.rateminimum = { "up": 3.0,
                             "down": 0.01 }

        self.timer = NamedTimer(4, self.RateTasks)


    def RateTasks(self):
        self.lock.acquire()
        
        # self.UploadRateMaximizer() TODO: add queueing system
        
        self.CalculateBandwidth("down")
        self.CalculateBandwidth("up")
        
        self.lock.release()
        self.timer = NamedTimer(4, self.RateTasks)


    def add_downloadstate(self,d,ds):
        #self.states.append(ds)
        self.statusmap[ds.get_status()].append((d,ds))
        stats = ds.get_stats()
        self.currentotal['up'] += stats['up']
        self.currentotal['down'] += stats['down']
            
    def clear_downloadstates(self):
        #self.states.clear()
        self.statusmap[DLSTATUS_ALLOCATING_DISKSPACE] = []
        self.statusmap[DLSTATUS_WAITING4HASHCHECK] = []
        self.statusmap[DLSTATUS_HASHCHECKING] = []
        self.statusmap[DLSTATUS_DOWNLOADING] = []
        self.statusmap[DLSTATUS_SEEDING] = []
        self.statusmap[DLSTATUS_STOPPED] = []
        self.statusmap[DLSTATUS_STOPPED_ON_ERROR] = []
        self.currentotal = {}
        self.currentotal['up'] = 0.0
        self.currentotal['down'] = 0.0


    def MaxRate(self, dir = "up"):
        if dir == "up":
            if self.allseeds:
                # Static overall maximum up rate when seeding
                return self.max_seed_upload_rate
            else:
                # Static overall maximum up rate when downloading
                return self.max_upload_rate
        else:
            return self.max_download_rate
           
    # See if any torrents are in the "checking existing data"
    # or "allocating space" stages
    def any_torrents_checking(self):

        if len(self.statusmap[DLSTATUS_ALLOCATING_DISKSPACE]) > 0 or \
           len(self.statusmap[DLSTATUS_WAITING4HASHCHECK]) > 0 or \
           len(self.statusmap[DLSTATUS_HASHCHECKING]) > 0:
            return True
        return False


            
    def CalculateBandwidth(self, dir = "up"):
        if dir == "up":
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]+self.statusmap[DLSTATUS_SEEDING]
        else:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]

        # Limit working set to active torrents with connections:
        newws = []
        for ds in workingset:
            stats = ds.get_stats()
            statsobj = stats['stats']
            if statsobj.numSeeds+statsobj.numPeers > 0:
                newws.apppend(ds)
        workingset = newws

        # No active file, not need to calculate
        if not workingset:
            return
        
        maxrate = self.MaxRate(dir)
        # See if global rate settings are set to unlimited
        if maxrate == 0:
            # Unlimited rate
            for (d,ds) in workingset:
                if dir == "up":
                    # Arno: you have 2 values: the rate you want, and the rate you are allowed
                    # you want to remember the first too.
                    d.set_max_upload_rate(d.get_max_desired_upload_rate()) # TODO: optimize so less locking?
                else:
                    d.set_max_download_rate(d.get_max_desired_download_rate()) # TODO: optimize so less locking?
            return
        
        #print "====================== BEGINNING ALGO ======= th1=%.1f ; th2=%.1f =============================" % (self.calcupth1, self.calcupth2)

        #######################################################
        # - Find number of completed/incomplete torrent
        # - Number of torrent using local setting
        # - bandwidth already used by torrents
        # - Sorting of torrents in lists according to their will in matter
        #   of upload rate :
        #   (tobelowered, toberaisedinpriority, toberaised, nottobechanged)
        #######################################################

        # Option set in Preferences/Queue.
        # If not set, torrents with rate local settings are treated like other 
        # torrents, except they have their own max rate they can't cross over. 
        # The consequence is a behaviour slightly different from the behavior of
        # ABC releases prior to 2.7.0.
        # If set, this gives the algorithm the behaviour of ABC releases prior 
        # to 2.7.0 : the torrents with an rate local setting will be granted 
        # bandwidth in priority to fulfill their local setting, even is this one
        # is higher than the global max rate setting, and even if this bandwidth
        # must be taken from other active torrents without a local rate setting. 
        # These torrents will not take part in the rate exchange between active 
        # torrents when all bandwidth has been distributed, since they will have 
        # been served in priority.
        prioritizelocal = True # Arno set to True

        # torrents with local rate settings when prioritizelocal is set (see prioritizelocal)
        localprioactive = []       
    
        # torrents for which measured rate is lowering and so reserved rate can
        # be lowered
        tobelowered = []
     
        # torrents for which measured rate is growing and so reserved rate can 
        # be raised, (with reserved rate > 3 kB/s for uploading)
        toberaised  = []                           

        # torrents for which reserved rate can be raised, with reserved 
        # rate < 3 kB/s
        # These will always be raised even there's no available up bandwith, 
        # to fulfill the min 3 kB/s rate rule
        toberaisedinpriority = []                             

        # torrents for which reserved rate is not to be changed and 
        # is > rateminimum; (for these, the measured rate is between (max upload
        # reserved - calcupth1) and (max upload reserved - calcupth2)
        nottobechanged = []   

        # mean max rate for torrents to be raised or not to be changed ; it will
        # be used to decide which torrents must be raised amongst those that 
        # want to get higher and that must share the available up bandwidth. 
        # The torrents that don't want to change their rate and that are below 
        # 3 kB/s are not taken into account on purpose, because these ones will 
        # never be lowered to give more rate to a torrent that wants to raise 
        # its rate, or to compensate for the rate given to torrents to be raised
        # in priority.
        meanrate = 0.0            
        
        for (d,ds) in workingset:
            # Active Torrent
            stats = ds.get_stats()
            if dir == "up":
                currentrate = stats['up'] 
                currentlimit = d.get_max_upload_rate()
                maxdesiredrate = d.get_max_desired_upload_rate()
            else:
                currentrate = stats['down'] 
                currentlimit = d.get_max_download_rate()
                maxdesiredrate = d.get_max_desired_download_rate()

