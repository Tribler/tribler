# Written by Arno Bakker and ABC authors 
# see LICENSE.txt for license information

import sys
from sets import Set
from threading import RLock
from traceback import print_exc


from Tribler.API.simpledefs import *

DEBUG = False


class RateManager:
    def __init__(self):
        self.lock = RLock()
        self.statusmap = {}
        self.currenttotal = {}
        self.dset = Set()
        self.clear_downloadstates()
        
    def adjust_speeds(self):
        self.lock.acquire()
        
        self.calc_and_set_speed_limits(DOWNLOAD)
        self.calc_and_set_speed_limits(UPLOAD)
        self.clear_downloadstates()
        
        self.lock.release()


    def add_downloadstate(self,d,ds):
        """ Returns the number of unique states currently stored """
        self.lock.acquire()
        try:
            if d not in self.dset:
                self.statusmap[ds.get_status()].append((d,ds))
                for dir in [UPLOAD,DOWNLOAD]:
                    self.currenttotal[dir] += ds.get_current_speed(dir)
                self.dset.add(d)
            return len(self.dset)
        finally:
            self.lock.release()

    #
    # Internal methods
    #
    #
    # The following methods are all called with the lock held
    #
    def clear_downloadstates(self):
        self.statusmap[DLSTATUS_ALLOCATING_DISKSPACE] = []
        self.statusmap[DLSTATUS_WAITING4HASHCHECK] = []
        self.statusmap[DLSTATUS_HASHCHECKING] = []
        self.statusmap[DLSTATUS_DOWNLOADING] = []
        self.statusmap[DLSTATUS_SEEDING] = []
        self.statusmap[DLSTATUS_STOPPED] = []
        self.statusmap[DLSTATUS_STOPPED_ON_ERROR] = []
        for dir in [UPLOAD,DOWNLOAD]:
            self.currenttotal[dir] = 0
        self.dset.clear()

    def calc_and_set_speed_limits(self,direct):
        """ Override this method to write you own speed management policy. """
        pass


class UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager(RateManager):
    """ This class implements a simple rate management policy that:
    1. If the API user set a desired speed for a particular download,
       the speed limit for this download is set to the desired value.
    2. For all torrents for which no desired speeds have been set, 
       the global limit is equally divided amongst all downloads.
       (however small the piece of the pie may be).
    3. There are separate global limits for download speed, upload speed
       and upload speed when all torrents are seeding. 
    """
    def __init__(self,global_maxupload_speed,global_maxseed_upload_speed,global_maxdownload_speed):
        
        RateManager.__init__(self)
        self.global_maxupload_speed = global_maxupload_speed 
        self.global_maxseed_upload_speed = global_maxseed_upload_speed
        self.global_maxdownload_speed = global_maxdownload_speed

        
    def calc_and_set_speed_limits(self, dir = UPLOAD):
        
        if DEBUG:
            print >>sys.stderr,"RateManager: calc_and_set_speed_limits",dir
        
        if dir == UPLOAD:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]+self.statusmap[DLSTATUS_SEEDING]
        else:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]

        # Limit working set to active torrents with connections:
        newws = []
        for (d,ds) in workingset:
            if ds.has_active_connections():
                newws.append((d,ds))
        workingset = newws

        if DEBUG:
            print >>sys.stderr,"RateManager: calc_and_set_speed_limits: len workingset",len(workingset)

        # No active file, not need to calculate
        if not workingset:
            return
        
        globalmaxspeed = self.get_global_max_speed(dir)
        # See if global speed settings are set to unlimited
        if globalmaxspeed == 0:
            # Unlimited speed
            for (d,ds) in workingset:
                d.set_max_speed(dir,d.get_max_desired_speed(dir)) 
            return
        
        if DEBUG:
            print >>sys.stderr,"RateManager: calc_and_set_speed_limits: globalmaxspeed is",globalmaxspeed,dir

        # User set priority is always granted, ignoring global limit
        todoset = []
        for (d,ds) in workingset:
            maxdesiredspeed = d.get_max_desired_speed(dir)
            if maxdesiredspeed > 0.0:
                d.set_max_speed(dir,maxdesiredspeed)
            else:
                todoset.append((d,ds))

        if len(todoset) > 0:
            # Rest divides globalmaxspeed equally
            localmaxspeed = globalmaxspeed / float(len(todoset))
            # if too small than user's problem
            
            if DEBUG:
                print >>sys.stderr,"RateManager: calc_and_set_speed_limits: localmaxspeed is",localmaxspeed,dir

            for (d,ds) in todoset:
                d.set_max_speed(dir,localmaxspeed)


    def get_global_max_speed(self, dir = UPLOAD):
        if dir == UPLOAD:
            if len(self.statusmap[DLSTATUS_DOWNLOADING]) == 0 and len(self.statusmap[DLSTATUS_SEEDING]) > 0:
                # Static overall maximum up speed when seeding
                return self.global_maxseed_upload_speed
            else:
                # Static overall maximum up speed when downloading
                return self.global_maxupload_speed
        else:
            return self.global_maxdownload_speed
           
