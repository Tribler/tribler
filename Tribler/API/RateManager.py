# Written by Arno Bakker and ABC authors 
# see LICENSE.txt for license information

import sys
from sets import Set
from threading import RLock
from traceback import print_exc


from Tribler.API.simpledefs import *




class RateManager:
    def __init__(self,global_maxupload_rate,global_maxseed_upload_rate,global_maxdownload_rate):

        self.global_maxupload_rate = global_maxupload_rate 
        self.global_maxseed_upload_rate = global_maxseed_upload_rate
        self.global_maxdownload_rate = global_maxdownload_rate

        self.lock = RLock()
        self.statusmap = {}
        self.currenttotal = {}
        self.dset = Set()
        self.clear_downloadstates()
        
    def adjust_speeds(self):
        self.lock.acquire()
        
        self.calc_bandwidth(DOWNLOAD)
        self.calc_bandwidth(UPLOAD)
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

            
    def get_global_max_speed(self, dir = UPLOAD):
        if dir == UPLOAD:
            if len(self.statusmap[DLSTATUS_DOWNLOADING]) == 0 and len(self.statusmap[DLSTATUS_SEEDING]) > 0:
                # Static overall maximum up rate when seeding
                return self.global_maxseed_upload_rate
            else:
                # Static overall maximum up rate when downloading
                return self.global_maxupload_rate
        else:
            return self.global_maxdownload_rate
           

    def calc_bandwidth(self, dir = UPLOAD):
        
        print >>sys.stderr,"RateManager: CalculateBandwidth",dir
        
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

        print >>sys.stderr,"RateManager: CalculateBandwidth: len workingset",len(workingset)

        # No active file, not need to calculate
        if not workingset:
            return
        
        globalmaxrate = self.get_global_max_speed(dir)
        # See if global rate settings are set to unlimited
        if globalmaxrate == 0:
            # Unlimited rate
            for (d,ds) in workingset:
                d.set_max_speed(dir,d.get_max_desired_speed(dir)) 
            return
        
        print >>sys.stderr,"RateManager: globalmaxrate is",globalmaxrate,dir

        # User set priority is always granted, ignoring global limit
        todoset = []
        for (d,ds) in workingset:
            maxdesiredrate = d.get_max_desired_speed(dir)
            if maxdesiredrate > 0.0:
                d.set_max_speed(dir,maxdesiredrate)
            else:
                todoset.append((d,ds))

        if len(todoset) > 0:
            # Rest divides globalmaxrate equally
            localmaxrate = globalmaxrate / float(len(todoset))
            # if too small than user's problem
            for (d,ds) in todoset:
                d.set_max_speed(dir,localmaxrate)

